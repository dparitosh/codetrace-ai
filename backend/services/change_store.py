"""Durable, versioned local-workspace dossiers, independent of review sessions.

Access is the existing local reviewer model, not enterprise identity/RBAC.
No source files or external resources are modified by this store.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from fastapi import HTTPException
from core.config import settings

FIELDS = ('title', 'problem', 'impact', 'scope', 'proposal', 'acceptance', 'validation', 'rollback')


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class ChangeStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,state TEXT NOT NULL,
                  snapshot_digest TEXT NOT NULL,graph TEXT NOT NULL,body TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS turns(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,request_id TEXT NOT NULL,
                  state TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(case_id,request_id));
                CREATE INDEX IF NOT EXISTS turns_case ON turns(case_id,created_at,id);
                CREATE TABLE IF NOT EXISTS versions(case_id TEXT NOT NULL,version INTEGER NOT NULL,body TEXT NOT NULL,
                  digest TEXT NOT NULL,PRIMARY KEY(case_id,version));
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
        finally:
            db.close()

    def capacity(self, db):
        size = db.execute('SELECT COALESCE(SUM(LENGTH(CAST(graph AS BLOB))+LENGTH(CAST(body AS BLOB))),0) FROM cases').fetchone()[0]
        for table in ('turns', 'versions'):
            size += db.execute(f'SELECT COALESCE(SUM(LENGTH(CAST(body AS BLOB))),0) FROM {table}').fetchone()[0]
        if size > settings.CHANGE_MAX_BYTES:
            raise HTTPException(507, 'Change-workspace storage capacity is exhausted; an administrator must review the configured storage limit.')

    def row(self, db, case_id):
        row = db.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Change dossier was not found')
        return row

    def pending(self, db, case_id):
        rows = db.execute("SELECT * FROM turns WHERE case_id=? AND state='processing'", (case_id,)).fetchall()
        for row in rows:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(row['created_at'])).total_seconds()
            if elapsed > settings.AI_AGENT_DEADLINE_SECONDS + 60:
                body = json.loads(row['body']); body['error'] = 'Interrupted analysis; retry this turn to recover.'
                db.execute("UPDATE turns SET state='failed',body=? WHERE id=?", (encoded(body), row['id']))
        return db.execute("SELECT COUNT(*) FROM turns WHERE case_id=? AND state='processing'", (case_id,)).fetchone()[0]

    def check(self, db, case_id, revision, draft=True):
        row = self.row(db, case_id)
        if row['revision'] != revision:
            raise HTTPException(409, 'Dossier changed; refresh before editing or reviewing.')
        if draft and row['state'] != 'draft':
            raise HTTPException(409, 'This version is frozen. Create a new draft revision to edit or analyze it.')
        if self.pending(db, case_id):
            raise HTTPException(409, 'Analysis is still active. Refresh before another operation.')
        return row, json.loads(row['body'])

    def save(self, db, row, body, state=None):
        db.execute('UPDATE cases SET body=?,state=?,revision=revision+1,updated_at=? WHERE id=?',
                   (encoded(body), state or row['state'], now(), row['id']))
        self.capacity(db)

    def audit(self, body, action, note=''):
        body['audit'].append({'action': action, 'at': now(), 'actor': 'Local reviewer', 'note': note})

    def create(self, graph, snapshot_digest, selected_id, request_id):
        case_id = request_id  # Caller-generated UUID provides idempotent creation.
        with self.db() as db:
            existing = db.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
            if existing:
                if existing['snapshot_digest'] != snapshot_digest or json.loads(existing['body']).get('creation_context') != selected_id:
                    raise HTTPException(409, 'Creation request ID belongs to another snapshot')
                return case_id
            if db.execute('SELECT COUNT(*) FROM cases').fetchone()[0] >= settings.CHANGE_MAX_CASES:
                raise HTTPException(507, 'Local change queue capacity is exhausted')
            node = next((node for node in graph['nodes'] if node['id'] == selected_id), None)
            if selected_id and node is None:
                raise HTTPException(422, 'Selected context is not in this source snapshot')
            body = {field: '' for field in FIELDS}
            body.update(title='Change: ' + node['label'][:150] if node else 'New change dossier', version=1,
                        selected_id=selected_id, creation_context=selected_id, scope_context_id=selected_id, context_warnings=[],
                        evidence=[], audit=[], automation_review_required=False, agent_generated_fields=[],
                        snapshot_id=graph['metadata'].get('snapshot_id'), limitations=graph['metadata'].get('limitations', []))
            self.audit(body, 'created')
            db.execute('INSERT INTO cases VALUES(?,0,?,?,?,?,?)',
                       (case_id, 'draft', snapshot_digest, encoded(graph), encoded(body), now()))
            self.capacity(db)
        return case_id

    def list(self):
        with self.db() as db:
            return [{'id': row['id'], 'revision': row['revision'], 'state': row['state'], 'title': body['title'],
                     'version': body['version'], 'updated_at': row['updated_at']}
                    for row in db.execute('SELECT id,revision,state,body,updated_at FROM cases ORDER BY updated_at DESC,id')
                    for body in [json.loads(row['body'])]]

    def get(self, case_id, graph=False):
        with self.db() as db:
            row = self.row(db, case_id)
            self.pending(db, case_id)
            result = {key: row[key] for key in ('id', 'revision', 'state', 'snapshot_digest', 'updated_at')}
            result.update(json.loads(row['body']))
            result['turns'] = [dict(json.loads(turn['body']), id=turn['id'], state=turn['state'], request_id=turn['request_id'])
                               for turn in db.execute('SELECT * FROM turns WHERE case_id=? ORDER BY created_at,id', (case_id,))]
            result['versions'] = [{'version': v['version'], 'digest': v['digest'], 'dossier': json.loads(v['body'])}
                                  for v in db.execute('SELECT * FROM versions WHERE case_id=? ORDER BY version', (case_id,))]
            if graph:
                result['graph'] = json.loads(row['graph'])
            return result

    def update(self, case_id, revision, fields):
        with self.db() as db:
            row, body = self.check(db, case_id, revision)
            for key in FIELDS:
                if key in fields:
                    if fields[key] != body[key]:
                        body['agent_generated_fields'] = [name for name in body.get('agent_generated_fields', []) if name != key]
                        if key == 'scope':
                            body['scope_context_id'] = body.get('selected_id')
                            body['context_warnings'] = []
                    body[key] = fields[key]
            self.audit(body, 'draft_saved')
            self.save(db, row, body)

    def remove_evidence(self, case_id, revision, evidence_id):
        with self.db() as db:
            row, body = self.check(db, case_id, revision)
            retained = [item for item in body['evidence'] if item['id'] != evidence_id]
            if len(retained) == len(body['evidence']):
                raise HTTPException(404, 'Evidence item was not found in this dossier')
            body['evidence'] = retained
            self.audit(body, 'draft_evidence_removed', evidence_id)
            self.save(db, row, body)

    def evidence(self, body, graph, node_id, provenance):
        node = next((n for n in graph['nodes'] if n['id'] == node_id), None)
        if node is None:
            raise HTTPException(422, 'Evidence must reference a resource in the frozen snapshot')
        key = digest([body['snapshot_id'], node_id])
        existing = next((item for item in body['evidence'] if item['id'] == key), None)
        if existing:
            observations = existing.setdefault('observations', [existing['provenance']])
            if provenance not in observations:
                observations.append(provenance)
            return
        if len(body['evidence']) >= 200:
            raise HTTPException(413, 'Dossier evidence is limited to 200 resources')
        edges = [edge for edge in graph['edges'] if node_id in (edge['source'], edge['target'])]
        findings = graph.get('source_assessments') or {}
        body['evidence'].append({'id': key, 'node': node, 'snapshot_id': body['snapshot_id'], 'captured_at': now(),
                                 'provenance': provenance, 'observations': [provenance], 'relationships': edges[:50], 'relationship_count': len(edges),
                                 'relationships_truncated': len(edges) > 50,
                                 'source_findings': [f for f in findings.get('security', {}).get('findings', [])
                                                     if node['properties'].get('path') and f.get('file') == node['properties']['path']][:30]})

    def capture(self, case_id, revision, node_id, turn_id='', agent_id='', citation_id=''):
        with self.db() as db:
            row, body = self.check(db, case_id, revision)
            provenance = {'kind': 'manual_snapshot_selection'}
            if turn_id:
                turn = db.execute("SELECT * FROM turns WHERE id=? AND case_id=? AND state='completed'", (turn_id, case_id)).fetchone()
                if not turn:
                    raise HTTPException(422, 'Choose a completed conversation turn from this dossier')
                analyses = json.loads(turn['body']).get('analyses', [])
                match = next((citation for analysis in analyses if analysis['agent_id'] == agent_id
                              for citation in analysis['result']['citations'] if citation['citation_id'] == citation_id), None)
                if match is None or match['node_id'] != node_id:
                    raise HTTPException(422, 'Citation identity does not match this turn and resource')
                provenance = {'kind': 'agent_observation', 'turn_id': turn_id, 'agent_id': agent_id, 'citation_id': citation_id}
            self.evidence(body, json.loads(row['graph']), node_id, provenance)
            self.audit(body, 'evidence_captured', node_id)
            self.save(db, row, body)

    def reserve(self, case_id, revision, request_id, question, selected_id, automate, agent_id='trace-explorer'):
        with self.db() as db:
            row = self.row(db, case_id)
            self.pending(db, case_id)
            existing = db.execute('SELECT * FROM turns WHERE case_id=? AND request_id=?', (case_id, request_id)).fetchone()
            if existing:
                old = json.loads(existing['body'])
                if (old['question'], old.get('selected_id'), old['automate'], old.get('agent_id', 'trace-explorer')) != (question, selected_id, automate, agent_id):
                    raise HTTPException(409, 'Request ID was already used with different analysis inputs')
                if existing['state'] == 'completed':
                    return existing['id'], False, None
                if existing['state'] == 'processing':
                    raise HTTPException(409, 'This analysis is still processing; refresh the conversation before retrying')
            self.check(db, case_id, revision)
            graph = json.loads(row['graph'])
            if selected_id and not any(node['id'] == selected_id for node in graph['nodes']):
                raise HTTPException(422, 'Conversation context is not in this dossier snapshot')
            if not existing and db.execute('SELECT COUNT(*) FROM turns WHERE case_id=?', (case_id,)).fetchone()[0] >= 100:
                raise HTTPException(413, 'Conversation is limited to 100 turns per dossier')
            turn_id = existing['id'] if existing else str(uuid4())
            attempt = str(uuid4())
            payload = {'question': question, 'selected_id': selected_id, 'automate': automate, 'agent_id': agent_id, 'created_at': now(), 'analyses': [], 'attempt': attempt}
            if existing:
                db.execute("UPDATE turns SET state='processing',body=?,created_at=? WHERE id=?", (encoded(payload), now(), turn_id))
            else:
                db.execute("INSERT INTO turns VALUES(?,?,?,'processing',?,?)", (turn_id, case_id, request_id, encoded(payload), now()))
            self.capacity(db)
            return turn_id, True, attempt

    def finish(self, case_id, turn_id, analyses, attempt):
        with self.db() as db:
            row = self.row(db, case_id); body = json.loads(row['body'])
            turn = db.execute("SELECT * FROM turns WHERE id=? AND case_id=? AND state='processing'", (turn_id, case_id)).fetchone()
            if turn is None or json.loads(turn['body']).get('attempt') != attempt:
                raise HTTPException(409, 'Analysis attempt expired; refresh before retrying')
            payload = json.loads(turn['body']); payload['analyses'] = analyses
            body.setdefault('scope_context_id', body.get('selected_id'))
            if payload['automate']:
                graph = json.loads(row['graph'])
                for analysis in analyses:
                    for citation in analysis['result']['citations'][:12]:
                        self.evidence(body, graph, citation['node_id'],
                                      {'kind': 'agent_observation', 'turn_id': turn_id, 'agent_id': analysis['agent_id'], 'citation_id': citation['citation_id']})
                suggestions = {
                    'problem': payload['question'],
                    'scope': f"Frozen snapshot {body['snapshot_id']}; selected context: {payload.get('selected_id') or 'whole snapshot'}. Review the captured resources to define the exact change boundary.",
                    'proposal': '\n\n'.join(f"{a['agent_id']} (proposed analysis; human review required):\n{a['result']['answer'][:3000]}" +
                        ('\n[Excerpt: read the full response in Conversation.]' if len(a['result']['answer']) > 3000 else '') for a in analyses),
                    'impact': f"Assess affected resources using the {len(body['evidence'])} captured evidence item(s); causal impact and runtime use remain unverified.",
                    'acceptance': 'Review the proposed correction against the captured evidence; define change-specific success criteria before approval.',
                    'validation': 'Run affected tests and review changed graph relationships. No test execution or passing outcome is asserted by this agent analysis.',
                }
                owned = set(body.get('agent_generated_fields', []))
                for field, value in suggestions.items():
                    if not body[field] or (field in {'proposal', 'impact', 'scope'} and field in owned):
                        body[field] = value; owned.add(field)
                        if field == 'scope':
                            body['scope_context_id'] = payload.get('selected_id')
                body['agent_generated_fields'] = sorted(owned)
                body['automation_review_required'] = True
            body['selected_id'] = payload.get('selected_id')
            body['context_warnings'] = (
                ['The investigation context changed. Review the retained scope against the selected context before submission.']
                if body['scope'] and body['scope_context_id'] != body['selected_id'] else [])
            self.audit(body, 'automated_draft' if payload['automate'] else 'conversation_turn', turn_id)
            payload['completed_at'] = now()
            db.execute("UPDATE turns SET state='completed',body=? WHERE id=?", (encoded(payload), turn_id))
            self.save(db, row, body)

    def fail(self, case_id, turn_id, attempt):
        with self.db() as db:
            row = db.execute("SELECT * FROM turns WHERE id=? AND case_id=? AND state='processing'", (turn_id, case_id)).fetchone()
            if row and json.loads(row['body']).get('attempt') == attempt:
                payload = json.loads(row['body']); payload['error'] = 'Analysis interrupted or failed. Review evidence and retry this turn.'
                db.execute("UPDATE turns SET state='failed',body=? WHERE id=?", (encoded(payload), turn_id))

    def transition(self, case_id, revision, action, note, acknowledged):
        with self.db() as db:
            row, body = self.check(db, case_id, revision, draft=False)
            state = row['state']
            if action == 'submit' and state == 'draft':
                missing = [field for field in FIELDS if field != 'rollback' and not body[field].strip()]
                if not body['evidence']:
                    missing.append('evidence')
                if body['automation_review_required'] and not acknowledged:
                    missing.append('human review of automated draft')
                if missing:
                    raise HTTPException(422, 'Complete before submitting: ' + ', '.join(missing))
                if body['automation_review_required']:
                    body['automation_review_required'] = False
                    self.audit(body, 'automated_draft_reviewed')
                turns = [dict(json.loads(t['body']), id=t['id'], state=t['state'], request_id=t['request_id'])
                         for t in db.execute('SELECT * FROM turns WHERE case_id=? ORDER BY created_at,id', (case_id,))]
                frozen = {**{key: value for key, value in body.items() if key != 'audit'},
                          'snapshot_digest': row['snapshot_digest'],
                          'turn_ids': [t['id'] for t in turns], 'turns': turns}
                db.execute('INSERT INTO versions VALUES(?,?,?,?)', (case_id, body['version'], encoded(frozen), digest(frozen)))
                body['submitted_digest'] = digest(frozen); state = 'submitted'
            elif action in {'approve', 'reject', 'request_changes'} and state == 'submitted':
                if not note.strip():
                    raise HTTPException(422, 'Record a reviewer decision note')
                state = {'approve': 'approved', 'reject': 'rejected', 'request_changes': 'changes_requested'}[action]
            elif action == 'revise' and state in {'submitted', 'approved', 'rejected', 'changes_requested'}:
                body['version'] += 1; body.pop('submitted_digest', None); state = 'draft'
            else:
                raise HTTPException(409, 'This action is not available in the current dossier state')
            self.audit(body, action, note)
            self.save(db, row, body, state)
