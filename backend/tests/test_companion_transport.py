"""Offline regressions for native and compatible companion transport boundaries."""
import json
from unittest.mock import patch
import httpx
import pytest
from core.config import settings
from services.companion_service import answer_question
from services.ai_connection import AIConnection

GRAPH = {'nodes': [{'id':'f','label':'Fixture function','type':'function','properties':{'domain':'CODE'}}], 'edges':[], 'metadata': {'snapshot_id':'offline-audit','coverage':{}}}
VALID = json.dumps({'answer':'Observed fixture [E1]', 'citation_ids':['E1']})

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'ollama')
    monkeypatch.setattr(settings, 'AI_MODEL', 'fixture-only')
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://127.0.0.1:1434')
    monkeypatch.setattr('services.companion_service.server_secret', lambda _: None)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a, **k: (_ for _ in ()).throw(AssertionError('Live transport prohibited')))


def transport(body, requests):
    def handle(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=body if isinstance(body, bytes) else json.dumps(body).encode())
    real = httpx.Client
    return patch('httpx.Client', side_effect=lambda **kw: real(transport=httpx.MockTransport(handle), **kw))

@pytest.mark.parametrize('state', [{'done':False}, {'done':True,'done_reason':'length'}])
def test_incomplete_legacy_answer_must_not_be_accepted(state):
    with transport({**state, 'message':{'role':'assistant','content':VALID}}, []):
        result = answer_question(GRAPH, 'Explain', 'f')
    assert result['mode'] == 'evidence', result


def test_native_operation_url_must_not_be_duplicated(monkeypatch):
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://127.0.0.1:1434/api/chat')
    requests=[]
    with transport({'message':{'content':VALID}, 'done':True}, requests):
        answer_question(GRAPH, 'Explain', 'f')
    assert requests == ['http://127.0.0.1:1434/api/chat'], requests


def test_nested_provider_json_must_return_evidence(monkeypatch):
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'openai-compatible')
    with transport(b'[' * 10000 + b'0' + b']' * 10000, []):
        result = answer_question(GRAPH, 'Explain', 'f')
    assert result['mode'] == 'evidence'


def test_session_companion_must_report_specific_validation_reason():
    bad=json.dumps({'answer':'Invented [E999]','citation_ids':['E999']})
    connection=AIConnection(base_url=settings.AI_BASE_URL, model='fixture-only', embeddings_enabled=False)
    with transport({'message':{'content':bad}, 'done':True}, []):
        result=answer_question(GRAPH,'Explain','f',connection=connection)
    assert 'unknown_citations' in result['warning'], result['warning']

def test_native_readiness_nested_content_must_be_controlled(monkeypatch):
    import threading
    from types import SimpleNamespace
    from api import workspace_routes
    monkeypatch.setattr(workspace_routes.review_routes, 'store', SimpleNamespace(workers=threading.BoundedSemaphore(1)))
    connection=AIConnection(base_url=settings.AI_BASE_URL, model='fixture-only', embeddings_enabled=False, discovery_enabled=False)
    monkeypatch.setattr(workspace_routes, 'connection_for', lambda *args: connection)
    monkeypatch.setattr(workspace_routes, 'ai_guard', lambda *args: lambda: None)
    nested='[' * 10000 + '0' + ']' * 10000
    with transport({'message':{'content':nested}, 'done':True}, []):
        try:
            workspace_routes.test_ai('fixture-session')
        except Exception as error:
            from fastapi import HTTPException
            assert isinstance(error, HTTPException) and error.status_code == 502, type(error).__name__
        else:
            pytest.fail('Invalid readiness unexpectedly succeeded')
    assert workspace_routes.review_routes.store.workers.acquire(blocking=False)
    workspace_routes.review_routes.store.workers.release()

@pytest.mark.parametrize('base', ['http://127.0.0.1:1434', 'http://127.0.0.1:1434/gateway/api/chat'])
@pytest.mark.parametrize('completion', [{}, {'done':True}])
def test_complete_native_answer_preserves_gateway_prefix(monkeypatch, base, completion):
    monkeypatch.setattr(settings, 'AI_BASE_URL', base)
    requests=[]
    with transport({**completion, 'message':{'role':'assistant','content':VALID}}, requests):
        result=answer_question(GRAPH,'Explain','f')
    assert requests == [base if base.endswith('/api/chat') else base + '/api/chat']
    assert result['mode']=='ollama' and result['warning'] is None
    assert result['citation_ids']==['E1']


def test_compatible_contract_retains_version_prefix_auth_and_answer(monkeypatch):
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'openai-compatible')
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://127.0.0.1:1434/v1')
    monkeypatch.setattr(settings, 'AI_KEY_HEADER', 'api-key')
    monkeypatch.setattr('services.companion_service.server_secret', lambda _: 'FIXTURE_KEY')
    def handle(request):
        assert str(request.url)=='http://127.0.0.1:1434/v1/chat/completions'
        assert request.headers['api-key']=='FIXTURE_KEY'
        payload=json.loads(request.content)
        assert payload['response_format']=={'type':'json_object'}
        assert 'options' not in payload
        return httpx.Response(200,json={'choices':[{'message':{'content':VALID}}]})
    real=httpx.Client
    with patch('httpx.Client', side_effect=lambda **kw: real(transport=httpx.MockTransport(handle),**kw)):
        result=answer_question(GRAPH,'Explain','f')
    assert result['mode']=='openai-compatible' and result['citation_ids']==['E1']
    assert 'FIXTURE_KEY' not in json.dumps(result)


@pytest.mark.parametrize('status, expected', [(401,'authentication failed'),(403,'access was denied'),(429,'rate limited')])
def test_companion_http_diagnostics_never_echo_provider_secrets(status, expected):
    real=httpx.Client
    def handle(request):
        return httpx.Response(status,text='PRIVATE_PROVIDER_BODY FIXTURE_KEY')
    with patch('httpx.Client',side_effect=lambda **kw: real(transport=httpx.MockTransport(handle),**kw)):
        result=answer_question(GRAPH,'Explain','f')
    assert result['mode']=='evidence' and expected in result['warning']
    assert 'PRIVATE_PROVIDER_BODY' not in json.dumps(result) and 'FIXTURE_KEY' not in json.dumps(result)


def test_disabled_native_helper_does_not_contact_provider(monkeypatch):
    monkeypatch.setattr(settings,'AI_PROVIDER','disabled')
    result=answer_question(GRAPH,'Explain','f')
    assert result['mode']=='evidence' and 'disabled' in result['warning']
