import json
import sqlite3
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import review_routes
from api.review_routes import ReviewStore
from api.workspace_routes import ManagedSync
from core.config import settings
from main import app
from services.ai_connection import AIConnection, OllamaREST, normalize_base
from services.agent_workspace import GraphAgent, GraphSearch, coverage_gaps
from services.shared_reviews import SQLiteReviewStore


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://127.0.0.1:11434')
    monkeypatch.setattr(settings, 'AI_ALLOWED_BASE_URLS', ['https://models.example/ollama'])
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'disabled')


def snapshot():
    return {'nodes': [
        {'id': 'urn:test:rm', 'label': 'Brake safety', 'type': 'requirement', 'properties': {'domain': 'RM', 'description': 'Stop the rotor'}},
        {'id': 'urn:test:fn', 'label': 'apply_brake', 'type': 'function', 'properties': {'domain': 'CODE', 'path': 'brake.py'}},
        {'id': 'urn:test:qm', 'label': 'Brake verification', 'type': 'test', 'properties': {'domain': 'QM'}},
        {'id': 'urn:test:deleted', 'label': 'Brake obsolete', 'type': 'requirement', 'properties': {'domain': 'TRS', 'deleted': True}},
    ], 'edges': [
        {'source': 'urn:test:rm', 'target': 'urn:test:fn', 'type': 'http://open-services.net/ns/rm#implementedBy', 'properties': {'origin': 'lifecycle_assertion'}},
        {'source': 'urn:test:qm', 'target': 'urn:test:rm', 'type': 'http://open-services.net/ns/qm#validatesRequirement', 'properties': {'origin': 'lifecycle_assertion'}},
    ], 'metadata': {'snapshot_id': 'agent-fixture', 'coverage': {}}}


@pytest.fixture(params=['memory', 'sqlite'])
def session_store(request, tmp_path, monkeypatch):
    store = ReviewStore() if request.param == 'memory' else SQLiteReviewStore(tmp_path / 'reviews.sqlite')
    monkeypatch.setattr(review_routes, 'store', store)
    token = store.create()['token']
    store.reserve(token, ManagedSync(request_id='graph', source_id='workspace'))
    store.finish(token, 'graph', snapshot(), 0)
    return store, token, TestClient(app)


def profile(**kwargs):
    return AIConnection(base_url='http://127.0.0.1:11434', model='chat-fixture', embedding_model='nomic-embed-text', **kwargs)


def test_normalization_and_origin_policy():
    assert normalize_base('https://models.example/ollama/api/chat') == 'https://models.example/ollama'
    assert AIConnection(base_url='https://models.example/ollama/api/embed').base_url == 'https://models.example/ollama'
    for url in ['https://unregistered.example', 'http://127.0.0.1:9999', 'http://user:pass@127.0.0.1:11434',
                'http://127.0.0.1:11434/api/chat?key=x', 'http://127.0.0.1:11434/%2e%2e', 'http://127.0.0.1:bad']:
        with pytest.raises(ValueError): AIConnection(base_url=url)


