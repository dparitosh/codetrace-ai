import base64
import json
from unittest.mock import patch

import httpx
import pytest
from core.config import Settings, settings
from core.connection_models import ManagedRepository
from services.sbom_service import inventory, normalize, root_dependencies, attach, license_choices, sri_hashes
from services.advisory_service import advisory_evidence


def test_spdx_roots_union_document_describes_with_relationships_and_reject_unknown():
    doc = {'spdxVersion': 'SPDX-2.3', 'SPDXID': 'SPDXRef-DOCUMENT',
           'documentDescribes': ['a', 'a'], 'packages': [{'SPDXID': 'a', 'name': 'A'}, {'SPDXID': 'b', 'name': 'B'}],
           'relationships': [{'spdxElementId': 'SPDXRef-DOCUMENT', 'relationshipType': 'DESCRIBES', 'relatedSpdxElement': 'b'}]}
    nodes, _ = normalize(doc)
    assert root_dependencies(doc, nodes) == ['a', 'b']
    doc['documentDescribes'] = ['unknown']
    with pytest.raises(ValueError, match='unknown dependency'):
        root_dependencies(doc, nodes)


@pytest.mark.parametrize('value', ['MIT', '(MIT OR CC0-1.0)', 'MIT AND Apache-2.0', 'GPL-2.0-only WITH Classpath-exception-2.0', 'LicenseRef-Customer'])
def test_spdx_license_expressions_preserve_semantics(value):
    assert license_choices(value) == [{'expression': value}]


def test_unknown_license_remains_an_unverified_name():
    assert license_choices('Customer free form license') == [{'license': {'name': 'Customer free form license'}}]


def test_lockfile_purls_hashes_and_peer_paths_are_retained_in_graph(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'VULNERABILITY_PROVIDER', 'disabled')
    raw = b'x' * 64
    lock = {'lockfileVersion': 3, 'packages': {
        '': {'dependencies': {'consumer': '1'}},
        'node_modules/consumer': {'version': '1.0.0', 'peerDependencies': {'@scope/peer': '*', 'absent': '*'},
                                  'peerDependenciesMeta': {'absent': {'optional': True}}},
        'node_modules/@scope/peer': {'version': '2.0.0', 'integrity': 'sha512-' + base64.b64encode(raw).decode(), 'license': 'MIT'},
    }}
    (tmp_path / 'package-lock.json').write_text(json.dumps(lock))
    result = inventory(tmp_path, ManagedRepository(id='audit', label='Audit', path=str(tmp_path)))
    peer = next(c for c in result['components'] if c['name'] == '@scope/peer')
    assert peer['purl'] == 'pkg:npm/%40scope/peer@2.0.0'
    assert peer['hashes'] == [{'alg': 'SHA-512', 'content': raw.hex()}]
    assert ('package-lock.json#node_modules/consumer', peer['ref']) in result['dependencies']
    assert not result['unresolved_dependencies']
    graph = {'nodes': [{'id': 'app', 'type': 'repository'}], 'edges': [], 'metadata': {}}
    attach(graph, result, 'app')
    assert next(n for n in graph['nodes'] if n.get('properties', {}).get('name') == '@scope/peer')['properties']['hashes'] == peer['hashes']
    assert graph['metadata']['sbom']['advisory_lookup']['status'] == 'disabled'


def test_imported_checksum_evidence_is_not_discarded():
    digest = {'alg': 'SHA-256', 'content': 'a' * 64}
    nodes, _ = normalize({'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': [{'name': 'A', 'hashes': [digest]}]})
    assert nodes[0]['hashes'] == [digest]
    nodes, _ = normalize({'spdxVersion': 'SPDX-2.3', 'packages': [{'name': 'A', 'SPDXID': 'a', 'checksums': [{'algorithm': 'SHA256', 'checksumValue': 'b' * 64}]}]})
    assert nodes[0]['hashes'] == [{'alg': 'SHA256', 'content': 'b' * 64}]
    with pytest.raises(ValueError):
        sri_hashes('sha512-bad-base64')


def test_disabled_lookup_never_constructs_network_client(monkeypatch):
    monkeypatch.setattr(settings, 'VULNERABILITY_PROVIDER', 'disabled')
    with patch('services.advisory_service.httpx.Client', side_effect=AssertionError('network must be disabled')):
        assert advisory_evidence({'components': []})['status'] == 'disabled'


