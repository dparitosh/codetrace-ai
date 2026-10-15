"""Transactional OSLC publication and collaboration repository.

SQLite/WAL is the first storage adapter. Published resource identities, ETags,
link overrides, audit events and TRS bases survive sessions and process restarts.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import HTTPException
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, DCTERMS

from core.config import settings
from graph.traceability import TYPE_URIS, CT

OSLC = 'http://open-services.net/ns/core#'
AM = 'http://open-services.net/ns/am#'
RM = 'http://open-services.net/ns/rm#'
CM = 'http://open-services.net/ns/cm#'
QM = 'http://open-services.net/ns/qm#'
TRS = 'http://open-services.net/ns/core/trs#'
LINK_PREDICATES = {
    AM + 'derives', AM + 'refines', AM + 'satisfies', AM + 'verifies',
    RM + 'implementedBy', RM + 'validatedBy', RM + 'satisfiedBy', RM + 'decomposedBy', RM + 'elaboratedBy', RM + 'trackedBy',
    CM + 'implementsRequirement', CM + 'tracksRequirement', CM + 'affectsRequirement', CM + 'relatedChangeRequest',
    QM + 'validatesRequirement', QM + 'validatesRequirementCollection', QM + 'usesTestCase', QM + 'usesTestScript',
    QM + 'runsTestCase', QM + 'executesTestScript', QM + 'reportsOnTestCase', QM + 'reportsOnTestPlan',
    QM + 'producedByTestExecutionRecord', QM + 'relatedChangeRequest', QM + 'testsChangeRequest',
    CT + 'references', CT + 'depends_on', CT + 'implements',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(graph):
    return '\n'.join(sorted(line for line in graph.serialize(format='nt').splitlines() if line.strip())) + '\n'


def etag(body):
    return '"' + hashlib.sha256(body.encode()).hexdigest() + '"'


def graph_from_body(body):
    graph = Graph()
    graph.parse(data=body, format='nt')
    return graph


class OSLCStore:
    def __init__(self, path=None):
        self.path = path or settings.OSLC_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction(write=True) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS publications(source_id TEXT PRIMARY KEY, version INTEGER NOT NULL, snapshot_id TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS resources(id TEXT PRIMARY KEY, source_id TEXT NOT NULL, origin_id TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, body TEXT NOT NULL, etag TEXT NOT NULL, version INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, UNIQUE(source_id,origin_id));
                CREATE INDEX IF NOT EXISTS resource_source ON resources(source_id,deleted,id);
                CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, resource_id TEXT NOT NULL, action TEXT NOT NULL, at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS bases(id INTEGER PRIMARY KEY, members TEXT NOT NULL, at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS overrides(resource_id TEXT NOT NULL,predicate TEXT NOT NULL,target TEXT NOT NULL,action TEXT NOT NULL,PRIMARY KEY(resource_id,predicate,target));
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,resource_id TEXT,action TEXT NOT NULL,actor TEXT NOT NULL,at TEXT NOT NULL,details TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,owner_hash TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            ''')
            db.execute('INSERT OR IGNORE INTO bases VALUES(0,?,?)', ('[]', now()))

    @contextmanager
    def transaction(self, write=False):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def uri(self, resource_id):
        return settings.OSLC_PUBLIC_BASE_URL.rstrip('/') + '/resources/' + resource_id

    def provider_uri(self, source_id):
        return settings.OSLC_PUBLIC_BASE_URL.rstrip('/') + '/providers/' + source_id

    def _id(self, source_id, origin_id):
        return str(uuid5(NAMESPACE_URL, source_id + '\n' + origin_id))

    def _base(self, db):
        cutoff = db.execute('SELECT COALESCE(MAX(sequence),0) FROM events').fetchone()[0]
        members = [row[0] for row in db.execute('SELECT id FROM resources WHERE deleted=0 ORDER BY id')]
        db.execute('INSERT OR REPLACE INTO bases VALUES(?,?,?)', (cutoff, json.dumps(members), now()))
        # Keep recent immutable bases; clients of an expired base get 410 and resync.
        db.execute('DELETE FROM bases WHERE id NOT IN (SELECT id FROM bases ORDER BY id DESC LIMIT 20)')

    def _event(self, db, resource_id, action, actor, details):
        db.execute('INSERT INTO events(resource_id,action,at) VALUES(?,?,?)', (resource_id, action, now()))
        db.execute('INSERT INTO audit(resource_id,action,actor,at,details) VALUES(?,?,?,?,?)',
                   (resource_id, action, actor, now(), json.dumps(details, sort_keys=True)))

    def _capacity(self, db, resources_delta=0, events_delta=0, bytes_delta=0):
        if db.execute('SELECT COUNT(*) FROM resources').fetchone()[0] + resources_delta > settings.OSLC_SERVER_MAX_RESOURCES:
            raise HTTPException(507, 'Published OSLC resource capacity is exhausted')
        if db.execute('SELECT COUNT(*) FROM events').fetchone()[0] + events_delta > settings.OSLC_SERVER_MAX_EVENTS:
            raise HTTPException(507, 'OSLC event capacity is exhausted; administrator maintenance is required')
        size = db.execute('SELECT COALESCE(SUM(LENGTH(CAST(body AS BLOB))),0) FROM resources').fetchone()[0]
        if size + bytes_delta > settings.OSLC_SERVER_MAX_BYTES:
            raise HTTPException(507, 'Published OSLC representation capacity is exhausted')

    def publication(self, source_id):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM publications WHERE source_id=?', (source_id,)).fetchone()
            return dict(row) if row else {'source_id': source_id, 'version': 0, 'snapshot_id': None}

    def publish(self, source_id, snapshot, expected_version, actor):
        active_nodes = [node for node in snapshot['nodes'] if not node['properties'].get('deleted')]
        ids = {node['id']: self._id(source_id, node['id']) for node in active_nodes}
        outgoing = {}
        for edge in snapshot['edges']:
            outgoing.setdefault(edge['source'], []).append(edge)
        prepared = {}
        for node in active_nodes:
            resource_id = ids[node['id']]
            uri = URIRef(self.uri(resource_id))
            graph = Graph()
            type_uri = TYPE_URIS.get(node['type'], AM + 'Resource' if node['properties'].get('domain') == 'CODE' else CT + node['type'])
            graph.add((uri, RDF.type, URIRef(type_uri)))
            graph.add((uri, DCTERMS.title, Literal(node['label'])))
            graph.add((uri, DCTERMS.identifier, Literal(resource_id)))
            graph.add((uri, URIRef(OSLC + 'serviceProvider'), URIRef(self.provider_uri(source_id))))
            graph.add((uri, URIRef(OSLC + 'instanceShape'), URIRef(settings.OSLC_PUBLIC_BASE_URL.rstrip('/') + '/shapes/' + node['type'])))
            graph.add((uri, URIRef(CT + 'sourceIdentity'), URIRef(node['id'])))
            graph.add((uri, URIRef(CT + 'approvedSnapshot'), Literal(snapshot['metadata']['snapshot_id'])))
            for key in ('path', 'start', 'source_digest', 'status', 'outcome', 'domain'):
                value = node['properties'].get(key)
                if value is not None:
                    predicate = QM + 'status' if key == 'outcome' else CT + key
                    graph.add((uri, URIRef(predicate), Literal(value)))
            for edge in outgoing.get(node['id'], []):
                target = self.uri(ids[edge['target']]) if edge['target'] in ids else edge['target']
                graph.add((uri, URIRef(edge['type']), URIRef(target)))
            prepared[resource_id] = (node, graph)
        with self.transaction(write=True) as db:
            current = db.execute('SELECT * FROM publications WHERE source_id=?', (source_id,)).fetchone()
            if current and current['snapshot_id'] == snapshot['metadata']['snapshot_id']:
                return dict(current)
            if (current['version'] if current else 0) != expected_version:
                raise HTTPException(409, 'Published source changed. Refresh publication status before publishing.')
            old = {row['id']: row for row in db.execute('SELECT * FROM resources WHERE source_id=?', (source_id,))}
            changes = []
            bytes_delta = 0
            for resource_id, (node, graph) in prepared.items():
                subject = URIRef(self.uri(resource_id))
                for override in db.execute('SELECT * FROM overrides WHERE resource_id=?', (resource_id,)):
                    triple = (subject, URIRef(override['predicate']), URIRef(override['target']))
                    graph.add(triple) if override['action'] == 'added' else graph.remove(triple)
                body = canonical(graph)
                previous = old.get(resource_id)
                if previous and not previous['deleted'] and previous['etag'] == etag(body):
                    continue
                changes.append((resource_id, node, body, previous))
                bytes_delta += len(body.encode()) - (len(previous['body'].encode()) if previous else 0)
            deleted = [row for key, row in old.items() if key not in prepared and not row['deleted']]
            additions = sum(previous is None for _, _, _, previous in changes)
            self._capacity(db, additions, len(changes) + len(deleted), bytes_delta)
            for resource_id, node, body, previous in changes:
                version = previous['version'] + 1 if previous else 1
                db.execute('INSERT OR REPLACE INTO resources VALUES(?,?,?,?,?,?,?,?,0)',
                    (resource_id, source_id, node['id'], node['type'], node['label'], body, etag(body), version))
                self._event(db, resource_id, 'Modification' if previous and not previous['deleted'] else 'Creation', actor,
                            {'snapshot_id': snapshot['metadata']['snapshot_id']})
            for row in deleted:
                db.execute('UPDATE resources SET deleted=1,version=version+1 WHERE id=?', (row['id'],))
                self._event(db, row['id'], 'Deletion', actor, {'snapshot_id': snapshot['metadata']['snapshot_id']})
            version = (current['version'] if current else 0) + 1
            db.execute('INSERT OR REPLACE INTO publications VALUES(?,?,?,?)', (source_id, version, snapshot['metadata']['snapshot_id'], now()))
            self._base(db)
            return {'source_id': source_id, 'version': version, 'snapshot_id': snapshot['metadata']['snapshot_id'],
                    'resources': len(prepared), 'changed_resources': len(changes), 'deleted_resources': len(deleted)}

    def resource(self, resource_id):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM resources WHERE id=?', (resource_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Published resource was not found')
            if row['deleted']:
                raise HTTPException(410, 'Published resource was deleted; consult the TRS change log')
            return dict(row)

    def by_origin(self, source_id, origin_id):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM resources WHERE source_id=? AND origin_id=? AND deleted=0', (source_id, origin_id)).fetchone()
            return dict(row) if row else None

    def query(self, source_id, page=1, page_size=50, kind=None, title=None):
        filters = ['source_id=?', 'deleted=0']; parameters = [source_id]
        if kind:
            kinds = kind if isinstance(kind, list) else [kind]
            filters.append('kind IN (' + ','.join('?' for _ in kinds) + ')'); parameters.extend(kinds)
        if title:
            filters.append('label=?'); parameters.append(title)
        clause = ' AND '.join(filters)
        with self.transaction() as db:
            total = db.execute('SELECT COUNT(*) FROM resources WHERE ' + clause, parameters).fetchone()[0]
            rows = db.execute('SELECT * FROM resources WHERE ' + clause + ' ORDER BY id LIMIT ? OFFSET ?',
                              parameters + [page_size, (page - 1) * page_size]).fetchall()
            return [dict(row) for row in rows], total

    def update(self, resource_id, incoming, expected_etag, actor):
        with self.transaction(write=True) as db:
            row = db.execute('SELECT * FROM resources WHERE id=? AND deleted=0', (resource_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Published resource was not found')
            if row['etag'] != expected_etag:
                raise HTTPException(412, 'Resource ETag changed; reload before updating')
            original = graph_from_body(row['body'])
            source = URIRef(self.uri(resource_id))
            if any(subject != source for subject, _, _ in incoming):
                raise HTTPException(422, 'Only the selected resource subject may be updated')
            old_readonly = {triple for triple in original if str(triple[1]) not in LINK_PREDICATES}
            new_readonly = {triple for triple in incoming if str(triple[1]) not in LINK_PREDICATES}
            if old_readonly != new_readonly:
                raise HTTPException(422, 'Identity, type, source data, and provenance are read-only')
            old_links = {triple for triple in original if str(triple[1]) in LINK_PREDICATES}
            new_links = {triple for triple in incoming if str(triple[1]) in LINK_PREDICATES}
            if any(not isinstance(target, URIRef) or not str(target).startswith(('http://', 'https://', 'urn:')) for _, _, target in new_links):
                raise HTTPException(422, 'Contextual links must reference absolute resource URIs')
            body = canonical(incoming)
            if body == row['body']:
                return dict(row)
            self._capacity(db, events_delta=1, bytes_delta=len(body.encode()) - len(row['body'].encode()))
            for action, triples in (('added', new_links - old_links), ('removed', old_links - new_links)):
                for _, predicate, target in triples:
                    db.execute('INSERT OR REPLACE INTO overrides VALUES(?,?,?,?)', (resource_id, str(predicate), str(target), action))
            db.execute('UPDATE resources SET body=?,etag=?,version=version+1 WHERE id=?', (body, etag(body), resource_id))
            db.execute('UPDATE publications SET version=version+1,updated_at=? WHERE source_id=?', (now(), row['source_id']))
            self._event(db, resource_id, 'Modification', actor, {'added': len(new_links - old_links), 'removed': len(old_links - new_links)})
            self._base(db)
            return {**dict(row), 'body': body, 'etag': etag(body), 'version': row['version'] + 1}

    def base(self, base_id=None):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM bases WHERE id=?', (base_id,)).fetchone() if base_id is not None else db.execute('SELECT * FROM bases ORDER BY id DESC LIMIT 1').fetchone()
            if not row:
                raise HTTPException(410, 'TRS base expired; restart synchronization from /oslc/trs')
            return dict(row)

    def events(self, before=None, limit=50):
        with self.transaction() as db:
            if before is None:
                rows = db.execute('SELECT * FROM events ORDER BY sequence DESC LIMIT ?', (limit,)).fetchall()
            else:
                rows = db.execute('SELECT * FROM events WHERE sequence<=? ORDER BY sequence DESC LIMIT ?', (before, limit)).fetchall()
            return [dict(row) for row in rows]

    def event(self, sequence):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM events WHERE sequence=?', (sequence,)).fetchone()
            if not row:
                raise HTTPException(404, 'TRS event was not found')
            return dict(row)

    def propose(self, owner_hash, body):
        with self.transaction(write=True) as db:
            if db.execute('SELECT COUNT(*) FROM proposals').fetchone()[0] >= settings.OSLC_SERVER_MAX_PROPOSALS:
                raise HTTPException(507, 'Link proposal capacity is exhausted')
            proposal_id = str(uuid4()); created = now()
            db.execute('INSERT INTO proposals VALUES(?,?,?,0,?,?,?)', (proposal_id, owner_hash, 'pending', json.dumps(body), created, created))
            return {'id': proposal_id, 'status': 'pending', 'version': 0, 'created_at': created, **body}

    def proposal(self, proposal_id, owner_hash):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM proposals WHERE id=? AND owner_hash=?', (proposal_id, owner_hash)).fetchone()
            if not row:
                raise HTTPException(404, 'Link proposal was not found in this session')
            return {key: value for key, value in {**dict(row), **json.loads(row['body'])}.items() if key not in {'owner_hash', 'body'}}

    def proposals(self, owner_hash, offset=0, limit=100):
        with self.transaction() as db:
            rows = db.execute('SELECT * FROM proposals WHERE owner_hash=? ORDER BY created_at DESC,id LIMIT ? OFFSET ?', (owner_hash, limit, offset)).fetchall()
            return [{key: value for key, value in {**dict(row), **json.loads(row['body'])}.items() if key not in {'owner_hash', 'body'}} for row in rows]

    def transition(self, proposal_id, owner_hash, expected_status, expected_version, status, details=None):
        with self.transaction(write=True) as db:
            row = db.execute('SELECT * FROM proposals WHERE id=? AND owner_hash=?', (proposal_id, owner_hash)).fetchone()
            if not row:
                raise HTTPException(404, 'Link proposal was not found in this session')
            if row['status'] != expected_status or row['version'] != expected_version:
                raise HTTPException(409, 'Proposal changed; refresh before deciding or applying')
            body = json.loads(row['body'])
            body.setdefault('audit', []).append({'action': status, 'at': now(), **(details or {})})
            db.execute('UPDATE proposals SET status=?,version=version+1,body=?,updated_at=? WHERE id=?',
                       (status, json.dumps(body), now(), proposal_id))
            return {'id': proposal_id, 'status': status, 'version': row['version'] + 1, **body}
