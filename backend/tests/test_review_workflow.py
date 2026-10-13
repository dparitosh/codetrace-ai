import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import api.review_routes as reviews
from core.config import settings
from main import app


@pytest.fixture
def workflow(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(settings, 'SESSION_IDLE_SECONDS', 10)
    monkeypatch.setattr(settings, 'SESSION_MAX_SECONDS', 25)
    store = reviews.ReviewStore(clock=lambda: clock[0])
    monkeypatch.setattr(reviews, 'store', store)
    client = TestClient(app)
    token = client.post('/api/v1/review/session').json()['token']
    return client, {'X-CodeTrace-Session': token}, clock, store


def submit(client, headers, request_id='first', **extra):
    return client.post('/api/v1/review/reviews', headers=headers, json={
        'request_id': request_id, 'kind': 'analysis',
        'source': {'files': [{'path': 'a.py', 'content': 'def run(): pass'}]}, **extra,
    })


def decision(record, action='approved', **extra):
    return {'action': action, 'note': 'Checked source', 'revision': record['revision'],
            'result_digest': record['result_digest'], **extra}


def test_pending_cannot_export_then_approval_is_audited_and_idempotent(workflow):
    c, h, _, store = workflow
    record = submit(c, h).json()
    assert record['status'] == 'pending'
    assert 'content' not in str(store.sessions)
    assert c.get('/api/v1/review/reviews/first/export', headers=h).status_code == 409
    data = decision(record)
    approved = c.post('/api/v1/review/reviews/first/decision', headers=h, json=data)
    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'
    assert [event['action'] for event in approved.json()['audit']] == ['submitted', 'approved']
    assert c.post('/api/v1/review/reviews/first/decision', headers=h, json=data).json() == approved.json()
    exported = c.get('/api/v1/review/reviews/first/export', headers=h)
    assert exported.status_code == 200
    assert exported.headers['cache-control'] == 'no-store'
    assert exported.json()['result'] == record['result']


def test_wrong_digest_stale_revision_and_rejection_cannot_approve(workflow):
    c, h, _, _ = workflow
    record = submit(c, h).json()
    path = '/api/v1/review/reviews/first/decision'
    assert c.post(path, headers=h, json=decision(record, result_digest='0' * 64)).status_code == 409
    assert c.post(path, headers=h, json=decision(record, revision=99)).status_code == 409
    assert c.post(path, headers=h, json=decision(record, 'rejected')).status_code == 200
    assert c.post(path, headers=h, json=decision(record)).status_code == 409
    assert c.get('/api/v1/review/reviews/first/export', headers=h).status_code == 409


def test_sessions_are_isolated_and_ended_sessions_release_memory(workflow):
    c, h, _, store = workflow
    submit(c, h)
    other = {'X-CodeTrace-Session': c.post('/api/v1/review/session').json()['token']}
    assert c.get('/api/v1/review/reviews/first', headers=other).status_code == 404
    assert c.get('/api/v1/review/reviews/first').status_code == 401
    assert store.bytes > 0
    assert c.delete('/api/v1/review/session', headers=h).status_code == 200
    assert store.bytes == 0
    assert c.get('/api/v1/review/session', headers=h).status_code == 401


def test_polling_does_not_extend_idle_timeout(workflow):
    c, h, clock, store = workflow
    submit(c, h)
    clock[0] = 109
    assert c.get('/api/v1/review/session', headers=h).json()['expires_in_seconds'] == 1
    c.get('/api/v1/review/reviews', headers=h)
    clock[0] = 110
    assert c.get('/api/v1/review/session', headers=h).status_code == 401
    assert store.bytes == 0


def test_keepalive_cannot_extend_absolute_deadline(workflow):
    c, h, clock, _ = workflow
    for now in (109, 118, 124):
        clock[0] = now
        result = c.post('/api/v1/review/session/keepalive', headers=h)
        assert result.status_code == 200
        assert result.json()['expires_in_seconds'] <= 125 - now
    clock[0] = 125
    assert c.post('/api/v1/review/session/keepalive', headers=h).status_code == 401


def test_request_retries_reuse_exact_result_and_reject_changed_input(workflow):
    c, h, _, _ = workflow
    first = submit(c, h).json()
    assert submit(c, h).json() == first
    assert submit(c, h, kind='quality').status_code == 409
    assert len(c.get('/api/v1/review/reviews', headers=h).json()) == 1


def test_storage_and_review_limits_fail_without_leaking_reservations(workflow, monkeypatch):
    c, h, _, store = workflow
    monkeypatch.setattr(settings, 'MAX_REVIEW_STORAGE_BYTES', 1)
    assert submit(c, h).status_code == 413
    assert store.bytes == 0
    assert c.get('/api/v1/review/reviews', headers=h).json() == []
    monkeypatch.setattr(settings, 'MAX_REVIEW_STORAGE_BYTES', 1000000)
    monkeypatch.setattr(settings, 'MAX_REVIEWS_PER_SESSION', 1)
    assert submit(c, h).status_code == 200
    assert submit(c, h, 'second').status_code == 429


def test_busy_analysis_fails_fast_and_capacity_recovers(workflow):
    c, h, _, store = workflow
    for _ in range(settings.MAX_CONCURRENT_ANALYSES):
        store.workers.acquire()
    try:
        assert submit(c, h).status_code == 429
        assert c.get('/api/v1/review/reviews', headers=h).json() == []
    finally:
        for _ in range(settings.MAX_CONCURRENT_ANALYSES):
            store.workers.release()
    assert submit(c, h).status_code == 200


def test_expiry_during_analysis_discards_result(workflow, monkeypatch):
    c, h, clock, store = workflow
    def slow(_):
        clock[0] += 11
        return {'result': 'late'}
    monkeypatch.setattr(reviews, 'analyze_local_sources', slow)
    assert submit(c, h).status_code == 401
    assert store.bytes == 0


def test_simultaneous_opposing_decisions_have_one_winner(workflow):
    c, h, _, store = workflow
    record = submit(c, h).json()
    barrier = threading.Barrier(2)
    def decide(action):
        barrier.wait()
        try:
            return store.decide(h['X-CodeTrace-Session'], 'first', reviews.Decision(**decision(record, action)))['status']
        except reviews.HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, ['approved', 'rejected']))
    assert outcomes.count(409) == 1
    assert len(store.get(h['X-CodeTrace-Session'], 'first')['audit']) == 2


@pytest.mark.parametrize('kind', ['analysis', 'quality', 'security', 'graph'])
def test_all_ui_analysis_kinds_support_review(workflow, kind):
    c, h, _, _ = workflow
    assert submit(c, h, kind=kind).status_code == 200
