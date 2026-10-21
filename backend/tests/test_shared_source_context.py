from unittest.mock import patch
import pytest
from api.graph_routes import LocalGraphRequest, build_graph_from_files
from services.ai_connection import AIConnection, OllamaREST
from services.agent_workspace import GraphAgent


def test_snapshot_assessments_use_only_graph_sources():
    graph = build_graph_from_files(LocalGraphRequest(files=[
        {'path': 'src/app.py', 'content': 'def run(value):\n    return eval(value)\n'},
        {'path': 'node_modules/excluded.py', 'content': 'eval(secret)'},
        {'path': 'unselected.txt', 'content': 'eval(other)'},
    ]))
    assessments = graph['source_assessments']
    assert assessments['source_digest'] == graph['metadata']['source_digest']
    assert assessments['summary']['total_files'] == 1
    assert assessments['security']['files_scanned'] == 1
    assert assessments['security']['total_findings'] == 1
    assert assessments['security']['findings'][0]['file'] == 'src/app.py'
    assert next(metric for metric in assessments['quality']['metrics'] if metric['name'] == 'Functions')['value'] == 1


def test_managed_snapshot_retains_bound_assessments(tmp_path, monkeypatch):
    from core.config import settings
    from core.connection_models import ManagedRepository
    from services.workspace_service import build_managed_snapshot
    (tmp_path / 'app.py').write_text('def run(value):\n    return eval(value)\n', encoding='utf-8')
    monkeypatch.setattr(settings, 'MANAGED_REPOSITORIES', [ManagedRepository(id='fixture', label='Fixture', path=str(tmp_path))])
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', [])
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [])
    with patch('services.workspace_service.raw_revision', return_value=None):
        graph = build_managed_snapshot('fixture')
    assert graph['source_assessments']['summary']['total_files'] == graph['metadata']['files'] == 1
    findings = graph['source_assessments']['security']['findings']
    assert findings and any(node['type'] == 'file' and node['properties']['path'] == findings[0]['file'] for node in graph['nodes'])


def test_agent_domain_and_source_evidence_share_snapshot():
    graph = {'nodes': [
        {'id': 'urn:test:code', 'label': 'Brake code', 'type': 'file', 'properties': {'domain': 'CODE', 'path': 'brake.py'}},
        {'id': 'urn:test:req', 'label': 'Brake requirement', 'type': 'requirement', 'properties': {'domain': 'RM'}},
    ], 'edges': [], 'metadata': {'snapshot_id': 'fixture'}, 'source_assessments': {
        'summary': {'total_files': 1}, 'security': {'findings': [{'file': 'brake.py', 'rule': 'dynamic-execution', 'line': 1}]}}}
    rest = OllamaREST(AIConnection(base_url='http://127.0.0.1:11434', model='offline', enabled=False))
    result = GraphAgent(graph, rest).run('Brake', domain='RM')
    assert result['trace'][0]['arguments']['domain'] == 'RM'
    assert result['highlight_ids'] == ['urn:test:req']
    assert result['snapshot_id'] == 'fixture'
    inspected = GraphAgent(graph, rest).tool('inspect_resource', {'node_id': 'urn:test:code'})
    assert inspected['source_findings'][0]['file'] == 'brake.py'
    assert inspected['evidence'][0]['node_id'] == 'urn:test:code'