def test_config_keys_are_owned_masked_and_removable(session_store):
    store, token, client = session_store
    headers = {'X-CodeTrace-Session': token}
    body = profile(api_key='fixture-super-private-key').private()
    assert client.put('/api/v1/workspace/ai/config', json=body).status_code == 401
    saved = client.put('/api/v1/workspace/ai/config', headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()['key_configured'] and 'fixture-super-private-key' not in saved.text
    invalid = client.put('/api/v1/workspace/ai/config', headers=headers, json={**body, 'api_key': 'private-invalid-key\n'})
    assert invalid.status_code == 422 and 'private-invalid-key' not in invalid.text
    invalid_url = client.put('/api/v1/workspace/ai/config', headers=headers, json={**body, 'base_url': 'http://user:private-password@127.0.0.1:11434'})
    assert invalid_url.status_code == 422 and 'private-password' not in invalid_url.text
    public = client.get('/api/v1/workspace/ai/config', headers=headers)
    assert 'api_key' not in public.json() and 'fixture-super-private-key' not in public.text
    other = store.create()['token']
    assert not client.get('/api/v1/workspace/ai/config', headers={'X-CodeTrace-Session': other}).json()['key_configured']
    body['api_key'] = ''
    client.put('/api/v1/workspace/ai/config', headers=headers, json=body)
    assert store.ai_profile(token)['api_key'] == 'fixture-super-private-key'
    body['keep_key'] = False
    client.put('/api/v1/workspace/ai/config', headers=headers, json=body)
    assert store.ai_profile(token)['api_key'] == ''
    assert client.delete('/api/v1/workspace/ai/config', headers=headers).status_code == 200
    assert store.ai_profile(token) is None
    with patch('services.ai_connection.server_secret', return_value='private-central-key\r'):
        invalid_default = client.get('/api/v1/workspace/ai/config', headers=headers)
        assert invalid_default.status_code == 422 and 'private-central-key' not in invalid_default.text


def test_sqlite_profile_encryption_sharing_and_expiry(tmp_path):
    clock = [100.]
    path = tmp_path/'encrypted.sqlite'
    first = SQLiteReviewStore(path, clock=lambda: clock[0]); second = SQLiteReviewStore(path, clock=lambda: clock[0])
    token = first.create()['token']
    first.ai_profile(token, profile(api_key='fixture-key-not-plaintext').private())
    assert second.ai_profile(token)['api_key'] == 'fixture-key-not-plaintext'
    with sqlite3.connect(path) as db:
        encrypted = db.execute('SELECT encrypted FROM session_ai').fetchone()[0]
        assert b'fixture-key-not-plaintext' not in encrypted
    first.end(token)
    with pytest.raises(HTTPException): second.ai_profile(token)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM session_ai').fetchone()[0] == 0


@pytest.mark.parametrize('header,value', [('Authorization','Bearer fixture-key'), ('api-key','fixture-key'), ('Ocp-Apim-Subscription-Key','fixture-key')])
def test_transport_headers_and_native_rest_routes(header, value):
    requests = []
    def reply(request):
        requests.append(request)
        assert request.headers[header] == value
        return httpx.Response(200, json={'models': [{'name': 'model-a'}]})
    factory = httpx.Client
    with patch('services.ai_connection.httpx.Client', side_effect=lambda **kwargs: factory(transport=httpx.MockTransport(reply), **kwargs)):
        assert OllamaREST(profile(api_key='fixture-key', key_header=header)).models() == ['model-a']
    assert str(requests[0].url) == 'http://127.0.0.1:11434/api/tags'


def test_embedding_validation():
    rest = OllamaREST(profile())
    for vectors in [[[1, 2]], [[0, 0], [1, 2]], [[1, float('nan')], [1, 2]], [[1, 2], [1]]]:
        with patch.object(rest, 'request', return_value={'embeddings': vectors}), pytest.raises(ValueError):
            rest.embed(['one','two'])


def test_hybrid_search_and_disclosed_fallback():
    rest = OllamaREST(profile())
    def embed(texts):
        return [[1., 0.] if 'rotor' in text.lower() else [0., 1.] for text in texts]
    with patch.object(rest, 'embed', side_effect=embed):
        result = GraphSearch(snapshot(), rest).search('rotor')
    assert result['mode'] == 'hybrid' and result['semantic_nodes'] == 3
    assert result['results'][0]['node_id'] == 'urn:test:rm'
    assert all(item['node_id'] != 'urn:test:deleted' for item in result['results'])
    with patch.object(rest, 'embed', side_effect=ValueError('fixture failure')):
        result = GraphSearch(snapshot(), rest).search('Brake')
    assert result['mode'] == 'lexical' and result['warning']
    assert result['results']


def test_domain_coverage_requires_separate_explicit_evidence():
    data = snapshot()
    assert coverage_gaps(data) == []
    data['edges'][0]['type'] = 'http://open-services.net/ns/rm#trackedBy'
    assert coverage_gaps(data) == [{'node_id': 'urn:test:rm', 'missing_implementation': True, 'missing_validation': False}]


def test_model_directed_tool_loop_and_citation_verification():
    rest = OllamaREST(profile(embeddings_enabled=False))
    messages = [
        {'role':'assistant', 'tool_calls':[{'function':{'name':'traverse_graph', 'arguments':{'node_id':'urn:test:rm','direction':'outgoing','depth':1}}}]},
        {'role':'assistant', 'content':json.dumps({'answer':'The requirement has an explicit implementation link [E1].', 'citation_ids':['E1']})},
    ]
    with patch.object(rest, 'chat', side_effect=messages) as chat:
        result = GraphAgent(snapshot(), rest).run('Explain implementation', 'urn:test:rm')
    assert result['mode'] == 'agent' and chat.call_count == 2
    assert [step['tool'] for step in result['trace']] == ['inspect_resource', 'traverse_graph']
    assert 'urn:test:fn' in result['highlight_ids']
    assert all(item['node_id'] != 'urn:test:deleted' for item in result['citations'])


def test_forbidden_tools_and_invented_citations_fall_back():
    for message in [
        {'tool_calls':[{'function':{'name':'http_get','arguments':{'url':'https://attacker.invalid'}}}]},
        {'content':json.dumps({'answer':'Invented result [E999]', 'citation_ids':['E999']})},
    ]:
        rest = OllamaREST(profile(embeddings_enabled=False))
        with patch.object(rest, 'chat', return_value=message):
            result = GraphAgent(snapshot(), rest).run('Explain', 'urn:test:rm')
        assert result['mode'] == 'evidence' and result['warning']
        assert 'Invented result' not in result['answer']


@pytest.mark.parametrize('status, expected', [(400, 'native tool calling'), (401, 'authentication failed'),
    (403, 'access was denied'), (404, 'chat route was not found'), (429, 'rate limited'), (503, 'HTTP 503')])
def test_agent_reports_safe_http_failure_reason(status, expected):
    rest = OllamaREST(profile(embeddings_enabled=False))
    request = httpx.Request('POST', 'https://secret.invalid/api/chat?key=PRIVATE_SENTINEL', headers={'api-key': 'PRIVATE_SENTINEL'})
    error = httpx.HTTPStatusError('PRIVATE_SENTINEL', request=request,
        response=httpx.Response(status, text='PRIVATE_SENTINEL', request=request))
    with patch.object(rest, 'chat', side_effect=error):
        result = GraphAgent(snapshot(), rest).run('Explain', 'urn:test:rm')
    assert result['mode'] == 'evidence' and expected in result['warning']
    assert 'PRIVATE_SENTINEL' not in json.dumps(result) and 'secret.invalid' not in json.dumps(result)


@pytest.mark.parametrize('error, expected', [
    (httpx.ReadTimeout('PRIVATE_SENTINEL'), 'timed out'),
    (httpx.ConnectError('PRIVATE_SENTINEL'), 'Could not communicate'),
    (ValueError('AI request exceeded the configured context byte budget'), 'AI_CONTEXT_MAX_BYTES'),
    (ValueError('AI operation reached its total deadline'), 'AI_AGENT_DEADLINE_SECONDS'),
    (ValueError('PRIVATE_SENTINEL'), 'arguments were invalid'),
])
def test_agent_reports_safe_transport_and_budget_reason(error, expected):
    rest = OllamaREST(profile(embeddings_enabled=False))
    with patch.object(rest, 'chat', side_effect=error):
        result = GraphAgent(snapshot(), rest).run('Explain', 'urn:test:rm')
    assert result['mode'] == 'evidence' and expected in result['warning']
    assert 'PRIVATE_SENTINEL' not in json.dumps(result)


def test_agent_distinguishes_malformed_json_citations_and_unfinished_loop():
    for message, expected in [({'content': 'PRIVATE_SENTINEL'}, 'not valid JSON'),
        ({'content': json.dumps({'answer': 'Unknown [E999]', 'citation_ids': ['E999']})}, 'citation validation'),
        ({'tool_calls': [{'function': {'name': 'inspect_resource', 'arguments': {'node_id': 'urn:test:fn'}}}]}, 'AI_AGENT_MAX_STEPS')]:
        rest = OllamaREST(profile(embeddings_enabled=False))
        with patch.object(rest, 'chat', return_value=message):
            result = GraphAgent(snapshot(), rest).run('Explain', 'urn:test:rm')
        assert result['mode'] == 'evidence' and expected in result['warning']
        assert 'PRIVATE_SENTINEL' not in json.dumps(result)


def test_configured_ollama_port_alias_and_embedding_default(monkeypatch):
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://127.0.0.1:1434/ollama')
    monkeypatch.setattr(settings, 'AI_EMBEDDING_MODEL', 'custom-embed:local')
    profile = AIConnection(base_url='http://localhost:1434/ollama/api/chat')
    assert profile.base_url == 'http://localhost:1434/ollama'
    assert profile.embedding_model == 'custom-embed:local'
    with pytest.raises(ValueError):
        AIConnection(base_url='http://localhost:11434/ollama')


def test_http_ai_policy_applies_to_session_profiles_without_relaxing_allowlist(monkeypatch):
    monkeypatch.setattr(settings, 'AI_REQUIRE_HTTPS', False)
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://models.example/ollama')
    monkeypatch.setattr(settings, 'AI_ALLOWED_BASE_URLS', [])
    assert AIConnection(base_url='http://models.example/ollama/api/chat').base_url == 'http://models.example/ollama'
    with pytest.raises(ValueError):
        AIConnection(base_url='http://unregistered.example')
    with pytest.raises(ValueError):
        AIConnection(base_url='http://user:secret@models.example/ollama')
    monkeypatch.setattr(settings, 'AI_REQUIRE_HTTPS', True)
    with pytest.raises(ValueError, match='AI_REQUIRE_HTTPS=true'):
        AIConnection(base_url='http://models.example/ollama')


def test_agent_session_guard_rechecked_between_tools():
    allowed = [True]
    def guard():
        if not allowed[0]: raise HTTPException(401, 'fixture session ended')
    rest = OllamaREST(profile(embeddings_enabled=False), guard)
    def chat(*_):
        allowed[0] = False
        return {'tool_calls':[{'function':{'name':'inspect_resource','arguments':{'node_id':'urn:test:fn'}}}]}
    with patch.object(rest, 'chat', side_effect=chat), pytest.raises(HTTPException):
        GraphAgent(snapshot(), rest).run('Explain', 'urn:test:rm')


def test_api_search_and_evidence_agent_without_ollama(session_store):
    _, token, client = session_store
    headers = {'X-CodeTrace-Session': token}
    search = client.post('/api/v1/workspace/search', headers=headers, json={'review_id':'graph','query':'Brake','semantic':False})
    assert search.status_code == 200 and search.json()['mode'] == 'lexical'
    agent = client.post('/api/v1/workspace/agent/run', headers=headers, json={'review_id':'graph','question':'Explain','selected_id':'urn:test:rm'})
    assert agent.status_code == 200, agent.text
    assert agent.json()['mode'] == 'evidence' and agent.json()['trace']
    assert client.post('/api/v1/workspace/agent/run', headers=headers, json={'review_id':'graph','question':'Explain','agent_id':'shell-executor'}).status_code == 422


def test_raw_git_checks_do_not_execute_filters(tmp_path):
    import os
    import subprocess
    import sys
    import time
    from services.git_revision import raw_revision
    from services.git_isolation import git_environment
    root = tmp_path/'repo'; root.mkdir()
    marker = tmp_path/'marker'
    helper = tmp_path/'filter.py'
    helper.write_text('import sys\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("fixture")\nsys.stdout.write(sys.stdin.read())\n')
    def git(*args):
        return subprocess.run(['git','-C',str(root),*args], capture_output=True, check=True).stdout
    git('init')
    git('config', 'core.autocrlf', 'false')
    git('config','filter.audit.clean','"'+sys.executable.replace('\\','/')+'" "'+str(helper).replace('\\','/')+'"')
    (root/'.gitattributes').write_text('*.py filter=audit\n')
    (root/'a.py').write_text('x=1\n')
    git('add','.')
    git('-c','user.name=Audit','-c','user.email=audit@example.invalid','commit','-m','fixture')
    marker.unlink(missing_ok=True)
    env = git_environment(tmp_path/'home')
    assert raw_revision(root, env) == git('rev-parse','HEAD').decode().strip()
    assert not marker.exists()
    (root/'a.py').write_text('x=2\n'); os.utime(root/'a.py', (time.time()+3,time.time()+3))
    assert raw_revision(root, env) is None
    assert not marker.exists()


def test_session_agent_configuration_isolated_and_resettable(session_store):
    store, token, client = session_store
    headers = {'X-CodeTrace-Session': token}
    body = profile().private()
    body['agent_configuration'] = {'trace-explorer': {'system_prompt': 'Review braking evidence precisely.', 'tools': ['coverage_gaps']}}
    body['tool_configuration'] = {'coverage_gaps': {'description': 'Check explicit RM implementation and QM validation.'}}
    assert client.put('/api/v1/workspace/ai/config', headers=headers, json=body).status_code == 200
    result = client.get('/api/v1/workspace/ai/config', headers=headers).json()
    assert result['agents'][0]['system_prompt'] == 'Review braking evidence precisely.'
    assert result['agents'][0]['tools'] == ['coverage_gaps']
    other = store.create()['token']
    other_profile = client.get('/api/v1/workspace/ai/config', headers={'X-CodeTrace-Session': other}).json()
    assert other_profile['agents'][0]['system_prompt'] != result['agents'][0]['system_prompt']
    assert client.delete('/api/v1/workspace/ai/config', headers=headers).status_code == 200
    assert client.get('/api/v1/workspace/ai/config', headers=headers).json()['agent_configuration'] == {}


def test_configured_tools_enforced_and_prompts_forwarded():
    from services.agent_workspace import tool_schema
    connection = profile(agent_configuration={'trace-explorer': {'system_prompt': 'Custom reviewer instructions.', 'tools': ['coverage_gaps']}},
                         tool_configuration={'coverage_gaps': {'description': 'Custom coverage description.'}})
    rest = OllamaREST(connection)
    agent = GraphAgent(snapshot(), rest)
    with pytest.raises(ValueError, match='not permitted'):
        agent.tool('inspect_resource', {'node_id': 'urn:test:rm'})
    assert tool_schema('coverage_gaps', connection)['function']['description'] == 'Custom coverage description.'
    with patch.object(rest, 'chat', return_value={'content': '{}'}) as chat:
        result = agent.run('Review coverage', 'urn:test:rm')
    assert chat.call_args.args[0][0]['content'] == 'Custom reviewer instructions.'
    assert 'Runtime evidence contract' in chat.call_args.args[0][1]['content']
    assert not result['trace']  # Disabled automatic inspect/search must never run.
    for override in [{'system_prompt': ' ', 'tools': ['search_graph']},
                     {'system_prompt': 'Review', 'tools': []},
                     {'system_prompt': 'Review', 'tools': ['execute_shell']},
                     {'system_prompt': 'Review', 'tools': ['search_graph', 'search_graph']}]:
        with pytest.raises(ValueError):
            profile(agent_configuration={'trace-explorer': override})
