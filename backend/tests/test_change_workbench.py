import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from api import review_routes
from api.change_routes import store
from core.config import settings
from services.change_store import ChangeStore, FIELDS, digest, encoded
from services.agent_workspace import GraphAgent

BASE = '/api/v1/workspace/changes'


@pytest.fixture
def workbench(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'CHANGE_DB_PATH', tmp_path / 'changes.sqlite')
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'disabled')
    monkeypatch.setattr(review_routes, 'store', review_routes.ReviewStore())
    with TestClient(app) as client:
        token = client.post('/api/v1/review/session').json()['token']
        headers = {'X-CodeTrace-Session': token}
        response = client.post('/api/v1/review/reviews', headers=headers, json={
            'request_id': 'source', 'kind': 'graph', 'source': {'files': [
                {'path': 'app.py', 'content': 'def charge():\n    return 1\ndef refund():\n    return 2\n'}]}})
        assert response.status_code == 200, response.text
        graph = response.json()['result']
        nodes = [node['id'] for node in graph['nodes'] if node['type'] == 'function']
        response = client.post(BASE, headers=headers, json={'review_id': 'source', 'request_id': 'case', 'selected_id': nodes[0]})
        assert response.status_code == 200, response.text
        yield client, headers, response.json(), nodes


def ask(client, headers, case, node_id, request_id='turn', automate=False):
    response = client.post(BASE + '/case/conversation', headers=headers, json={
        'revision': case['revision'], 'request_id': request_id, 'question': 'Explain this context and propose corrections',
        'selected_id': node_id, 'automate': automate})
    assert response.status_code == 200, response.text
    return response.json()


def complete(client, headers, case, node):
    result = client.post(BASE + '/case/evidence', headers=headers, json={'revision': case['revision'], 'node_id': node})
    assert result.status_code == 200
    case = result.json()
    fields = {key: 'Reviewed, change-specific ' + key for key in FIELDS}
    response = client.post(BASE + '/case/edit', headers=headers, json={'revision': case['revision'], **fields})
    assert response.status_code == 200
    return response.json()


def test_automation_uses_three_read_only_agents_and_preserves_human_edits(workbench):
    client, headers, case, nodes = workbench
    response = client.post(BASE + '/case/edit', headers=headers, json={'revision': case['revision'], 'proposal': 'Human curated proposal'})
    case = response.json()
    with patch('services.ai_connection.OllamaREST.chat', side_effect=AssertionError('No live LLM allowed')):
        case = ask(client, headers, case, nodes[0], automate=True)
    assert len(case['turns']) == 1
    assert [item['agent_id'] for item in case['turns'][0]['analyses']] == ['trace-explorer', 'coverage-reviewer', 'change-analyst']
    assert case['evidence'] and all(item['snapshot_id'] == case['snapshot_id'] for item in case['evidence'])
    assert case['proposal'] == 'Human curated proposal'
    assert case['automation_review_required'] is True
    assert all(case[field] for field in FIELDS if field != 'rollback')
    response = client.post(BASE + '/case/decision', headers=headers, json={'revision': case['revision'], 'action': 'submit'})
    assert response.status_code == 422
    assert 'human review' in response.json()['error']


def test_conversation_context_and_e1_capture_are_distinct_between_turns(workbench):
    client, headers, case, nodes = workbench
    observed_history = []
    original = GraphAgent.run
    def inspect_history(self, *args, **kwargs):
        observed_history.append(kwargs.get('history'))
        return original(self, *args, **kwargs)
    with patch.object(GraphAgent, 'run', inspect_history):
        case = ask(client, headers, case, nodes[0], 'one')
        first = case['turns'][0]
        case = ask(client, headers, case, nodes[1], 'two')
    second = case['turns'][1]
    assert observed_history[0] == []
    assert observed_history[1][0]['question'] == first['question']
    assert observed_history[1][0]['selected_id'] == nodes[0]
    for turn, node in [(first, nodes[0]), (second, nodes[1])]:
        citation = turn['analyses'][0]['result']['citations'][0]
        assert citation['citation_id'] == 'E1' and citation['node_id'] == node
        response = client.post(BASE + '/case/evidence', headers=headers, json={'revision': case['revision'], 'node_id': node,
            'turn_id': turn['id'], 'agent_id': 'trace-explorer', 'citation_id': 'E1'})
        assert response.status_code == 200, response.text
        case = response.json()
    assert len(case['evidence']) == 2
    assert len({e['id'] for e in case['evidence']}) == 2
    assert {e['provenance']['turn_id'] for e in case['evidence']} == {first['id'], second['id']}
    spoof = client.post(BASE + '/case/evidence', headers=headers, json={'revision': case['revision'], 'node_id': nodes[1],
        'turn_id': first['id'], 'agent_id': 'trace-explorer', 'citation_id': 'E1'})
    assert spoof.status_code == 422


