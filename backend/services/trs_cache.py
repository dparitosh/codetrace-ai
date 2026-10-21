"""Durable TRS replay with exact-event continuity and conservative full fallback."""
import hashlib
import json
import sqlite3
from urllib.parse import urljoin

from rdflib import Graph, URIRef
from rdflib.namespace import RDF
from core.config import settings


def collect_incremental(provider, client):
    from services.oslc_service import (TRS, OSLC, allowed_url, ingest_provider,
                                       parse_rdf, provider_headers, read_response)
    headers = provider_headers(provider)
    fingerprint = hashlib.sha256(json.dumps([provider.model_dump(), headers], sort_keys=True).encode()).hexdigest()
    settings.TRS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.TRS_CACHE_PATH, timeout=10)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS checkpoints(provider TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL)')
        row = db.execute('SELECT fingerprint,version,body FROM checkpoints WHERE provider=?', (provider.id,)).fetchone()
        cached = json.loads(row[2]) if row and row[0] == fingerprint else None
        expected = row[1] if row else 0
        fetched, next_pages, pages = Graph(), {}, 0

        def fetch(uri):
            nonlocal pages
            allowed_url(provider, uri)
            if pages >= settings.OSLC_MAX_PAGES:
                raise ValueError('TRS incremental replay page limit reached')
            pages += 1
            content, kind, next_uri = read_response(client, uri, headers, with_next=True)
            page = parse_rdf(content, kind)
            fetched.__iadd__(page)
            if len(fetched) > settings.MAX_GRAPH_EDGES:
                raise ValueError('TRS incremental replay triple limit reached')
            if next_uri:
                next_pages[uri] = urljoin(uri, next_uri)
            return page

        result, bases = None, []
        if cached and cached.get('event'):
            root = fetch(provider.endpoint)
            bases = sorted(str(value) for value in root.objects(None, URIRef(TRS + 'base')))
            # A new base or a missing exact checkpoint forces a full rebuild.
            if bases and bases == cached['bases']:
                pending, seen = [provider.endpoint], set()
                found = False
                while pending and pages <= settings.OSLC_MAX_PAGES:
                    uri = pending.pop(0)
                    if uri in seen:
                        continue
                    seen.add(uri)
                    page = root if uri == provider.endpoint else fetch(uri)
                    marker = URIRef(cached['event']['id'])
                    orders = [int(value) for value in fetched.objects(marker, URIRef(TRS + 'order'))]
                    if orders == [cached['event']['order']]:
                        found = True
                        break
                    for predicate in (TRS + 'changeLog', TRS + 'previous', OSLC + 'nextPage'):
                        pending.extend(str(value) for value in page.objects(None, URIRef(predicate)) if isinstance(value, URIRef))
                    if uri in next_pages:
                        pending.append(next_pages[uri])
                if found:
                    changes = {}
                    for event in fetched.subjects(URIRef(TRS + 'changed'), None):
                        order = int(next(iter(fetched.objects(event, URIRef(TRS + 'order'))), -1))
                        if order <= cached['event']['order']:
                            continue
                        changed = str(next(iter(fetched.objects(event, URIRef(TRS + 'changed')))))
                        deletion = (event, RDF.type, URIRef(TRS + 'Deletion')) in fetched
                        if order >= changes.get(changed, (-1, False))[0]:
                            changes[changed] = (order, deletion)
                    for uri, (_, deletion) in changes.items():
                        if not deletion:
                            page = fetch(uri)
                            if not any(page.triples((URIRef(uri), RDF.type, None))):
                                raise ValueError('Changed TRS resource is missing its representation')
                    delta = ingest_provider(provider, client, supplied_graph=fetched)
                    old_resources, old_links, old_properties, old_events, _ = cached['result']
                    nodes = {item['uri']: item for item in old_resources}
                    properties = dict(old_properties)
                    incoming = {item['uri']: item for item in delta[0]}
                    deleted = {uri for uri, (_, deletion) in changes.items() if deletion}
                    for uri in changes:
                        if uri not in incoming:
                            raise ValueError('Changed TRS resource has no supported resource type')
                        if uri in deleted and uri in nodes:
                            properties[uri] = {**properties.get(uri, {}), **delta[2].get(uri, {})}
                        else:
                            nodes[uri] = incoming[uri]
                            properties[uri] = delta[2].get(uri, {})
                    # Preserve unchanged source assertions across target deletion/recreation.
                    # The target tombstone carries deletion state in the snapshot.
                    links = [item for item in old_links if item['source']['uri'] not in changes]
                    links.extend(item for item in delta[1] if item['source']['uri'] in changes and item['source']['uri'] not in deleted)
                    events = {item['id']: item for item in old_events}
                    events.update({item['id']: item for item in delta[3]})
                    ordered = sorted(events.values(), key=lambda event: (event['order'], event['id']))[-settings.TRS_CACHE_EVENTS:]
                    status = {**delta[4], 'resources': len(nodes), 'pages': pages, 'sync_mode': 'incremental',
                              'checkpoint': {**delta[4]['checkpoint'], 'latest_order': max((item['order'] for item in ordered), default=None)}}
                    result = (list(nodes.values()), links, properties, ordered, status)
                    if len(nodes) > settings.OSLC_MAX_RESOURCES or len(links) > settings.MAX_GRAPH_EDGES:
                        raise ValueError('TRS accumulated snapshot exceeds configured limits')
        if result is None:
            result = ingest_provider(provider, client)
            result[4]['sync_mode'] = 'full'
            # A full reconstruction is authoritative only when complete.
            if result[4]['status'] != 'ready':
                return result
            if provider.file_path:
                return result
            root = fetch(provider.endpoint)
            bases = sorted(str(value) for value in root.objects(None, URIRef(TRS + 'base')))
        events = result[3]
        event = max(events, key=lambda item: (item['order'], item['id'])) if events else None
        body = json.dumps({'bases': bases, 'event': event, 'result': result})
        if len(body.encode()) > settings.TRS_CACHE_MAX_BYTES:
            raise ValueError('TRS cache snapshot exceeds configured storage limit')
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT version FROM checkpoints WHERE provider=?', (provider.id,)).fetchone()
        if (current[0] if current else 0) != expected:
            raise ValueError('Concurrent TRS sync changed the checkpoint; retry')
        db.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?,?,?)', (provider.id, fingerprint, expected + 1, body))
        db.commit()
        return result
    finally:
        db.close()
