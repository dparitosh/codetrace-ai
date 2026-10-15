"""Bounded SQLite review sessions shared by workers on one host.

Use a private local disk, not a network filesystem. Tokens are hashed; review
payloads are retained until explicit end or expiry, including across restarts.
"""
import hashlib
import json
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from core.config import settings


def stamp():
    return datetime.now(timezone.utc).isoformat()


class SharedCapacity:
    def __init__(self, store):
        self.store = store
        self.local = threading.local()

    def acquire(self, blocking=False):
        if blocking:
            raise ValueError('Shared capacity only supports fail-fast acquisition')
        token = secrets.token_hex(24)
        with self.store.transaction() as db:
            db.execute('DELETE FROM work_leases WHERE expires <= ?', (time.time(),))
            if db.execute('SELECT COUNT(*) FROM work_leases').fetchone()[0] >= settings.MAX_CONCURRENT_ANALYSES:
                return False
            db.execute('INSERT INTO work_leases VALUES(?,?)', (token, time.time() + 60))
        stop = threading.Event()

        def renew():
            while not stop.wait(15):
                try:
                    with self.store.transaction() as db:
                        db.execute('UPDATE work_leases SET expires=? WHERE token=?', (time.time() + 60, token))
                except sqlite3.Error:
                    # A failed renewal cannot silently re-create an expired lease.
                    return
        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
        self.local.lease = (token, stop, thread)
        return True

    def release(self):
        token, stop, thread = self.local.lease
        stop.set()
        thread.join(timeout=11)
        with self.store.transaction() as db:
            db.execute('DELETE FROM work_leases WHERE token=?', (token,))
        del self.local.lease


