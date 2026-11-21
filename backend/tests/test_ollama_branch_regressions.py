"""Offline transport/agent regressions for the pre-optimization test branch."""
import json
from unittest.mock import patch

import httpx
import pytest

from core.config import settings
from services.ai_connection import AIConnection, OllamaREST
from services.agent_workspace import GraphAgent


@pytest.fixture(autouse=True)
def no_live_transport(monkeypatch):
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a, **k: (_ for _ in ()).throw(AssertionError('No live model transport')))


def connection():
    return AIConnection(base_url=settings.AI_BASE_URL, model='offline-fixture', embeddings_enabled=False)


@pytest.mark.parametrize('done', [False, None, 'true', 1])
def test_explicit_unfinished_or_invalid_completion_is_not_accepted(done):
    rest=OllamaREST(connection())
    with patch.object(rest, 'request', return_value={'done':done,'message':{'role':'assistant','content':'{"answer":"Observed [E1]","citation_ids":["E1"]}'}}):
        with pytest.raises(ValueError,match='Invalid chat response'):
            rest.chat([])


def test_native_tool_history_retains_protocol_context_but_never_exports_thinking():
    graph={'nodes':[{'id':'f','type':'function','label':'Fixture','properties':{'domain':'CODE'}}],
           'edges':[],'metadata':{'snapshot_id':'offline-fixture','coverage':{}}}
    rest=OllamaREST(connection())
    protocol_content='progress '*300
    private_context='PRIVATE_THINKING_CONTEXT'
    turns=[]
    def reply(messages,tools=None):
        turns.append(1)
        if len(turns)==1:
            return {'role':'assistant','content':protocol_content,'thinking':private_context,
                    'tool_calls':[{'function':{'name':'inspect_resource','arguments':{'node_id':'f'}}}]}
        assistant=next(message for message in messages if message.get('tool_calls'))
        assert assistant.get('thinking')==private_context
        assert assistant['content']==protocol_content
        return {'role':'assistant','content':'{"answer":"Observed [E1]","citation_ids":["E1"]}'}
    with patch.object(rest,'chat',side_effect=reply):
        result=GraphAgent(graph,rest).run('Explain','f')
    assert result['mode']=='agent' and len(turns)==2
    assert private_context not in json.dumps(result)


def test_response_decoding_cannot_return_after_total_deadline(monkeypatch):
    clock=[0.]
    original_loads=json.loads
    def decode(body):
        value=original_loads(body);clock[0]=11.
        return value
    factory=httpx.Client
    transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'{"models":[]}'))
    with patch('services.ai_connection.time.monotonic',side_effect=lambda:clock[0]), \
         patch('services.ai_connection.httpx.Client',side_effect=lambda **kw:factory(transport=transport,**kw)):
        rest=OllamaREST(connection(),deadline=10.)
        monkeypatch.setattr('services.ai_connection.json.loads',decode)
        with pytest.raises(ValueError,match='total deadline'):
            rest.request('tags')


def test_preserved_protocol_context_cannot_bypass_existing_request_byte_limit(monkeypatch):
    monkeypatch.setattr(settings,'AI_CONTEXT_MAX_BYTES',4096)
    rest=OllamaREST(connection())
    with pytest.raises(ValueError,match='context byte budget'):
        rest.chat([{'role':'assistant','thinking':'PRIVATE_CONTEXT'*1000,'content':'','tool_calls':[]}])


@pytest.mark.parametrize('extra',[{'content':[]},{'thinking':{}},{'thinking':[]}])
def test_malformed_tool_context_falls_back_without_executing_the_model_tool(extra):
    graph={'nodes':[{'id':'f','type':'function','label':'Fixture','properties':{'domain':'CODE'}}],
           'edges':[],'metadata':{'snapshot_id':'offline-fixture','coverage':{}}}
    rest=OllamaREST(connection())
    message={'content':'','tool_calls':[{'function':{'name':'inspect_resource','arguments':{'node_id':'f'}}}],**extra}
    with patch.object(rest,'chat',return_value=message) as chat:
        result=GraphAgent(graph,rest).run('Explain','f')
    assert chat.call_count==1 and result['mode']=='evidence'
    assert len(result['trace'])==1  # Initial local inspection only.


@pytest.mark.parametrize('done',[{}, {'done':True}])
def test_compatible_gateway_without_done_and_completed_native_chat_still_work(done):
    rest=OllamaREST(connection())
    with patch.object(rest,'request',return_value={**done,'message':{'role':'assistant','content':'{"ready":true}'}}):
        assert rest.chat([])['content']=='{"ready":true}'


@pytest.mark.parametrize('suffix,path',[('/api/chat','/api/chat'),('/gateway/api/chat','/gateway/api/chat')])
def test_configured_http_port_and_operation_url_use_exact_native_route(monkeypatch,suffix,path):
    monkeypatch.setattr(settings,'AI_BASE_URL','http://127.0.0.1:1434'+suffix)
    monkeypatch.setattr(settings,'AI_REQUIRE_HTTPS',False)
    monkeypatch.setattr(settings,'AI_ALLOWED_BASE_URLS',[])
    requests=[]
    def reply(request):
        requests.append(request)
        assert request.url.port==1434 and request.url.path==path
        assert json.loads(request.content)['model']=='offline-fixture'
        return httpx.Response(200,json={'done':True,'message':{'role':'assistant','content':'{"ready":true}'}})
    factory=httpx.Client
    with patch('services.ai_connection.httpx.Client',side_effect=lambda **kw:factory(transport=httpx.MockTransport(reply),**kw)):
        assert OllamaREST(connection()).chat([])['content']=='{"ready":true}'
    assert len(requests)==1


def test_https_is_optional_by_default_and_enforced_when_configured(monkeypatch):
    assert settings.__class__.model_fields['AI_REQUIRE_HTTPS'].default is False
    monkeypatch.setattr(settings,'AI_REQUIRE_HTTPS',True)
    with pytest.raises(ValueError,match='HTTPS'):
        connection()