@pytest.fixture
def enabled_lookup(monkeypatch):
    monkeypatch.setattr(settings, 'VULNERABILITY_PROVIDER', 'osv-compatible')
    monkeypatch.setattr(settings, 'VULNERABILITY_API_URL', 'http://customer.invalid/advisories/batch')
    monkeypatch.setattr(settings, 'VULNERABILITY_TOKEN_ENV', 'SYNTHETIC_AUDIT_TOKEN')
    monkeypatch.setattr(settings, 'VULNERABILITY_BATCH_SIZE', 1)
    monkeypatch.setenv('SYNTHETIC_AUDIT_TOKEN', 'fixture-secret')
    return {'components': [{'ref': 'a', 'purl': 'pkg:npm/a@1.0.0', 'version': '1.0.0'}]}


def test_customer_endpoint_and_auth_are_used_without_public_fallback(enabled_lookup):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={'results': [{'vulns': [{'id': 'CUSTOM-1'}]}]})
    factory = httpx.Client
    with patch('services.advisory_service.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(respond), **kw)):
        result = advisory_evidence(enabled_lookup)
    assert str(calls[0].url) == 'http://customer.invalid/advisories/batch'
    assert calls[0].headers['Authorization'] == 'Bearer fixture-secret'
    assert json.loads(calls[0].content)['queries'][0]['package']['purl'] == 'pkg:npm/a@1.0.0'
    assert result['status'] == 'complete' and result['matches'] == [{'component_ref': 'a', 'advisory_id': 'CUSTOM-1'}]
    assert 'fixture-secret' not in json.dumps(result)


@pytest.mark.parametrize('response', [httpx.Response(500), httpx.Response(302, headers={'Location': 'https://api.osv.dev/v1/querybatch'}),
    httpx.Response(200, json={'results': []}), httpx.Response(200, json={'results': [{'vulns': ['invalid']}]}),
    httpx.Response(200, content=b'not json')])
def test_invalid_or_redirected_customer_response_is_not_reported_clean(enabled_lookup, response):
    factory = httpx.Client
    with patch('services.advisory_service.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(lambda request: response), **kw)):
        result = advisory_evidence(enabled_lookup)
    assert result['status'] == 'unavailable' and result['checked_components'] == 0


def test_advisory_partial_batches_keep_checked_evidence(enabled_lookup):
    enabled_lookup['components'].append({'ref': 'b', 'purl': 'pkg:npm/b@1', 'version': '1'})
    count = 0
    def respond(request):
        nonlocal count
        count += 1
        if count == 2:
            raise httpx.ReadTimeout('fixture-secret', request=request)
        return httpx.Response(200, json={'results': [{}]})
    factory = httpx.Client
    with patch('services.advisory_service.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(respond), **kw)):
        result = advisory_evidence(enabled_lookup)
    assert result['status'] == 'partial' and result['checked_components'] == 1
    assert 'fixture-secret' not in json.dumps(result)


def test_response_bound_is_enforced(enabled_lookup, monkeypatch):
    monkeypatch.setattr(settings, 'VULNERABILITY_MAX_RESPONSE_BYTES', 1000)
    factory = httpx.Client
    with patch('services.advisory_service.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x'*1001)), **kw)):
        assert advisory_evidence(enabled_lookup)['status'] == 'unavailable'


def test_customer_configuration_defaults_disabled_and_http_is_configurable():
    config = Settings(_env_file=None, AI_PROVIDER='disabled', VULNERABILITY_PROVIDER='disabled')
    assert config.VULNERABILITY_PROVIDER == 'disabled' and not config.VULNERABILITY_API_URL
    config = Settings(_env_file=None, AI_PROVIDER='disabled', VULNERABILITY_PROVIDER='osv-compatible', VULNERABILITY_API_URL='http://customer.invalid/batch')
    assert config.VULNERABILITY_API_URL.startswith('http:')
    with pytest.raises(ValueError, match='VULNERABILITY_REQUIRE_HTTPS'):
        Settings(_env_file=None, AI_PROVIDER='disabled', VULNERABILITY_REQUIRE_HTTPS=True, VULNERABILITY_API_URL='http://customer.invalid/batch')
    with pytest.raises(ValueError, match='requires VULNERABILITY_API_URL'):
        Settings(_env_file=None, AI_PROVIDER='disabled', VULNERABILITY_PROVIDER='osv-compatible', VULNERABILITY_API_URL='')
