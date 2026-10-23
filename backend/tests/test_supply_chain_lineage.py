import json
from unittest.mock import patch

import networkx as nx
import pytest
from fastapi.testclient import TestClient
from main import app
from api import review_routes
from core.config import settings
from core.connection_models import ManagedRepository
from services.sbom_service import inventory, attach

PREDICATE = 'urn:codetrace:vocab:depends_on'


def lockfile():
    return {'lockfileVersion': 3, 'packages': {
        '': {'name': 'application', 'dependencies': {'a': '^1'}, 'devDependencies': {'dev': '^1'}},
        'node_modules/a': {'version': '1.0.0', 'dependencies': {'b': '^2'}},
        'node_modules/b': {'version': '2.0.0', 'dependencies': {'c': '^3'}},
        'node_modules/c': {'version': '3.0.0'}, 'node_modules/dev': {'version': '1.0.0'},
    }}


def test_npm_application_lineage_uses_direct_roots_only(tmp_path):
    (tmp_path / 'package-lock.json').write_text(json.dumps(lockfile()))
    repo = ManagedRepository(id='fixture', label='Application', path=str(tmp_path))
    sbom = inventory(tmp_path, repo)
    assert sbom['root_dependencies'] == ['package-lock.json#node_modules/a', 'package-lock.json#node_modules/dev']
    graph = {'nodes': [{'id': 'app', 'type': 'repository'}], 'edges': [], 'metadata': {}}
    attach(graph, sbom, 'app')
    ids = {node.get('properties', {}).get('name'): node['id'] for node in graph['nodes'][1:]}
    dependencies = nx.DiGraph((edge['source'], edge['target']) for edge in graph['edges'] if edge['type'] == PREDICATE)
    assert nx.shortest_path(dependencies, 'app', ids['c']) == ['app', ids['a'], ids['b'], ids['c']]
    assert not dependencies.has_edge('app', ids['c'])
    assert graph['metadata']['sbom']['root_known'] is True


@pytest.mark.parametrize('root_in_components', [False, True])
def test_cyclonedx_explicit_roots_preserve_lineage(tmp_path, root_in_components):
    components = [{'bom-ref': 'a', 'name': 'a'}, {'bom-ref': 'b', 'name': 'b'}]
    if root_in_components:
        components.append({'bom-ref': 'root', 'name': 'application'})
    document = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'metadata': {'component': {'bom-ref': 'root'}},
                'components': components, 'dependencies': [{'ref': 'root', 'dependsOn': ['a']}, {'ref': 'a', 'dependsOn': ['b']}]}
    (tmp_path / 'sbom.json').write_text(json.dumps(document))
    sbom = inventory(tmp_path, ManagedRepository(id='fixture', label='App', path=str(tmp_path), sbom_path='sbom.json'))
    assert sbom['root_dependencies'] == (['root'] if root_in_components else ['a'])
    assert ('a', 'b') in sbom['dependencies']
    if root_in_components:
        assert ('root', 'a') in sbom['dependencies']


def test_inventory_without_roots_does_not_infer_direct_dependencies(tmp_path):
    document = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': [{'bom-ref': 'a', 'name': 'a'}]}
    (tmp_path / 'sbom.json').write_text(json.dumps(document))
    sbom = inventory(tmp_path, ManagedRepository(id='fixture', label='App', path=str(tmp_path), sbom_path='sbom.json'))
    graph = {'nodes': [{'id': 'app', 'type': 'repository'}], 'edges': [], 'metadata': {}}
    attach(graph, sbom, 'app')
    assert graph['metadata']['sbom']['root_known'] is False
    assert not any(edge['type'] == PREDICATE for edge in graph['edges'])


def test_metadata_only_cyclonedx_root_can_be_a_dependency_target(tmp_path):
    document = {'bomFormat': 'CycloneDX', 'specVersion': '1.5',
                'metadata': {'component': {'bom-ref': 'root', 'name': 'App', 'type': 'application'}},
                'components': [{'bom-ref': 'a', 'name': 'A', 'type': 'library'}],
                'dependencies': [{'ref': 'root', 'dependsOn': ['a']}, {'ref': 'a', 'dependsOn': ['root']}]}
    (tmp_path / 'sbom.json').write_text(json.dumps(document))
    sbom = inventory(tmp_path, ManagedRepository(id='fixture', label='App', path=str(tmp_path), sbom_path='sbom.json'))
    assert sbom['dependencies'] == [('a', 'root')]
    graph = {'nodes': [{'id': 'app', 'type': 'repository'}], 'edges': [], 'metadata': {}}
    attach(graph, sbom, 'app')
    component = next(node['id'] for node in graph['nodes'] if node['type'] == 'sbom_component')
    relationships = {(edge['source'], edge['target']) for edge in graph['edges'] if edge['type'] == PREDICATE}
    assert relationships == {('app', component), (component, 'app')}
    assert graph['metadata']['sbom']['components'] == 1