class SQLiteReviewStore:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,idle REAL NOT NULL,absolute REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews(owner TEXT NOT NULL,id TEXT NOT NULL,body TEXT NOT NULL,payload BLOB,
                    reserved REAL NOT NULL,lease TEXT,PRIMARY KEY(owner,id),FOREIGN KEY(owner) REFERENCES sessions(token_hash) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS work_leases(token TEXT PRIMARY KEY,expires REAL NOT NULL);
            ''')
            if 'lease' not in {row[1] for row in db.execute('PRAGMA table_info(reviews)')}:
                db.execute('ALTER TABLE reviews ADD COLUMN lease TEXT')
        self.workers = SharedCapacity(self)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA secure_delete=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _prune(self, db):
        db.execute('DELETE FROM sessions WHERE idle<=? OR absolute<=?', (self.clock(), self.clock()))
        # A crashed worker must not leave a request ID permanently processing.
        db.execute("""DELETE FROM reviews WHERE payload IS NULL AND reserved < ?
                   AND (lease IS NULL OR NOT EXISTS(SELECT 1 FROM work_leases WHERE token=reviews.lease AND expires>?))""",
                   (self.clock() - max(settings.REQUEST_TIMEOUT_SECONDS, settings.AI_TIMEOUT_SECONDS) - 120, time.time()))

    def prune(self):
        with self.transaction() as db:
            self._prune(db)

    def _session(self, db, token, touch=False):
        key = hashlib.sha256((token or '').encode()).hexdigest()
        row = db.execute('SELECT * FROM sessions WHERE token_hash=?', (key,)).fetchone()
        if not row or self.clock() >= min(row['idle'], row['absolute']):
            raise HTTPException(401, 'Review session expired or was ended. Start a new session.')
        session = dict(row)
        if touch:
            session['idle'] = min(self.clock() + settings.SESSION_IDLE_SECONDS, row['absolute'])
            db.execute('UPDATE sessions SET idle=? WHERE token_hash=?', (session['idle'], key))
        return key, session

    def _info(self, session):
        return {'expires_in_seconds': max(0, min(session['idle'], session['absolute']) - self.clock()),
                'absolute_remaining_seconds': max(0, session['absolute'] - self.clock()),
                'idle_timeout_seconds': settings.SESSION_IDLE_SECONDS,
                'retention': 'shared local SQLite; retained across restarts until session end or expiry'}

    def create(self):
        with self.transaction() as db:
            self._prune(db)
            if db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] >= settings.MAX_SESSIONS:
                raise HTTPException(429, 'Session capacity reached')
            token = secrets.token_urlsafe(32)
            session = {'idle': self.clock() + min(settings.SESSION_IDLE_SECONDS, settings.SESSION_MAX_SECONDS),
                       'absolute': self.clock() + settings.SESSION_MAX_SECONDS}
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), session['idle'], session['absolute']))
            return {'token': token, **self._info(session)}

    def info(self, token, touch=False):
        with self.transaction() as db:
            _, session = self._session(db, token, touch)
            return self._info(session)

    def end(self, token):
        with self.transaction() as db:
            key, _ = self._session(db, token)
            db.execute('DELETE FROM sessions WHERE token_hash=?', (key,))

    def _record(self, db, owner, review_id, include_result=True):
        row = db.execute('SELECT body,payload FROM reviews WHERE owner=? AND id=?', (owner, review_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Review not found in this session')
        record = json.loads(row['body'])
        if include_result and row['payload'] is not None:
            record['result'] = json.loads(row['payload'])
        return record

    def _public(self, record):
        return {key: value for key, value in record.items() if key != 'request_digest'}

    def reserve(self, token, request):
        digest = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self.transaction() as db:
            self._prune(db)
            owner, _ = self._session(db, token, True)
            row = db.execute('SELECT id FROM reviews WHERE owner=? AND id=?', (owner, request.request_id)).fetchone()
            if row:
                record = self._record(db, owner, request.request_id)
                if record['request_digest'] != digest:
                    raise HTTPException(409, 'Request ID is already bound to different input')
                if record['status'] == 'processing':
                    raise HTTPException(409, 'This analysis is still processing')
                return self._public(record)
            if db.execute('SELECT COUNT(*) FROM reviews WHERE owner=?', (owner,)).fetchone()[0] >= settings.MAX_REVIEWS_PER_SESSION:
                raise HTTPException(429, 'Review limit reached')
            body = {'id': request.request_id, 'kind': request.kind, 'request_digest': digest,
                    'status': 'processing', 'revision': 0, 'created_at': stamp(), 'audit': []}
            lease = getattr(self.workers.local, 'lease', None)
            db.execute('INSERT INTO reviews(owner,id,body,payload,reserved,lease) VALUES(?,?,?,NULL,?,?)',
                       (owner, request.request_id, json.dumps(body), self.clock(), lease[0] if lease else None))

    def abandon(self, token, review_id):
        with self.transaction() as db:
            owner = hashlib.sha256((token or '').encode()).hexdigest()
            db.execute('DELETE FROM reviews WHERE owner=? AND id=? AND payload IS NULL', (owner, review_id))

    def finish(self, token, review_id, result, elapsed):
        payload = json.dumps(result, sort_keys=True, ensure_ascii=False).encode()
        with self.transaction() as db:
            self._prune(db)
            owner, _ = self._session(db, token)
            record = self._record(db, owner, review_id, False)
            if record['status'] != 'processing':
                raise HTTPException(409, 'Review is no longer processing')
            used = db.execute('SELECT COALESCE(SUM(length(payload)),0) FROM reviews').fetchone()[0]
            if used + len(payload) > settings.MAX_REVIEW_STORAGE_BYTES:
                raise HTTPException(413, 'Review storage limit reached')
            record.update(result_digest=hashlib.sha256(payload).hexdigest(), status='pending', elapsed_seconds=round(elapsed, 3))
            record['audit'].append({'action': 'submitted', 'at': stamp(), 'note': '', 'result_digest': record['result_digest']})
            db.execute('UPDATE reviews SET body=?,payload=? WHERE owner=? AND id=?', (json.dumps(record), payload, owner, review_id))
            return {**self._public(record), 'result': result}

    def list(self, token):
        with self.transaction() as db:
            owner, _ = self._session(db, token)
            return [self._public(json.loads(row[0])) for row in db.execute('SELECT body FROM reviews WHERE owner=? ORDER BY reserved,id', (owner,))]

    def get(self, token, review_id, export=False):
        with self.transaction() as db:
            owner, _ = self._session(db, token, True)
            record = self._record(db, owner, review_id)
            if export and record['status'] != 'approved':
                raise HTTPException(409, 'Approve this result before exporting it')
            return self._public(record)

    def decide(self, token, review_id, decision):
        with self.transaction() as db:
            owner, _ = self._session(db, token, True)
            record = self._record(db, owner, review_id, False)
            if decision.result_digest != record.get('result_digest'):
                raise HTTPException(409, 'The result changed; reload before deciding')
            if record['status'] == decision.action and record['audit'][-1]['note'] == decision.note:
                return self._public(self._record(db, owner, review_id))
            if record['status'] != 'pending' or decision.revision != record['revision']:
                raise HTTPException(409, 'This review has already been decided or changed')
            record['status'] = decision.action
            record['revision'] += 1
            record['audit'].append({'action': decision.action, 'at': stamp(), 'note': decision.note, 'result_digest': record['result_digest']})
            db.execute('UPDATE reviews SET body=? WHERE owner=? AND id=?', (json.dumps(record), owner, review_id))
            return self._public(self._record(db, owner, review_id))

    def close(self):
        self.prune()  # Stopping one worker must never erase another worker's sessions.
