from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from main import app
from graph.traceability import CT, RM, RDF, code_uri

client = TestClient(app)
REPO = 'urn:example:repository:billing'
PROVIDER = 'https://alm.example.test/export/1'
REQ = 'https://alm.example.test/requirements/42'
METHOD = 'function:src/billing.py::Billing.::charge'


@pytest.fixture
def payload():
    resources = [{'uri': REQ, 'kind': 'requirement', 'label': 'Charge customer'}]
    resources += [{'uri': 'urn:example:' + kind, 'kind': kind, 'label': kind.title()}
                  for kind in ('feature', 'variant', 'product', 'test')]

    def link(source, predicate, target):
        return {'source': {'uri': source}, 'predicate': predicate, 'target': target, 'asserted_by': PROVIDER}

    return {'source': {'files': [{'path': 'src/billing.py', 'content': 'class Billing:\n    def charge(self):\n        return 1\n'}]},
            'manifest': {'repository': {'uri': REPO, 'label': 'Billing', 'revision': 'release-1'},
                         'configuration_uri': 'urn:example:configuration:premium', 'resources': resources,
                         'links': [link(REQ, RM + 'implementedBy', {'code_id': METHOD}),
                                   link(REQ, RM + 'validatedBy', {'uri': 'urn:example:test'}),
                                   link(REQ, CT + 'specifiesFeature', {'uri': 'urn:example:feature'}),
                                   link('urn:example:feature', CT + 'hasVariant', {'uri': 'urn:example:variant'}),
                                   link('urn:example:variant', CT + 'includedIn', {'uri': 'urn:example:product'})]}}


def build(payload):
    response = client.post('/api/v1/trace/materialize', json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_combines_real_code_hierarchy_and_lifecycle(payload):
    data = build(payload)
    nodes = {node['id']: node for node in data['nodes']}
    method = code_uri(REPO, METHOD)
    assert nodes[method]['type'] == 'method'
    assert {node['type'] for node in nodes.values()} >= {'repository', 'package', 'file', 'class', 'method', 'requirement', 'test', 'feature', 'variant', 'product'}
    assert all(edge['source'] in nodes and edge['target'] in nodes for edge in data['edges'])
    assert any(edge['source'] == REQ and edge['target'] == method and edge['type'] == RM + 'implementedBy' for edge in data['edges'])
    assert any(edge['target'] == method and edge['type'] == CT + 'contains' and nodes[edge['source']]['type'] == 'class' for edge in data['edges'])
    assert data['metadata']['diagnostics'] == []


def test_trace_reaches_product_and_test_with_bounded_witness_paths(payload):
    query = {**payload, 'start': {'code_id': METHOD}, 'depth': 6,
             'predicates': [RM + 'implementedBy', RM + 'validatedBy', CT + 'specifiesFeature', CT + 'hasVariant', CT + 'includedIn']}
    data = client.post('/api/v1/trace/query', json=query).json()
    assert {node['type'] for node in data['nodes']} >= {'test', 'requirement', 'product'}
    assert data['metadata']['witness_paths']['urn:example:product'] == [code_uri(REPO, METHOD), REQ, 'urn:example:feature', 'urn:example:variant', 'urn:example:product']
    small = client.post('/api/v1/trace/query', json={**query, 'max_nodes': 2}).json()
    assert len(small['nodes']) == 2 and small['metadata']['truncated'] is True
    outgoing = client.post('/api/v1/trace/query', json={**query, 'direction': 'outgoing'}).json()
    assert len(outgoing['nodes']) == 1


def test_snapshot_and_ids_are_reproducible_but_content_sensitive(payload):
    first = build(payload)
    assert build(payload)['metadata']['snapshot_id'] == first['metadata']['snapshot_id']
    modified = deepcopy(payload)
    modified['source']['files'][0]['content'] = modified['source']['files'][0]['content'].replace('return 1', 'return 2')
    second = build(modified)
    assert first['metadata']['snapshot_id'] != second['metadata']['snapshot_id']
    assert {node['id'] for node in first['nodes']} == {node['id'] for node in second['nodes']}
    assert code_uri(REPO, METHOD) != code_uri('urn:example:other-repo', METHOD)


def test_unknown_resource_is_reported_and_unknown_code_is_rejected(payload):
    payload['manifest']['links'][0]['target'] = {'uri': 'https://external.example.test/unimported'}
    data = build(payload)
    assert data['metadata']['diagnostics'][0]['kind'] == 'unresolved_resource'
    payload['manifest']['links'][0]['target'] = {'code_id': 'does-not-exist'}
    assert client.post('/api/v1/trace/materialize', json=payload).status_code == 422


def test_duplicate_resources_and_ambiguous_endpoints_rejected(payload):
    invalid = deepcopy(payload)
    invalid['manifest']['resources'].append(invalid['manifest']['resources'][0])
    assert client.post('/api/v1/trace/materialize', json=invalid).status_code == 422
    payload['manifest']['links'][0]['target']['uri'] = REQ
    assert client.post('/api/v1/trace/materialize', json=payload).status_code == 422


def test_jsonld_preserves_oslc_direction_and_assertion_provenance(payload):
    response = client.post('/api/v1/trace/jsonld', json=payload)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/ld+json')
    records = response.json()['@graph']
    requirement = next(item for item in records if item['@id'] == REQ)
    assert requirement[RM + 'implementedBy'] == [{'@id': code_uri(REPO, METHOD)}]
    assertion = next(item for item in records if item.get(RDF + 'predicate') == {'@id': RM + 'implementedBy'})
    assert assertion[CT + 'asserted_by'] == {'@id': PROVIDER}
    assert assertion[CT + 'configuration_uri'] == {'@id': 'urn:example:configuration:premium'}


def test_agent_context_contains_lifecycle_evidence(payload):
    response = client.post('/api/v1/agent/context', json={**payload['source'], 'query': 'charge', 'trace_manifest': payload['manifest']})
    assert response.status_code == 200, response.text
    trace = response.json()['lifecycle_trace']
    assert REQ in {node['id'] for node in trace['nodes']}
    assert 'urn:example:product' in {node['id'] for node in trace['nodes']}


def test_assertions_are_idempotent(payload):
    first = build(payload)
    payload['manifest']['links'].append(payload['manifest']['links'][0])
    assert build(payload)['edges'] == first['edges']


def test_contract_is_in_openapi():
    schema = client.get('/openapi.json').json()
    assert '/api/v1/trace/materialize' in schema['paths']
    assert '/api/v1/trace/query' in schema['paths']
    assert 'TraceManifest' in schema['components']['schemas']


def test_jsonld_link_predicate_can_overlap_literal_property(payload):
    payload['manifest']['links'][0]['predicate'] = 'http://www.w3.org/2000/01/rdf-schema#label'
    response = client.post('/api/v1/trace/jsonld', json=payload)
    assert response.status_code == 200
    requirement = next(item for item in response.json()['@graph'] if item['@id'] == REQ)
    values = requirement['http://www.w3.org/2000/01/rdf-schema#label']
    assert 'Charge customer' in values
    assert {'@id': code_uri(REPO, METHOD)} in values
