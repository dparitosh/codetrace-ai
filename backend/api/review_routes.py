"""Bounded review sessions, using memory or an administrator-selected SQLite store.

Memory mode requires one worker and clears on restart. SQLite mode persists until
expiry/end and supports workers sharing local disk. Tokens are not authentication.
"""
import hashlib
import json
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Literal, Optional, Union

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from api.graph_routes import LocalGraphRequest, GitLabGraphRequest, build_graph_from_files, generate_gitlab_graph, analyze_local_sources
from api.quality_routes import assess_local_quality
from api.security_routes import scan_local_source
from api.trace_routes import TraceManifest, TraceRequest, build_trace
from core.config import settings

review_router = APIRouter(tags=['Review and Approval'])


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class ReviewRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    kind: Literal['analysis', 'graph', 'quality', 'security']
    source: Union[LocalGraphRequest, GitLabGraphRequest]
    manifest: Optional[TraceManifest] = None

    @model_validator(mode='after')
    def supported_source(self):
        if self.kind != 'graph' and (not isinstance(self.source, LocalGraphRequest) or self.manifest is not None):
            raise ValueError('Only graph reviews support GitLab sources or lifecycle manifests')
        return self


class Decision(BaseModel):
    action: Literal['approved', 'rejected']
    note: str = Field(default='', max_length=2000)
    revision: int = Field(ge=0)
    result_digest: str = Field(min_length=64, max_length=64)


class ReviewStore:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.sessions = {}
        self.bytes = 0
        self.workers = threading.BoundedSemaphore(settings.MAX_CONCURRENT_ANALYSES)

    def _drop(self, key):
        session = self.sessions.pop(key)
        self.bytes -= sum(len(record.get('payload', b'')) for record in session['reviews'].values())

    def prune(self):
        with self.lock:
            now = self.clock()
            for key, session in list(self.sessions.items()):
                if now >= min(session['idle'], session['absolute']):
                    self._drop(key)

    def _session(self, token, touch=True):
        self.prune()
        key = hashlib.sha256((token or '').encode()).hexdigest()
        session = self.sessions.get(key)
        if session is None:
            raise HTTPException(401, 'Review session expired or was ended. Start a new session and run the analysis again.')
        if touch:
            session['idle'] = min(self.clock() + settings.SESSION_IDLE_SECONDS, session['absolute'])
        return key, session

    def _info(self, session):
        return {'expires_in_seconds': max(0, min(session['idle'], session['absolute']) - self.clock()),
                'absolute_remaining_seconds': max(0, session['absolute'] - self.clock()),
                'idle_timeout_seconds': settings.SESSION_IDLE_SECONDS,
                'retention': 'session memory only; cleared on expiration, end, or backend restart'}

    def create(self):
        with self.lock:
            self.prune()
            if len(self.sessions) >= settings.MAX_SESSIONS:
                raise HTTPException(429, 'Session capacity reached. End an existing session or wait for expiry.')
            token = secrets.token_urlsafe(32)
            now = self.clock()
            session = {'idle': now + settings.SESSION_IDLE_SECONDS, 'absolute': now + settings.SESSION_MAX_SECONDS, 'reviews': {}}
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = session
            return {'token': token, **self._info(session)}

    def info(self, token, touch=False):
        with self.lock:
            _, session = self._session(token, touch)
            return self._info(session)

    def end(self, token):
        with self.lock:
            key, _ = self._session(token, False)
            self._drop(key)

    def _view(self, record, include_result=True):
        public = {key: value for key, value in record.items() if key not in {'payload', 'request_digest'}}
        if include_result and 'payload' in record:
            public['result'] = json.loads(record['payload'])
        return public

    def reserve(self, token, request):
        digest = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self.lock:
            _, session = self._session(token)
            existing = session['reviews'].get(request.request_id)
            if existing:
                if existing['request_digest'] != digest:
                    raise HTTPException(409, 'Request ID is already bound to different input.')
                if existing['status'] == 'processing':
                    raise HTTPException(409, 'This analysis is still processing. Refresh review history shortly.')
                return self._view(existing)
            if len(session['reviews']) >= settings.MAX_REVIEWS_PER_SESSION:
                raise HTTPException(429, 'Review limit reached. Export approved results and start a new session.')
            session['reviews'][request.request_id] = {'id': request.request_id, 'kind': request.kind,
                'request_digest': digest, 'status': 'processing', 'revision': 0, 'created_at': timestamp(), 'audit': []}
            return None

    def abandon(self, token, review_id):
        with self.lock:
            try:
                _, session = self._session(token, False)
            except HTTPException:
                return
            record = session['reviews'].get(review_id)
            if record and record['status'] == 'processing':
                del session['reviews'][review_id]

    def finish(self, token, review_id, result, elapsed):
        payload = json.dumps(result, sort_keys=True, ensure_ascii=False).encode('utf-8')
        with self.lock:
            _, session = self._session(token, False)  # Long-running work never renews an expired session.
            if self.bytes + len(payload) > settings.MAX_REVIEW_STORAGE_BYTES:
                raise HTTPException(413, 'Review storage limit reached. Analyze a smaller selection or end another session.')
            record = session['reviews'][review_id]
            record.update(payload=payload, result_digest=hashlib.sha256(payload).hexdigest(), status='pending', elapsed_seconds=round(elapsed, 3))
            record['audit'].append({'action': 'submitted', 'at': timestamp(), 'note': '', 'result_digest': record['result_digest']})
            self.bytes += len(payload)
            return self._view(record)

    def list(self, token):
        with self.lock:
            _, session = self._session(token, False)
            return [self._view(record, False) for record in session['reviews'].values()]

    def get(self, token, review_id, export=False):
        with self.lock:
            _, session = self._session(token)
            record = session['reviews'].get(review_id)
            if not record:
                raise HTTPException(404, 'Review not found in this session')
            if export and record['status'] != 'approved':
                raise HTTPException(409, 'Approve this result before exporting it.')
            return self._view(record)

    def decide(self, token, review_id, decision):
        with self.lock:
            _, session = self._session(token)
            record = session['reviews'].get(review_id)
            if not record:
                raise HTTPException(404, 'Review not found in this session')
            if decision.result_digest != record.get('result_digest'):
                raise HTTPException(409, 'The result changed; reload it before deciding.')
            if record['status'] == decision.action and record['audit'][-1]['note'] == decision.note:
                return self._view(record)  # Retrying a lost response must not append another audit event.
            if record['status'] != 'pending' or decision.revision != record['revision']:
                raise HTTPException(409, 'This review has already been decided or changed. Reload it.')
            record['status'] = decision.action
            record['revision'] += 1
            record['audit'].append({'action': decision.action, 'at': timestamp(), 'note': decision.note,
                                    'result_digest': record['result_digest']})
            return self._view(record)


