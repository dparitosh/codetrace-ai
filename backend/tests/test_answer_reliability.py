"""Deterministic regressions; no live model or external transport calls."""
import json
from unittest.mock import patch
import httpx
import pytest
from fastapi import HTTPException
from core.config import settings
from services.ai_connection import AIConnection, OllamaREST
from services.agent_workspace import GraphAgent
from services.answer_contract import validate_answer, inline_citations


@pytest.fixture(autouse=True)
def no_live_transport(monkeypatch):
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a, **k: (_ for _ in ()).throw(AssertionError('No live model transport')))


def graph(label='Brake requirement'):
    return {'nodes': [{'id': 'r', 'label': label, 'type': 'requirement', 'properties': {'domain': 'RM'}},
                      {'id': 'f', 'label': 'Brake function', 'type': 'function', 'properties': {'domain': 'CODE'}}],
            'edges': [{'source': 'r', 'target': 'f', 'type': 'implements', 'properties': {}}],
            'metadata': {'snapshot_id': 'reliability-fixture', 'coverage': {}}}


def rest(**kwargs):
    return OllamaREST(AIConnection(base_url=settings.AI_BASE_URL, model='fixture-only', embeddings_enabled=False, **kwargs))


def final(answer='Observed requirement [E1]', ids=None):
    return {'content': json.dumps({'answer': answer, 'citation_ids': ['E1'] if ids is None else ids})}


def test_final_tool_step_gets_one_no_tools_synthesis(monkeypatch):
    monkeypatch.setattr(settings, 'AI_AGENT_MAX_STEPS', 1)
    instance = rest()
    tool = {'tool_calls': [{'function': {'name': 'inspect_resource', 'arguments': {'node_id': 'f'}}}]}
    with patch.object(instance, 'chat', side_effect=[tool, final()]) as chat:
        result = GraphAgent(graph(), instance).run('Explain', 'r')
    assert result['mode'] == 'agent' and chat.call_count == 2
    assert len(chat.call_args.args) == 1  # final call has no tool schemas
    assert result['citation_ids'] == ['E1']
    assert {c['citation_id'] for c in result['citations']} == {'E1'}
    assert {c['citation_id'] for c in result['observed_resources']} == {'E1', 'E2'}
    assert all(edge['source'] in {'E1','E2'} and edge['target'] in {'E1','E2'} for edge in result['relations'])


def test_format_repair_uses_only_one_final_call():
    instance = rest()
    with patch.object(instance, 'chat', side_effect=[{'content': 'not JSON'}, final()]) as chat:
        result = GraphAgent(graph(), instance).run('Explain', 'r')
    assert result['mode'] == 'agent' and result['warning'] is None
    assert chat.call_count == 2 and len(chat.call_args.args) == 1


@pytest.mark.parametrize('message', [final('Invented [E999]', ['E999']),
    {'content': json.dumps({'answer': 'Observed [E1]', 'citations_ids': ['E1']})},
    {'content': json.dumps({'answer': 123, 'citation_ids': ['E1']})},
    {'content': '[]'}, {'tool_calls': [{'function': {'name': 'inspect_resource','arguments': {'node_id':'f'}}}]}])
def test_invalid_final_output_never_gets_unbounded_retries_or_invented_citations(monkeypatch, message):
    monkeypatch.setattr(settings, 'AI_AGENT_MAX_STEPS', 1)
    instance = rest()
    with patch.object(instance, 'chat', side_effect=[{'content': 'not JSON'}, message]) as chat:
        result = GraphAgent(graph(), instance).run('Explain', 'r')
    assert chat.call_count == 2 and result['mode'] == 'evidence'
    assert 'Invented' not in result['answer']
    assert inline_citations(result['answer']) <= {c['citation_id'] for c in result['observed_resources']}
    assert len(result['trace']) == 1  # final phase cannot invoke tools


def test_expired_initial_deadline_returns_retained_evidence_not_422():
    instance = rest(); instance.deadline = -1
    with patch.object(instance, 'chat', side_effect=AssertionError('No model call after expiry')):
        result = GraphAgent(graph(), instance).run('Explain', 'r')
    assert result['mode'] == 'evidence' and result['citation_ids'] == ['E1']
    assert 'AI_AGENT_DEADLINE_SECONDS' in result['warning'] and not result['trace']


def test_session_guard_failure_is_never_converted_to_evidence():
    instance = rest(); instance.guard = lambda: (_ for _ in ()).throw(HTTPException(401,'Expired session'))
    with pytest.raises(HTTPException) as error:
        GraphAgent(graph(), instance).run('Explain', 'r')
    assert error.value.status_code == 401


