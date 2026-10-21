"""Bounded OSLC RDF snapshots and TRS base/change-log ingestion.

Only administrator-configured origins/path prefixes are fetched. References are
never followed as arbitrary navigation; external JSON-LD contexts are disabled.
"""
import json
import os
import base64
import hashlib
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlsplit, urljoin

import httpx
from dotenv import dotenv_values
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS, DCTERMS

from core.config import PROJECT_ROOT, settings

OSLC = 'http://open-services.net/ns/core#'
TRS = 'http://open-services.net/ns/core/trs#'
CT = 'urn:codetrace:vocab:'
TYPE_MAP = {
    'http://open-services.net/ns/rm#Requirement': ('requirement', 'RM'),
    'http://open-services.net/ns/rm#RequirementCollection': ('requirement_collection', 'RM'),
    'http://open-services.net/ns/am#Resource': ('architecture', 'AM'),
    'http://open-services.net/ns/cm#ChangeRequest': ('change_request', 'CM'),
    'http://open-services.net/ns/cm#Defect': ('change_request', 'CM'),
    'http://open-services.net/ns/qm#TestCase': ('test', 'QM'),
    'http://open-services.net/ns/qm#TestPlan': ('test_plan', 'QM'),
    'http://open-services.net/ns/qm#TestScript': ('test_script', 'QM'),
    'http://open-services.net/ns/qm#TestExecutionRecord': ('test_execution_record', 'QM'),
    'http://open-services.net/ns/qm#TestResult': ('test_result', 'QM'),
    'http://open-services.net/ns/config#Configuration': ('configuration', 'CONFIG'),
    'http://open-services.net/ns/config#Stream': ('configuration', 'CONFIG'),
    'http://open-services.net/ns/config#Baseline': ('configuration', 'CONFIG'),
    OSLC + 'ResourceShape': ('resource_shape', 'SCHEMA'),
    TRS + 'TrackedResourceSet': ('tracked_resource', 'TRS'),
}


def server_secret(name):
    if not name:
        return None
    if name in os.environ:
        return os.environ[name]
    for file in (PROJECT_ROOT / '.env.local', PROJECT_ROOT / '.env'):
        if file.is_file():
            value = dotenv_values(file).get(name)
            if value is not None:
                return value
    return None


def local_path(value):
    path = Path(value)
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def provider_headers(provider):
    headers = {'Accept': 'text/turtle, application/ld+json, application/rdf+xml', 'OSLC-Core-Version': '2.0'}
    if provider.auth_type == 'basic':
        username, password = server_secret(provider.username_env), server_secret(provider.password_env)
        if not username or not password:
            raise ValueError('Configured credential variables are missing')
        headers['Authorization'] = 'Basic ' + base64.b64encode((username + ':' + password).encode()).decode()
    elif provider.auth_type == 'bearer':
        token = server_secret(provider.token_env)
        if provider.token_env and not token:
            raise ValueError('Configured credential variable is missing')
        if token:
            headers['Authorization'] = 'Bearer ' + token
    if provider.configuration_uri:
        headers['Configuration-Context'] = provider.configuration_uri
    return headers


def allowed_url(provider, url):
    base = urlsplit(provider.allowed_base_url or provider.endpoint)
    target = urlsplit(url)
    prefix = unquote(base.path).rstrip('/') + '/'
    target_path = target.path
    for _ in range(4):
        decoded = unquote(target_path)
        if decoded == target_path:
            break
        target_path = decoded
    def origin(value):
        return value.scheme, value.hostname, value.port or (443 if value.scheme == 'https' else 80)
    if origin(target) != origin(base):
        raise ValueError('Linked OSLC endpoint is outside the configured origin')
    if (target.username or target.password or target.fragment or '\\' in target_path
            or '%' in target_path or any(part in {'.', '..'} for part in target_path.split('/'))
            or any(ord(char) < 32 for char in target_path)):
        raise ValueError('Invalid linked OSLC endpoint')
    if target_path != prefix.rstrip('/') and not target_path.startswith(prefix):
        raise ValueError('Linked OSLC endpoint is outside the configured path prefix')
    return url


def read_response(client, url, headers, with_next=False):
    with client.stream('GET', url, headers=headers) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > settings.OSLC_MAX_RESPONSE_BYTES:
                raise ValueError('Provider response exceeds OSLC_MAX_RESPONSE_BYTES')
            content.extend(chunk)
        result = (bytes(content), response.headers.get('content-type', '').split(';')[0])
        return (*result, response.links.get('next', {}).get('url')) if with_next else result