if settings.SESSION_STORE == 'sqlite':
    from services.shared_reviews import SQLiteReviewStore
    store = SQLiteReviewStore(settings.SESSION_DB_PATH)
else:
    store = ReviewStore()


@review_router.post('/session')
def create_session():
    return store.create()


@review_router.get('/session')
def session_info(x_codetrace_session: Optional[str] = Header(default=None)):
    return store.info(x_codetrace_session)


@review_router.post('/session/keepalive')
def keep_session(x_codetrace_session: Optional[str] = Header(default=None)):
    return store.info(x_codetrace_session, touch=True)


@review_router.delete('/session')
def end_session(x_codetrace_session: Optional[str] = Header(default=None)):
    store.end(x_codetrace_session)
    return {'ended': True}


@review_router.get('/reviews')
def list_reviews(x_codetrace_session: Optional[str] = Header(default=None)):
    return store.list(x_codetrace_session)


@review_router.post('/reviews')
def submit_review(request: ReviewRequest, x_codetrace_session: Optional[str] = Header(default=None)):
    # Fail fast rather than growing an unbounded queue of analysis requests.
    if not store.workers.acquire(blocking=False):
        raise HTTPException(429, 'Analysis capacity is busy. Retry shortly.')
    reserved = False
    try:
        existing = store.reserve(x_codetrace_session, request)
        if existing is not None:
            return existing
        reserved = True
        started = time.monotonic()
        if request.kind == 'graph':
            if request.manifest is not None:
                result = build_trace(TraceRequest(source=request.source, manifest=request.manifest))
            elif isinstance(request.source, LocalGraphRequest):
                result = build_graph_from_files(request.source)
            else:
                result = generate_gitlab_graph(request.source)
        elif request.kind == 'analysis':
            result = analyze_local_sources(request.source)
        elif request.kind == 'quality':
            result = assess_local_quality(request.source).model_dump()
        else:
            result = scan_local_source(request.source).model_dump()
        elapsed = time.monotonic() - started
        if elapsed >= settings.REQUEST_TIMEOUT_SECONDS:
            raise HTTPException(504, 'Analysis exceeded the review deadline. Retry a smaller source selection.')
        return store.finish(x_codetrace_session, request.request_id, result, elapsed)
    except Exception:
        if reserved:
            store.abandon(x_codetrace_session, request.request_id)
        raise
    finally:
        store.workers.release()


@review_router.get('/reviews/{review_id}')
def get_review(review_id: str, x_codetrace_session: Optional[str] = Header(default=None)):
    return store.get(x_codetrace_session, review_id)


@review_router.post('/reviews/{review_id}/decision')
def decide_review(review_id: str, decision: Decision, x_codetrace_session: Optional[str] = Header(default=None)):
    return store.decide(x_codetrace_session, review_id, decision)


@review_router.get('/reviews/{review_id}/export')
def export_review(review_id: str, x_codetrace_session: Optional[str] = Header(default=None)):
    return JSONResponse(store.get(x_codetrace_session, review_id, export=True),
                        headers={'Content-Disposition': 'attachment; filename="codetrace-approved-review.json"', 'Cache-Control': 'no-store'})