def test_exact_version_review_export_and_revision_do_not_inherit_approval(workbench):
    client, headers, case, nodes = workbench
    assert client.post(BASE + '/case/decision', headers=headers, json={'revision': case['revision'], 'action': 'submit'}).status_code == 422
    case = complete(client, headers, case, nodes[0])
    case = client.post(BASE + '/case/decision', headers=headers, json={'revision': case['revision'], 'action': 'submit'}).json()
    frozen = case['versions'][0]
    assert case['state'] == 'submitted'
    assert client.post(BASE + '/case/edit', headers=headers, json={'revision': case['revision'], 'title': 'Cannot change'}).status_code == 409
    assert client.get(BASE + '/case/export', headers=headers).status_code == 409
    assert client.post(BASE + '/case/external', headers=headers, json={'revision': case['revision']}).status_code == 409
    assert client.post(BASE + '/case/decision', headers=headers, json={'revision': case['revision'] - 1, 'action': 'approve', 'note': 'Stale'}).status_code == 409
    case = client.post(BASE + '/case/decision', headers=headers, json={'revision': case['revision'], 'action': 'approve', 'note': 'Reviewed evidence and acceptance criteria'}).json()
    assert case['state'] == 'approved'
    exported = client.get(BASE + '/case/export', headers=headers)
    assert exported.status_code == 200
    assert exported.json()['digest'] == frozen['digest']
    assert client.post(BASE + '/case/external', headers=headers, json={'revision': case['revision']}).status_code == 501
    case = client.post(BASE + '/case/decision', headers=headers, json={'revision': case['revision'], 'action': 'revise'}).json()
    assert case['state'] == 'draft' and case['version'] == 2
    assert case['versions'][0] == frozen
    assert client.get(BASE + '/case/export', headers=headers).status_code == 409


def test_dossiers_and_turns_survive_session_end_and_store_restart(workbench):
    client, headers, case, nodes = workbench
    case = ask(client, headers, case, nodes[0])
    client.delete('/api/v1/review/session', headers=headers)
    assert client.get(BASE + '/case', headers=headers).status_code == 401
    new_headers = {'X-CodeTrace-Session': client.post('/api/v1/review/session').json()['token']}
    recovered = client.get(BASE + '/case', headers=new_headers)
    assert recovered.status_code == 200
    assert recovered.json()['turns'] == case['turns']
    assert ChangeStore(settings.CHANGE_DB_PATH).get('case')['turns'] == case['turns']
    assert client.get(BASE).status_code == 401


def test_duplicate_analysis_request_does_not_duplicate_turn_or_evidence(workbench):
    client, headers, case, nodes = workbench
    original = case
    case = ask(client, headers, case, nodes[0], automate=True)
    retried = ask(client, headers, original, nodes[0], automate=True)
    assert retried['turns'] == case['turns'] and retried['evidence'] == case['evidence']
    assert retried['revision'] == case['revision']


def test_failed_analysis_is_saved_and_retry_recovers_same_turn(workbench):
    client, headers, case, nodes = workbench
    body = {'revision': case['revision'], 'request_id': 'retry', 'question': 'Explain', 'selected_id': nodes[0]}
    with patch.object(GraphAgent, 'run', side_effect=ValueError('Synthetic model failure')):
        response = client.post(BASE + '/case/conversation', headers=headers, json=body)
    assert response.status_code == 502
    failed = client.get(BASE + '/case', headers=headers).json()
    assert failed['turns'][0]['state'] == 'failed'
    response = client.post(BASE + '/case/conversation', headers=headers, json=body)
    assert response.status_code == 200
    recovered = response.json()
    assert len(recovered['turns']) == 1 and recovered['turns'][0]['state'] == 'completed'
    assert recovered['turns'][0]['id'] == failed['turns'][0]['id']


