"""Confirmed full-stack defects, exercised offline with isolated stores."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from api import review_routes, workspace_routes
from api.graph_routes import LocalGraphRequest, build_graph_from_files, build_graph_from_directory
from core.config import settings
from core.connection_models import connection_url
from graph.traceability import materialize
from main import app
from services.agent_workspace import GraphSearch
from services.analysis_capacity import analysis_capacity
from services.companion_service import context_evidence
from services.oslc_store import OSLCStore
from services.shared_reviews import SQLiteReviewStore


@pytest.mark.parametrize('content', ['[]', 'null', 'true', '0', '{}', '{"ready":false}'])
def test_readiness_rejects_non_ready_json_without_server_errors(monkeypatch, content):
    store = review_routes.ReviewStore()
    monkeypatch.setattr(review_routes, 'store', store)
    fake = SimpleNamespace(models=lambda: [], chat=lambda *args: {'content': content},
                           connection=SimpleNamespace(embeddings_enabled=False, discovery_enabled=True))
    monkeypatch.setattr(workspace_routes, 'OllamaREST', lambda *args: fake)
    client = TestClient(app)
    token = client.post('/api/v1/review/session').json()['token']
    response = client.post('/api/v1/workspace/ai/test', headers={'X-CodeTrace-Session': token})
    assert response.status_code == 502
    assert store.workers.acquire(blocking=False)
    store.workers.release()


@pytest.mark.parametrize('kind,domain', [('requirement', 'RM'), ('requirement_collection', 'RM'),
    ('test_script', 'QM'), ('test_result', 'QM'), ('architecture', 'AM'), ('configuration', 'CONFIG')])
def test_materialized_and_legacy_graph_search_infer_lifecycle_domains(kind, domain):
    resource = {'id': 'urn:audit:resource', 'label': 'Payment evidence', 'type': kind, 'properties': {}}
    legacy = {'nodes': [resource], 'edges': [], 'metadata': {}}
    result = GraphSearch(legacy).search('Payment', domain=domain, semantic=False)
    assert len(result['results']) == 1
    assert result['results'][0]['domain'] == domain
    assert context_evidence(legacy, 'Payment')[0][0]['domain'] == domain
    code = build_graph_from_files(LocalGraphRequest(files=[{'path': 'app.py', 'content': 'x = 1'}]))
    combined = materialize(code, {'repository': {'uri': 'urn:audit:repo', 'label': 'Repo'},
        'resources': [{'uri': resource['id'], 'label': resource['label'], 'kind': kind}]}, 'digest')
    assert next(node for node in combined['nodes'] if node['id'] == resource['id'])['properties']['domain'] == domain


def test_explicit_provider_domain_is_preserved():
    graph = {'nodes': [{'id': 'a', 'label': 'Payment', 'type': 'test', 'properties': {'domain': 'AM'}}], 'edges': [], 'metadata': {}}
    assert GraphSearch(graph).search('Payment', domain='AM', semantic=False)['results']
    assert not GraphSearch(graph).search('Payment', domain='QM', semantic=False)['results']


def test_bom_python_keeps_typed_graph_and_raw_source_identity(tmp_path):
    source = 'class Payment:\n    def charge(self):\n        return 1\n'
    plain = build_graph_from_files(LocalGraphRequest(files=[{'path': 'payment.py', 'content': source}]))
    bom = build_graph_from_files(LocalGraphRequest(files=[{'path': 'payment.py', 'content': '\ufeff' + source}]))
    assert plain['nodes'] == bom['nodes']
    assert plain['edges'] == bom['edges']
    assert plain['metadata']['source_digest'] != bom['metadata']['source_digest']
    (tmp_path / 'payment.py').write_bytes(b'\xef\xbb\xbf' + source.encode())
    local = build_graph_from_directory(tmp_path, 'audit')
    assert local['nodes'] == bom['nodes']
    assert local['edges'] == bom['edges']


@pytest.mark.parametrize('value', ['https://example.org:70000', 'https://example.org:0',
                                   'https://example.org:not-a-port', 'https://[::1]:65536'])
def test_invalid_connection_ports_are_rejected_without_echoing_values(value):
    with pytest.raises(ValueError) as error:
        connection_url(value)
    assert value not in str(error.value)


@pytest.mark.parametrize('value', ['https://example.org', 'https://example.org:443', 'http://127.0.0.1:8009', 'http://[::1]:8009'])
def test_valid_connection_ports_remain_supported(value):
    assert connection_url(value) == value


def test_sqlite_yield_dependency_releases_lease_across_threads(tmp_path, monkeypatch):
    store = SQLiteReviewStore(tmp_path / 'reviews.sqlite')
    monkeypatch.setattr(review_routes, 'store', store)
    entered, cleanup = threading.Event(), threading.Event()
    manager = analysis_capacity()
    leases = []

    def enter_on_worker():
        manager.__enter__()
        leases.append(store.workers.local.lease)
        entered.set()
        try:
            assert cleanup.wait(10)
        finally:
            if not leases[0][1].is_set():
                store.workers.release()  # Stop the test's lease even on a failed assertion.

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(enter_on_worker)
        try:
            assert entered.wait(10)
            pool.submit(manager.__exit__, None, None, None).result(timeout=10)
            assert leases[0][1].is_set()
            assert not leases[0][2].is_alive()
            with store.transaction() as db:
                assert db.execute('SELECT COUNT(*) FROM work_leases').fetchone()[0] == 0
        finally:
            cleanup.set()
            first.result(timeout=10)


def test_sqlite_direct_api_requests_release_all_leases(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'MAX_CONCURRENT_ANALYSES', 8)
    store = SQLiteReviewStore(tmp_path / 'api.sqlite')
    monkeypatch.setattr(review_routes, 'store', store)

    def request(_):
        with TestClient(app) as client:
            return client.post('/api/v1/graph/local', json={'files': [{'path': 'app.py', 'content': 'def work(): pass'}]}).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(request, range(8))) == [200] * 8
    with store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM work_leases').fetchone()[0] == 0


@pytest.mark.parametrize('adapter,module', [(SQLiteReviewStore, 'services.shared_reviews'), (OSLCStore, 'services.oslc_store')])
@pytest.mark.parametrize('phase', ['PRAGMA', 'BEGIN', 'body'])
def test_sqlite_transaction_always_closes_and_preserves_failure(tmp_path, adapter, module, phase):
    target = object.__new__(adapter)
    target.path = tmp_path / 'unused.sqlite'
    db = MagicMock()

    def execute(sql, *args):
        if sql.startswith(phase):
            raise sqlite3.OperationalError('synthetic contention')
        return MagicMock()

    db.execute.side_effect = execute
    with patch(module + '.sqlite3.connect', return_value=db), pytest.raises(sqlite3.OperationalError, match='synthetic contention'):
        with target.transaction():
            raise sqlite3.OperationalError('synthetic contention')
    db.close.assert_called_once()
    assert db.rollback.call_count == (1 if phase == 'body' else 0)


def test_core_cli_without_subcommand_displays_help():
    result = subprocess.run([sys.executable, '-m', 'codegraph_core'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert 'usage: codegraph' in result.stdout
    assert 'Traceback' not in result.stderr


def test_source_review_search_agent_decision_export_workflow(monkeypatch):
    """Real ASGI requests and storage; model execution is explicitly disabled."""
    monkeypatch.setattr(review_routes, 'store', review_routes.ReviewStore())
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'disabled')
    source = {'files': [{'path': 'payment.py', 'content': 'def charge():\n    return 1\n'}]}
    raw = build_graph_from_files(LocalGraphRequest(**source))
    function = next(node['id'] for node in raw['nodes'] if node['type'] == 'function')
    manifest = {'repository': {'uri': 'urn:audit:payment', 'label': 'Payment'},
                'resources': [{'uri': 'urn:audit:requirement', 'kind': 'requirement', 'label': 'Payment requirement'}],
                'links': [{'source': {'uri': 'urn:audit:requirement'}, 'predicate': 'http://open-services.net/ns/rm#implementedBy',
                           'target': {'code_id': function}, 'asserted_by': 'urn:audit:fixture'}]}
    with TestClient(app) as client:
        token = client.post('/api/v1/review/session').json()['token']
        headers = {'X-CodeTrace-Session': token}
        submitted = client.post('/api/v1/review/reviews', headers=headers,
            json={'request_id': 'audit-workflow', 'kind': 'graph', 'source': source, 'manifest': manifest})
        assert submitted.status_code == 200
        record = submitted.json()
        assert record['status'] == 'pending'
        assert client.get('/api/v1/review/reviews/audit-workflow/export', headers=headers).status_code == 409
        search = client.post('/api/v1/workspace/search', headers=headers,
            json={'review_id': record['id'], 'query': 'Payment', 'domain': 'RM', 'semantic': False})
        assert search.status_code == 200
        assert search.json()['results'][0]['node_id'] == 'urn:audit:requirement'
        answer = client.post('/api/v1/workspace/agent/run', headers=headers,
            json={'review_id': record['id'], 'question': 'Explain Payment', 'domain': 'RM', 'agent_id': 'trace-explorer'})
        assert answer.status_code == 200
        assert answer.json()['mode'] == 'evidence'
        assert answer.json()['citations'][0]['domain'] == 'RM'
        decision = client.post('/api/v1/review/reviews/audit-workflow/decision', headers=headers,
            json={'action': 'approved', 'note': 'Offline audit fixture', 'revision': record['revision'], 'result_digest': record['result_digest']})
        assert decision.status_code == 200
        exported = client.get('/api/v1/review/reviews/audit-workflow/export', headers=headers)
        assert exported.status_code == 200
        assert exported.json()['result_digest'] == record['result_digest']
        assert exported.json()['result']['source_assessments']['summary']['total_files'] == 1
        assert client.delete('/api/v1/review/session', headers=headers).status_code == 200
        assert client.get('/api/v1/review/reviews/audit-workflow', headers=headers).status_code == 401