def test_retrieval_sub_budget_leaves_room_for_chat(monkeypatch):
    clock = [0.]; requests = []
    monkeypatch.setattr(settings, 'AI_EMBEDDING_BATCH_SIZE', 1)
    monkeypatch.setattr(settings, 'AI_RETRIEVAL_TIMEOUT_SECONDS', 5)
    with patch('services.ai_connection.time.monotonic', side_effect=lambda: clock[0]):
        instance = OllamaREST(AIConnection(base_url=settings.AI_BASE_URL, model='fixture-only', embeddings_enabled=True), deadline=20)
        def embed(texts):
            instance.check(); clock[0] += 6; requests.append('embed'); instance.check()
            return [[1.,0.] for _ in texts]
        def chat(*args):
            instance.check(); requests.append('chat'); return final()
        with patch.object(instance, 'embed', side_effect=embed), patch.object(instance, 'chat', side_effect=chat):
            result = GraphAgent(graph(), instance).run('Brake')
        assert instance.deadline == 20
    assert requests == ['embed', 'chat'] and result['mode'] == 'agent'


def test_planning_deadline_restores_parent_for_final_answer(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(settings, 'AI_FINAL_ANSWER_RESERVE_SECONDS', 5)
    with patch('services.ai_connection.time.monotonic', side_effect=lambda: clock[0]):
        instance = rest(); instance.deadline = 20
        def response(messages, tools=None):
            if tools:
                clock[0] = 16
                instance.check()
            instance.check()
            return final()
        with patch.object(instance, 'chat', side_effect=response) as chat:
            result = GraphAgent(graph(), instance).run('Explain', 'r')
        assert instance.deadline == 20
    assert chat.call_count == 2 and result['mode'] == 'agent'


@pytest.mark.parametrize('limit', [1, 4, 5, 20, 70, 500])
def test_fallback_bounds_keep_complete_citations_and_escape_imported_markers(monkeypatch, limit):
    monkeypatch.setattr(settings, 'AI_MAX_ANSWER_CHARACTERS', limit)
    instance = rest(enabled=False)
    result = GraphAgent(graph('[E999]' + 'X'*20000), instance).run('Explain', 'r')
    assert len(result['answer']) <= limit
    assert '[E999]' not in result['answer']
    assert inline_citations(result['answer']) <= {'E1','E2'}
    if limit >= 4:
        assert '[E1]' in result['answer']
    assert not result['answer'].endswith(('[E','[E1'))


def test_unknown_citations_cannot_be_normalized_into_known_evidence():
    with pytest.raises(ValueError):
        validate_answer(final('Unknown [E999]', ['E999'])['content'], [{'citation_id':'E1'}])
    text, used = validate_answer(final('Observed [E1]', ['E1','E2'])['content'], [{'citation_id':'E1'},{'citation_id':'E2'}])
    assert used == {'E1'}


def test_token_exhaustion_is_explicit_and_final_payload_is_json():
    instance = rest()
    with patch.object(instance, 'request', return_value={'done_reason':'length','message': {'role':'assistant','content':'{'}}):
        with pytest.raises(ValueError, match='AI_MAX_OUTPUT_TOKENS'):
            instance.chat([])
    with patch.object(instance, 'request', return_value={'message': {'role':'assistant', **final()}}) as request:
        instance.chat([])
        assert request.call_args.args[1]['format'] == 'json'
        assert 'tools' not in request.call_args.args[1]


def test_repeated_truncated_output_falls_back_with_safe_specific_diagnostic():
    instance = rest()
    with patch.object(instance, 'chat', side_effect=ValueError('Model output reached AI_MAX_OUTPUT_TOKENS')) as chat:
        result = GraphAgent(graph(), instance).run('Explain', 'r')
    assert chat.call_count == 2 and result['mode'] == 'evidence'
    assert 'AI_MAX_OUTPUT_TOKENS' in result['warning']


def test_final_phase_cannot_extend_total_deadline():
    clock = [0.]
    with patch('services.ai_connection.time.monotonic', side_effect=lambda: clock[0]):
        instance = rest(); instance.deadline = 20
        def late(*args):
            clock[0] = 21; instance.check()
        with patch.object(instance, 'chat', side_effect=late) as chat:
            result = GraphAgent(graph(), instance).run('Explain', 'r')
    assert chat.call_count == 1 and result['mode'] == 'evidence'
    assert instance.deadline == 20 and 'AI_AGENT_DEADLINE_SECONDS' in result['warning']