def test_processing_turn_blocks_edits_and_expired_attempt_cannot_overwrite_retry(workbench):
    _, _, case, nodes = workbench
    db = store()
    turn, _, attempt = db.reserve('case', case['revision'], 'work', 'Investigate', nodes[0], False)
    with pytest.raises(HTTPException) as error:
        db.update('case', case['revision'], {'title': 'Race'})
    assert error.value.status_code == 409
    with db.db() as conn:
        conn.execute("UPDATE turns SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?", (turn,))
    _, execute, retry_attempt = db.reserve('case', case['revision'], 'work', 'Investigate', nodes[0], False)
    assert execute and retry_attempt != attempt
    with pytest.raises(HTTPException):
        db.finish('case', turn, [], attempt)
    db.fail('case', turn, attempt)
    assert db.get('case')['turns'][0]['state'] == 'processing'
    db.fail('case', turn, retry_attempt)
    assert db.get('case')['turns'][0]['state'] == 'failed'


def test_capacity_failure_rolls_back_draft_edit(workbench, monkeypatch):
    client, headers, case, _ = workbench
    monkeypatch.setattr(settings, 'CHANGE_MAX_BYTES', 10000)
    response = client.post(BASE + '/case/edit', headers=headers, json={'revision': case['revision'], 'proposal': 'X' * 12000})
    assert response.status_code == 507
    recovered = client.get(BASE + '/case', headers=headers).json()
    assert recovered['proposal'] == '' and recovered['revision'] == case['revision']


def test_agent_owned_sections_are_corrected_but_human_changes_are_preserved(workbench):
    client, headers, case, nodes = workbench
    case = ask(client, headers, case, nodes[0], 'first', automate=True)
    assert 'proposal' in case['agent_generated_fields']
    with patch.object(GraphAgent, 'run', return_value={'answer': 'Corrected recommendation', 'citations': []}):
        case = ask(client, headers, case, nodes[0], 'second', automate=True)
    assert 'Corrected recommendation' in case['proposal']
    case = client.post(BASE + '/case/edit', headers=headers, json={
        'revision': case['revision'], 'proposal': 'Reviewed human correction'}).json()
    assert 'proposal' not in case['agent_generated_fields']
    with patch.object(GraphAgent, 'run', return_value={'answer': 'Another suggestion', 'citations': []}):
        case = ask(client, headers, case, nodes[0], 'third', automate=True)
    assert case['proposal'] == 'Reviewed human correction'
    assert 'Another suggestion' in case['turns'][-1]['analyses'][0]['result']['answer']


def test_evidence_removal_affects_only_new_draft_not_frozen_version(workbench):
    client, headers, case, nodes = workbench
    case = ask(client, headers, case, nodes[0], automate=True)
    case = client.post(BASE + '/case/decision', headers=headers, json={
        'revision': case['revision'], 'action': 'submit', 'acknowledged': True}).json()
    assert case['state'] == 'submitted' and not case['automation_review_required']
    frozen = case['versions'][0]
    evidence_id = case['evidence'][0]['id']
    assert client.post(BASE + '/case/evidence/remove', headers=headers, json={
        'revision': case['revision'], 'evidence_id': evidence_id}).status_code == 409
    case = client.post(BASE + '/case/decision', headers=headers, json={
        'revision': case['revision'], 'action': 'revise'}).json()
    response = client.post(BASE + '/case/evidence/remove', headers=headers, json={
        'revision': case['revision'], 'evidence_id': evidence_id})
    assert response.status_code == 200
    case = response.json()
    assert case['versions'][0] == frozen
    assert evidence_id not in {e['id'] for e in case['evidence']}


def test_creation_retry_preserves_original_context_identity(workbench):
    _, _, case, nodes = workbench
    db = store()
    graph = db.get('case', graph=True)['graph']
    assert db.create(graph, case['snapshot_digest'], nodes[0], 'case') == 'case'
    with pytest.raises(HTTPException) as error:
        db.create(graph, case['snapshot_digest'], nodes[1], 'case')
    assert error.value.status_code == 409