def reject_remote_contexts(value):
    if isinstance(value, dict):
        if '@context' in value:
            context = value['@context']
            contexts = context if isinstance(context, list) else [context]
            if any(isinstance(item, str) or isinstance(item, dict) and '@import' in item for item in contexts):
                raise ValueError('Remote JSON-LD contexts are disabled; use inline or expanded JSON-LD')
        for item in value.values():
            reject_remote_contexts(item)
    elif isinstance(value, list):
        for item in value:
            reject_remote_contexts(item)


def parse_rdf(content, content_type='', suffix=''):
    if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
        raise ValueError('RDF/XML entity declarations are disabled')
    formats = {'application/ld+json': 'json-ld', 'application/json': 'json-ld',
               'text/turtle': 'turtle', 'application/rdf+xml': 'xml',
               '.json': 'json-ld', '.jsonld': 'json-ld', '.ttl': 'turtle', '.rdf': 'xml', '.xml': 'xml'}
    format = formats.get(content_type) or formats.get(suffix)
    if format is None:
        raise ValueError('Expected JSON-LD, Turtle, or RDF/XML content')
    if format == 'json-ld':
        reject_remote_contexts(json.loads(content))
    graph = Graph()
    try:
        graph.parse(data=content, format=format)
    except Exception as exc:
        raise ValueError('Provider returned invalid RDF content') from exc
    if len(graph) > settings.MAX_GRAPH_EDGES:
        raise ValueError('Provider RDF exceeds the graph triple limit')
    return graph