@pytest.mark.parametrize('only_missing', [False, True])
def test_missing_npm_dependencies_are_retained_as_partial_evidence(tmp_path, only_missing):
    lock = {'lockfileVersion': 3, 'packages': {'': {'dependencies': {'missing': '^2'}}}}
    if not only_missing:
        lock['packages']['']['dependencies']['a'] = '^1'
        lock['packages']['node_modules/a'] = {'version': '1.0.0', 'dependencies': {'nested-missing': '^1'},
                                               'optionalDependencies': {'platform-optional': '^1'}}
    (tmp_path / 'package-lock.json').write_text(json.dumps(lock))
    sbom = inventory(tmp_path, ManagedRepository(id='fixture', label='App', path=str(tmp_path)))
    assert sbom is not None
    expected = {'missing'} if only_missing else {'missing', 'nested-missing', 'platform-optional'}
    assert {item['name'] for item in sbom['unresolved_dependencies']} == expected
    missing = next(item for item in sbom['unresolved_dependencies'] if item['name'] == 'missing')
    assert missing['source'] == '(application)' and missing['kind'] == 'required'
    graph = {'nodes': [{'id': 'app', 'type': 'repository'}], 'edges': [], 'metadata': {}}
    attach(graph, sbom, 'app')
    assert graph['metadata']['sbom']['resolution_complete'] is False
    assert any('Lineage is incomplete' in item for item in graph['metadata']['sbom']['limitations'])
    encoded = next(item['value'] for item in sbom['document']['metadata']['properties']
                   if item['name'] == 'codetrace:unresolved-dependencies')
    assert json.loads(encoded) == sbom['unresolved_dependencies']
    assert all(edge['source'] in {node['id'] for node in graph['nodes']}
               and edge['target'] in {node['id'] for node in graph['nodes']} for edge in graph['edges'])


def test_unknown_cyclonedx_root_dependency_is_rejected(tmp_path):
    document = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': [],
                'metadata': {'component': {'bom-ref': 'root'}}, 'dependencies': [{'ref': 'root', 'dependsOn': ['missing']}]}
    (tmp_path / 'sbom.json').write_text(json.dumps(document))
    with pytest.raises(ValueError, match='unknown dependency'):
        inventory(tmp_path, ManagedRepository(id='fixture', label='App', path=str(tmp_path), sbom_path='sbom.json'))


@pytest.mark.parametrize('relation', ['DESCRIBES', 'DESCRIBED_BY'])
def test_spdx_document_root_relationships(tmp_path, relation):
    source, target = ('SPDXRef-DOCUMENT', 'a') if relation == 'DESCRIBES' else ('a', 'SPDXRef-DOCUMENT')
    document = {'spdxVersion': 'SPDX-2.3', 'SPDXID': 'SPDXRef-DOCUMENT', 'packages': [{'SPDXID': 'a', 'name': 'a'}],
                'relationships': [{'spdxElementId': source, 'relatedSpdxElement': target, 'relationshipType': relation}]}
    (tmp_path / 'sbom.json').write_text(json.dumps(document))
    result = inventory(tmp_path, ManagedRepository(id='fixture', label='App', path=str(tmp_path), sbom_path='sbom.json'))
    assert result['root_dependencies'] == ['a']


def test_managed_sync_and_approved_export_retain_dependency_paths(tmp_path, monkeypatch):
    (tmp_path / 'app.py').write_text('def run(): return 1')
    (tmp_path / 'package-lock.json').write_text(json.dumps(lockfile()))
    monkeypatch.setattr(settings, 'MANAGED_REPOSITORIES', [ManagedRepository(id='fixture', label='App', path=str(tmp_path))])
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', [])
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [])
    monkeypatch.setattr(review_routes, 'store', review_routes.ReviewStore())
    with patch('services.workspace_service.raw_revision', return_value=None), TestClient(app) as client:
        token = client.post('/api/v1/review/session').json()['token']
        headers = {'X-CodeTrace-Session': token}
        response = client.post('/api/v1/workspace/sync', headers=headers, json={'request_id': 'lineage', 'source_id': 'fixture'})
        assert response.status_code == 200, response.text
        record = response.json()
        assert record['result']['metadata']['sbom']['root_dependencies'] == 2
        assert client.get('/api/v1/review/reviews/lineage/export', headers=headers).status_code == 409
        assert client.post('/api/v1/review/reviews/lineage/decision', headers=headers, json={
            'action': 'approved', 'note': 'Lineage fixture', 'revision': record['revision'], 'result_digest': record['result_digest']}).status_code == 200
        exported = client.get('/api/v1/review/reviews/lineage/export', headers=headers)
        assert exported.status_code == 200
        graph = exported.json()['result']
        assert sum(edge['properties'].get('root_dependency', False) for edge in graph['edges']) == 2
        assert graph['metadata']['snapshot_id'] == record['result']['metadata']['snapshot_id']