def test_context_change_refreshes_agent_scope_and_warns_for_retained_human_scope(workbench):
    client, headers, case, nodes = workbench
    case = ask(client, headers, case, nodes[0], 'scope-a', automate=True)
    case = ask(client, headers, case, nodes[1], 'scope-b', automate=True)
    assert nodes[1] in case['scope'] and nodes[0] not in case['scope']
    assert not case['context_warnings']
    case = client.post(BASE + '/case/edit', headers=headers, json={
        'revision': case['revision'], 'scope': 'Human scope for refund'}).json()
    case = ask(client, headers, case, nodes[0], 'scope-c', automate=True)
    assert case['scope'] == 'Human scope for refund'
    assert case['context_warnings'] and case['scope_context_id'] == nodes[1]
    case = ask(client, headers, case, nodes[0], 'scope-d', automate=True)
    assert case['context_warnings']  # Warning survives another run in the new context.
    case = client.post(BASE + '/case/edit', headers=headers, json={
        'revision': case['revision'], 'scope': 'Human scope for charge'}).json()
    assert not case['context_warnings']


def test_frozen_conversation_survives_later_retry_and_restart(workbench):
    client, headers, case, nodes = workbench
    body = {'revision': case['revision'], 'request_id': 'interrupted', 'question': 'Investigate', 'selected_id': nodes[0]}
    with patch.object(GraphAgent, 'run', side_effect=ValueError('Controlled failure')):
        assert client.post(BASE + '/case/conversation', headers=headers, json=body).status_code == 502
    case = complete(client, headers, case, nodes[0])
    case = client.post(BASE + '/case/decision', headers=headers, json={
        'revision': case['revision'], 'action': 'submit'}).json()
    case = client.post(BASE + '/case/decision', headers=headers, json={
        'revision': case['revision'], 'action': 'approve', 'note': 'Reviewed'}).json()
    exported = client.get(BASE + '/case/export', headers=headers).json()
    frozen = case['versions'][0]
    assert exported['turns'] == frozen['dossier']['turns']
    assert digest(exported['dossier']) == exported['digest']
    case = client.post(BASE + '/case/decision', headers=headers, json={
        'revision': case['revision'], 'action': 'revise'}).json()
    body['revision'] = case['revision']
    response = client.post(BASE + '/case/conversation', headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['turns'][0]['state'] == 'completed'
    recovered = ChangeStore(settings.CHANGE_DB_PATH).get('case')
    assert recovered['versions'][0] == frozen
    assert recovered['versions'][0]['dossier']['turns'][0]['state'] == 'failed'
    assert digest(recovered['versions'][0]['dossier']) == frozen['digest']


def test_export_uses_frozen_turns_and_discloses_legacy_gap(workbench):
    client, headers, case, nodes = workbench
    case = ask(client, headers, case, nodes[0])
    case = complete(client, headers, case, nodes[0])
    case = client.post(BASE + '/case/decision', headers=headers, json={
        'revision': case['revision'], 'action': 'submit'}).json()
    case = client.post(BASE + '/case/decision', headers=headers, json={
        'revision': case['revision'], 'action': 'approve', 'note': 'Reviewed'}).json()
    frozen = case['versions'][0]
    with store().db() as db:
        db.execute("UPDATE turns SET body=? WHERE case_id=?", (encoded({'question': 'Changed live turn'}), 'case'))
    exported = client.get(BASE + '/case/export', headers=headers).json()
    assert exported['turns'] == frozen['dossier']['turns']
    legacy = dict(frozen['dossier']); legacy.pop('turns')
    with store().db() as db:
        db.execute('UPDATE versions SET body=?,digest=? WHERE case_id=?', (encoded(legacy), digest(legacy), 'case'))
    exported = client.get(BASE + '/case/export', headers=headers).json()
    assert exported['turns'] == []
    assert 'Legacy version' in exported['conversation_integrity']
    assert exported['digest'] == digest(legacy)
    assert ChangeStore(settings.CHANGE_DB_PATH).get('case')['versions'][0]['dossier'] == legacy
