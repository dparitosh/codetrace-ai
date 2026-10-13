import pytest
from fastapi.testclient import TestClient
from main import app
from core.config import settings, Settings, PROJECT_ROOT

client = TestClient(app)


def test_javascript_symbols_reach_agent_context():
    response = client.post('/api/v1/agent/context', json={
        'query': 'hello', 'files': [{'path': 'hello.js', 'content': 'export function hello() { return 1; }'}],
    })
    assert response.status_code == 200
    assert response.json()['symbols'][0]['name'] == 'hello'
    assert response.json()['symbols'][0]['kind'] == 'symbol'


@pytest.mark.parametrize('route', ['graph/local', 'graph/local/analyze', 'quality/local', 'security/local', 'agent/context'])
def test_oversized_file_is_reported_not_silently_skipped(route, monkeypatch):
    monkeypatch.setattr(settings, 'MAX_SOURCE_FILE_BYTES', 20)
    response = client.post('/api/v1/' + route, json={'query': 'x', 'files': [{'path': 'large.py', 'content': '#' * 21}]})
    assert response.status_code == 413
    assert 'large.py' in response.json()['error']


def test_security_count_reports_truncation(monkeypatch):
    monkeypatch.setattr(settings, 'SECURITY_MAX_FINDINGS', 2)
    data = client.post('/api/v1/security/local', json={'files': [{'path': 'a.py', 'content': 'eval(x)\n' * 3}]}).json()
    assert data['total_findings'] == 3
    assert len(data['findings']) == 2
    assert data['truncated'] is True


def test_public_configuration_uses_live_settings_without_secrets(monkeypatch):
    monkeypatch.setattr(settings, 'MAX_LOCAL_FILES', 7)
    monkeypatch.setattr(settings, 'SOURCE_EXTENSIONS', ['py', '.TS'])
    data = client.get('/api/v1/graph/configuration').json()
    assert data['max_files'] == 7
    assert data['extensions'] == ['.py', '.ts']
    assert 'node_modules' in data['excludes']
    assert 'GITLAB_ALLOWED_HOSTS' not in data


def test_settings_precedence_and_cwd_independence(tmp_path, monkeypatch):
    legacy = tmp_path / '.env'
    local = tmp_path / '.env.local'
    legacy.write_text('BACKEND_PORT=8100\nFRONTEND_PORT=3100\n')
    local.write_text('BACKEND_PORT=8200\nFRONTEND_PORT=3200\n')
    monkeypatch.chdir(tmp_path)
    parsed = Settings(_env_file=(legacy, local))
    assert parsed.PORT == 8200
    assert 'http://127.0.0.1:3200' in parsed.CORS_ORIGINS
    monkeypatch.setenv('BACKEND_PORT', '8300')
    assert Settings(_env_file=(legacy, local)).PORT == 8300
    assert Settings().LOG_DIR == PROJECT_ROOT / 'logs'
    monkeypatch.delenv('BACKEND_PORT')
    monkeypatch.setenv('PORT', '8400')
    assert Settings(_env_file=(legacy, local)).PORT == 8400


@pytest.mark.parametrize('values', [{'BACKEND_PORT': 0}, {'FRONTEND_PORT': 99999},
                                  {'BACKEND_PORT': 3001, 'FRONTEND_PORT': 3001},
                                  {'MAX_SOURCE_FILE_BYTES': 100, 'MAX_LOCAL_PAYLOAD_BYTES': 10}])
def test_invalid_configuration_fails_early(values):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize('setting', ['MAX_GRAPH_NODES', 'MAX_GRAPH_EDGES'])
def test_graph_expansion_budget_rejects_small_but_dense_source(setting, monkeypatch):
    monkeypatch.setattr(settings, setting, 3)
    response = client.post('/api/v1/graph/local', json={'files': [{'path': 'a.py', 'content': 'def a(x): return b(x)\ndef b(y): return y'}]})
    assert response.status_code == 413


def test_empty_supported_selection_is_not_reported_as_success():
    response = client.post('/api/v1/graph/local', json={'files': [{'path': 'a.png', 'content': 'not source'}]})
    assert response.status_code == 422


def test_deep_source_paths_do_not_overflow_trace_package_recursion():
    path = '/'.join(['a'] * 1000) + '/b.py'
    response = client.post('/api/v1/trace/materialize', json={
        'source': {'files': [{'path': path, 'content': ''}]},
        'manifest': {'repository': {'uri': 'urn:example:repo', 'label': 'deep'}},
    })
    assert response.status_code == 200
    assert len(response.json()['nodes']) > 1000


def test_manifest_byte_limit_is_enforced_by_api(monkeypatch):
    monkeypatch.setattr(settings, 'MAX_TRACE_MANIFEST_BYTES', 50)
    response = client.post('/api/v1/trace/materialize', json={
        'source': {'files': [{'path': 'a.py', 'content': ''}]},
        'manifest': {'repository': {'uri': 'urn:example:repo', 'label': 'large'}},
    })
    assert response.status_code == 422


def test_review_session_rejects_untrusted_browser_origin():
    assert client.post('/api/v1/review/session', headers={'Origin': 'https://untrusted.example'}).status_code == 403