def ingest_provider(provider, client, supplied_graph=None):
    graph = Graph() if supplied_graph is None else supplied_graph
    complete = True
    pages = 0
    visited = set()
    warnings = []
    page_next = {}
    headers = provider_headers(provider)

    def fetch(url):
        nonlocal pages, complete
        if url in visited:
            complete = False
            return Graph()
        if pages >= settings.OSLC_MAX_PAGES:
            complete = False
            return Graph()
        allowed_url(provider, url)
        visited.add(url)
        pages += 1
        content, kind, next_url = read_response(client, url, headers, with_next=True)
        if next_url:
            page_next[url] = urljoin(url, next_url)
        page = parse_rdf(content, kind)
        graph.__iadd__(page)
        if len(graph) > settings.MAX_GRAPH_EDGES:
            raise ValueError('Combined provider RDF exceeds the graph triple limit')
        return page

    if supplied_graph is not None:
        pass
    elif provider.file_path:
        path = local_path(provider.file_path)
        if path.stat().st_size > settings.OSLC_MAX_RESPONSE_BYTES:
            raise ValueError('Provider RDF file exceeds OSLC_MAX_RESPONSE_BYTES')
        graph = parse_rdf(path.read_bytes(), suffix=path.suffix.lower())
    else:
        pending = [provider.endpoint]
        while pending:
            page_url = pending.pop(0)
            page = fetch(page_url)
            if page_next.get(page_url) in visited:
                complete = False
            for target in page.objects(None, URIRef(OSLC + 'nextPage')):
                if str(target) in visited:
                    complete = False
            if page_url in page_next and page_next[page_url] not in visited and page_next[page_url] not in pending:
                pending.append(page_next[page_url])
            for predicate in (OSLC + 'nextPage', TRS + 'base', TRS + 'changeLog', TRS + 'previous'):
                pending.extend(sorted(str(value) for value in page.objects(None, URIRef(predicate))
                                      if isinstance(value, URIRef) and str(value) not in visited and str(value) not in pending))
            if pages >= settings.OSLC_MAX_PAGES:
                if pending:
                    complete = False
                break
        # Fetch explicitly listed TRS base members and changed resources.
        if provider.domain == 'TRS':
            targets = {str(value) for value in graph.objects(None, RDFS.member) if isinstance(value, URIRef)}
            targets.update(str(value) for value in graph.objects(None, URIRef('http://www.w3.org/ns/ldp#contains')) if isinstance(value, URIRef))
            event_state = {}
            cutoff = next(iter(graph.objects(None, URIRef(TRS + 'cutoffEvent'))), None)
            cutoff_order = int(next(iter(graph.objects(cutoff, URIRef(TRS + 'order'))), 0)) if cutoff else 0
            for event in graph.subjects(URIRef(TRS + 'changed'), None):
                changed = str(next(iter(graph.objects(event, URIRef(TRS + 'changed')))))
                order = int(next(iter(graph.objects(event, URIRef(TRS + 'order'))), 0))
                if order > cutoff_order and order >= event_state.get(changed, (0, False))[0]:
                    event_state[changed] = (order, (event, RDF.type, URIRef(TRS + 'Deletion')) in graph)
            targets.update(event_state)
            targets = sorted(targets)
            if len(targets) > settings.OSLC_MAX_RESOURCES:
                complete = False
                targets = targets[:settings.OSLC_MAX_RESOURCES]
            for target in targets:
                if not any(predicate != RDF.type for _, predicate, _ in graph.triples((URIRef(target), None, None))):
                    if pages >= settings.OSLC_MAX_PAGES:
                        complete = False
                        break
                    # A deletion may return 404; retain its event rather than dereference it.
                    deletion = event_state.get(target, (0, False))[1]
                    if not deletion:
                        fetch(target)

    resources, enrichment, events = [], {}, []
    subjects = sorted({subject for subject, _, value in graph.triples((None, RDF.type, None))
                       if isinstance(subject, URIRef) and str(value) in TYPE_MAP}, key=str)
    if len(subjects) > settings.OSLC_MAX_RESOURCES:
        complete = False
        subjects = subjects[:settings.OSLC_MAX_RESOURCES]
    known = set()
    for subject in subjects:
        types = sorted(str(value) for value in graph.objects(subject, RDF.type))
        kind, domain = next(TYPE_MAP[value] for value in types if value in TYPE_MAP)
        title = next(iter(graph.objects(subject, DCTERMS.title)), None) or next(iter(graph.objects(subject, RDFS.label)), None) or str(subject).rsplit('/', 1)[-1]
        uri = str(subject)
        known.add(uri)
        resources.append({'uri': uri, 'kind': kind, 'label': str(title)[:512], 'provider_uri': provider.endpoint or 'urn:codetrace:provider:' + provider.id})
        properties = {'domain': domain, 'provider_id': provider.id, 'rdf_types': types,
                      'configuration_uri': provider.configuration_uri, 'origin': 'oslc_provider'}
        for predicate, name in ((DCTERMS.identifier, 'identifier'), (DCTERMS.modified, 'modified'),
                                (DCTERMS.description, 'description'), (URIRef(OSLC + 'instanceShape'), 'resource_shape'),
                                (URIRef('http://open-services.net/ns/cm#status'), 'status')):
            value = next(iter(graph.objects(subject, predicate)), None)
            if value is not None:
                properties[name] = str(value)[:2000]
        if 'status' not in properties:
            value = next(iter(graph.objects(subject, URIRef(CT + 'status'))), None)
            if value is not None:
                properties['status'] = str(value)[:2000]
        outcome = next(iter(graph.objects(subject, URIRef('http://open-services.net/ns/qm#status'))), None)
        if outcome is not None:
            properties['outcome'] = str(outcome)[:512]
        enrichment[uri] = properties
    for event, _, type_uri in graph.triples((None, RDF.type, None)):
        if str(type_uri) not in {TRS + 'Creation', TRS + 'Modification', TRS + 'Deletion'}:
            continue
        changed = next(iter(graph.objects(event, URIRef(TRS + 'changed'))), None)
        order = next(iter(graph.objects(event, URIRef(TRS + 'order'))), None)
        if isinstance(changed, URIRef):
            events.append({'id': str(event), 'resource_uri': str(changed), 'action': str(type_uri).split('#')[-1],
                           'order': int(order) if order is not None else 0, 'provider_id': provider.id,
                           'at': str(next(iter(graph.objects(event, DCTERMS.created)), ''))})
    events.sort(key=lambda event: (event['order'], event['id']))
    cutoffs = sorted(str(value) for value in graph.objects(None, URIRef(TRS + 'cutoffEvent')))
    cutoff_orders = [event['order'] for event in events if event['id'] in cutoffs]
    if provider.domain == 'TRS' and any(value != str(RDF.nil) and value not in {event['id'] for event in events} for value in cutoffs):
        complete = False
        warnings.append('Base cutoff event was not found in the retrieved change log; a complete resynchronization is required.')
    # Keep deletion tombstones so a deleted resource cannot look active.
    latest = {}
    for event in events:
        if cutoff_orders and event['order'] <= max(cutoff_orders):
            continue
        latest[event['resource_uri']] = event
    for uri, event in latest.items():
        if event['action'] == 'Deletion':
            if uri not in known:
                resources.append({'uri': uri, 'kind': 'tracked_resource', 'label': uri.rsplit('/', 1)[-1][:512], 'provider_uri': provider.endpoint})
                known.add(uri)
            enrichment.setdefault(uri, {}).update(domain='TRS', deleted=True, trs_order=event['order'], provider_id=provider.id)

    links = []
    for source, predicate, target in sorted(graph, key=lambda triple: tuple(map(str, triple))):
        if str(source) not in known or not isinstance(target, URIRef) or predicate == RDF.type:
            continue
        if enrichment.get(str(source), {}).get('deleted'):
            continue
        if not str(predicate).startswith(('http://open-services.net/ns/', CT)):
            continue
        code_id = next(iter(graph.objects(target, URIRef(CT + 'codeId'))), None)
        links.append({'source': {'uri': str(source)}, 'predicate': str(predicate),
                      'target': {'code_id': str(code_id)} if isinstance(code_id, Literal) else {'uri': str(target)},
                      'asserted_by': provider.endpoint or 'urn:codetrace:provider:' + provider.id})
    if not complete:
        warnings.append('Provider snapshot is partial because page/resource limits were reached.')
    checkpoint = {'latest_order': max((event['order'] for event in events), default=None),
                  'base_cutoff': cutoffs,
                  'complete': complete}
    return resources, links, enrichment, events, {'id': provider.id, 'label': provider.label,
        'domain': provider.domain, 'status': 'ready' if complete else 'partial', 'resources': len(resources),
        'pages': pages, 'warnings': warnings, 'checkpoint': checkpoint}


def collect_oslc(repository_id):
    resources, links, properties, events, statuses = {}, [], {}, [], []
    with httpx.Client(timeout=settings.OSLC_TIMEOUT_SECONDS, follow_redirects=False) as client:
        for provider in settings.OSLC_PROVIDERS:
            if provider.repository_ids and repository_id not in provider.repository_ids:
                continue
            try:
                if provider.domain == 'TRS' and provider.endpoint and settings.TRS_INCREMENTAL:
                    from services.trs_cache import collect_incremental
                    nodes, edges, enrich, changes, status = collect_incremental(provider, client)
                else:
                    nodes, edges, enrich, changes, status = ingest_provider(provider, client)
                if provider.configuration_uri:
                    def scoped(uri):
                        return 'urn:codetrace:configuration-resource:' + hashlib.sha256(
                            (provider.configuration_uri + '\n' + uri).encode()).hexdigest()
                    mapping = {node['uri']: scoped(node['uri']) for node in nodes}
                    enrich = {mapping.get(uri, uri): {**value, 'concept_uri': uri,
                              'configuration_uri': provider.configuration_uri} for uri, value in enrich.items()}
                    nodes = [{**node, 'uri': mapping[node['uri']]} for node in nodes]
                    edges = [{**edge, 'configuration_uri': provider.configuration_uri,
                              'source': {**edge['source'], 'uri': mapping.get(edge['source']['uri'], scoped(edge['source']['uri']))},
                              'target': ({**edge['target'], 'uri': mapping.get(edge['target']['uri'], scoped(edge['target']['uri']))}
                                         if 'uri' in edge['target'] else edge['target'])} for edge in edges]
                    changes = [{**event, 'resource_uri': mapping.get(event['resource_uri'], scoped(event['resource_uri']))}
                               for event in changes]
                resources.update({node['uri']: node for node in nodes})
                links.extend(edges); properties.update(enrich); events.extend(changes); statuses.append(status)
            except (ValueError, OSError, sqlite3.Error, httpx.HTTPError) as exc:
                # Endpoint URLs and credentials must not leak through exception strings.
                statuses.append({'id': provider.id, 'label': provider.label, 'domain': provider.domain,
                                 'status': 'unavailable', 'resources': 0,
                                 'warnings': ['Provider could not be read. Check central configuration, credentials, format, and connectivity.']})
    return list(resources.values()), links, properties, sorted(events, key=lambda event: (event['order'], event['id'])), statuses
