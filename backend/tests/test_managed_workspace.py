import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from api import review_routes
from core.config import Settings, settings
from core.connection_models import ManagedRepository, OSLCProvider, PipelineProvider
from services import oslc_service as oslc
from services.workspace_service import build_managed_snapshot
from services.companion_service import answer_question

RDF = '''
@prefix rm: <http://open-services.net/ns/rm#> .
@prefix am: <http://open-services.net/ns/am#> .
@prefix cm: <http://open-services.net/ns/cm#> .
@prefix oslc: <http://open-services.net/ns/core#> .
@prefix ct: <urn:codetrace:vocab:> .
@prefix trs: <http://open-services.net/ns/core/trs#> .
@prefix ldp: <http://www.w3.org/ns/ldp#> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
<urn:test:req:1> a rm:Requirement; dc:title "Charge customer"; rm:implementedBy <urn:test:code:1>; oslc:instanceShape <urn:test:shape:1> .
<urn:test:req:2> a rm:Requirement; dc:title "Unlinked requirement" .
<urn:test:code:1> ct:codeId "function:source.py::::run" .
<urn:test:architecture:1> a am:Resource; dc:title "Payment architecture"; am:derives <urn:test:req:1> .
<urn:test:shape:1> a oslc:ResourceShape; dc:title "Requirement resource shape" .
<urn:test:change:1> a cm:ChangeRequest; dc:title "Retired change"; cm:implementsRequirement <urn:test:req:1> .
<urn:test:trs:1> a trs:TrackedResourceSet; trs:base <urn:test:base:1> .
<urn:test:base:1> ldp:contains <urn:test:req:1>; trs:cutoffEvent rdf:nil .
<urn:test:event:2> a trs:Modification; trs:changed <urn:test:change:1>; trs:order 2 .
<urn:test:event:1> a trs:Creation; trs:changed <urn:test:change:1>; trs:order 1 .
<urn:test:event:3> a trs:Deletion; trs:changed <urn:test:change:1>; trs:order 3 .
'''


@pytest.fixture
def managed(tmp_path, monkeypatch):
    source = tmp_path / 'repo'
    source.mkdir()
    (source / 'source.py').write_text('def run():\n    return 1\n')
    rdf = tmp_path / 'lifecycle.ttl'
    rdf.write_text(RDF)
    monkeypatch.setattr(settings, 'MANAGED_REPOSITORIES', [ManagedRepository(id='managed', label='Managed source', path=str(source))])
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', [OSLCProvider(id='lifecycle', label='Lifecycle export', domain='TRS',
        file_path=str(rdf), repository_ids=['managed'])])
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [])
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'disabled')
    return source


def test_managed_snapshot_combines_code_and_correct_oslc_domains(managed):
    graph = build_managed_snapshot('managed')
    nodes = {node['id']: node for node in graph['nodes']}
    assert nodes['urn:test:req:1']['properties']['domain'] == 'RM'
    assert nodes['urn:test:architecture:1']['properties']['domain'] == 'AM'
    assert nodes['urn:test:shape:1']['properties']['domain'] == 'SCHEMA'
    assert nodes['urn:test:req:1']['properties']['resource_shape'] == 'urn:test:shape:1'
    assert any(edge['source'] == 'urn:test:req:1' and edge['type'].endswith('implementedBy')
               and nodes[edge['target']]['properties'].get('code_id') == 'function:source.py::::run' for edge in graph['edges'])
    assert graph['metadata']['coverage']['linked_requirements'] == 1
    assert graph['metadata']['coverage']['unlinked_requirements'] == ['urn:test:req:2']


def test_trs_orders_changes_and_keeps_deleted_tombstones(managed):
    graph = build_managed_snapshot('managed')
    assert [event['order'] for event in graph['trs_events']] == [1, 2, 3]
    deleted = next(node for node in graph['nodes'] if node['id'] == 'urn:test:change:1')
    assert deleted['properties']['deleted'] is True
    assert not any(edge['source'] == deleted['id'] and edge['properties']['origin'] == 'lifecycle_assertion' for edge in graph['edges'])
    assert graph['metadata']['connectors'][0]['checkpoint']['latest_order'] == 3


def test_base_cutoff_prevents_old_deletion_from_overriding_new_base(managed, tmp_path, monkeypatch):
    rdf = tmp_path / 'cutoff.ttl'
    rdf.write_text(RDF.replace('trs:cutoffEvent rdf:nil', 'trs:cutoffEvent <urn:test:event:3>'))
    monkeypatch.setattr(settings.OSLC_PROVIDERS[0], 'file_path', str(rdf))
    graph = build_managed_snapshot('managed')
    node = next(node for node in graph['nodes'] if node['id'] == 'urn:test:change:1')
    assert not node['properties'].get('deleted')


def test_catalog_never_discloses_paths_endpoints_or_tokens(managed, monkeypatch):
    provider = settings.OSLC_PROVIDERS[0]
    provider.token_env = 'TEST_PROVIDER_SECRET'
    monkeypatch.setenv('TEST_PROVIDER_SECRET', 'super-secret-value')
    response = TestClient(app).get('/api/v1/workspace/catalog')
    data = response.json()
    serialized = response.text
    assert data['sources'][0]['id'] == 'managed'
    assert data['providers'][0]['credential_configured'] is True
    assert 'super-secret-value' not in serialized and str(managed) not in serialized
    assert 'file_path' not in serialized and 'endpoint' not in serialized


def test_workspace_sync_and_companion_are_bound_to_session_review(managed, monkeypatch):
    monkeypatch.setattr(review_routes, 'store', review_routes.ReviewStore())
    client = TestClient(app)
    token = client.post('/api/v1/review/session').json()['token']
    headers = {'X-CodeTrace-Session': token}
    response = client.post('/api/v1/workspace/sync', headers=headers, json={'request_id': 'managed-1', 'source_id': 'managed'})
    assert response.status_code == 200, response.text
    record = response.json()
    assert record['status'] == 'pending'
    question = {'review_id': record['id'], 'question': 'Where are requirement traceability gaps?'}
    assert client.post('/api/v1/workspace/companion', json=question).status_code == 401
    answer = client.post('/api/v1/workspace/companion', headers=headers, json=question).json()
    assert answer['mode'] == 'evidence'
    assert any(item['node_id'] == 'urn:test:req:2' for item in answer['citations'])
    assert 'Unlinked requirement' in answer['answer']
    assert client.get('/api/v1/review/reviews/managed-1/export', headers=headers).status_code == 409
    assert client.post('/api/v1/workspace/sync', headers=headers,
                       json={'request_id': 'injection', 'source_id': 'managed', 'project_url': 'https://untrusted.example/repo'}).status_code == 422


def test_unknown_source_never_reads_user_selected_server_path(managed):
    with pytest.raises(Exception) as error:
        build_managed_snapshot('../../private')
    assert error.value.status_code == 404


@pytest.mark.parametrize('document,kind', [
    (b'{"@context":"https://untrusted.example/context","@id":"urn:a"}', 'application/ld+json'),
    (b'<!DOCTYPE rdf [<!ENTITY x SYSTEM "file:///private">]><rdf/>', 'application/rdf+xml'),
    (b'not valid turtle', 'text/turtle'),
])
def test_rdf_parser_rejects_external_context_entities_and_invalid_data(document, kind):
    with pytest.raises(ValueError):
        oslc.parse_rdf(document, kind)


def test_provider_follows_http_link_pages_and_reports_limits(monkeypatch):
    provider = OSLCProvider(id='rm', label='Requirements', domain='RM', endpoint='https://alm.test/api/page1', allowed_base_url='https://alm.test/api/')
    visited = []
    def handler(request):
        visited.append(str(request.url))
        data = '<urn:req:1> a <http://open-services.net/ns/rm#Requirement> .' if request.url.path.endswith('page1') else '<urn:req:2> a <http://open-services.net/ns/rm#Requirement> .'
        return httpx.Response(200, text=data, headers={'content-type': 'text/turtle', **({'Link': '</api/page2>; rel="next"'} if request.url.path.endswith('page1') else {})})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        resources, _, _, _, status = oslc.ingest_provider(provider, client)
    assert len(resources) == 2 and len(visited) == 2 and status['status'] == 'ready'
    monkeypatch.setattr(settings, 'OSLC_MAX_PAGES', 1)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        _, _, _, _, status = oslc.ingest_provider(provider, client)
    assert status['status'] == 'partial' and status['checkpoint']['complete'] is False


@pytest.mark.parametrize('url', ['https://evil.test/api/resource', 'https://alm.test/private', 'https://alm.test/api/%2e%2e/private'])
def test_linked_provider_resources_cannot_escape_configured_prefix(url):
    provider = OSLCProvider(id='rm', label='Requirements', domain='RM', endpoint='https://alm.test/api/query', allowed_base_url='https://alm.test/api/')
    with pytest.raises(ValueError):
        oslc.allowed_url(provider, url)


def test_ollama_answer_requires_real_evidence_citations(managed, monkeypatch):
    graph = build_managed_snapshot('managed')
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'ollama')
    monkeypatch.setattr(settings, 'AI_MODEL', 'test-local-model')
    real_client = httpx.Client
    def valid(request):
        payload = json.loads(request.content)
        assert request.url.host == '127.0.0.1' and payload['stream'] is False
        return httpx.Response(200, json={'message': {'content': json.dumps({'answer': 'This requirement has no imported trace link [E1].', 'citation_ids': ['E1']})}})
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(valid), **kwargs))
    result = answer_question(graph, 'Explain trace gaps', 'urn:test:req:2')
    assert result['mode'] == 'ollama' and result['citations'][0]['node_id'] == 'urn:test:req:2'
    def hallucinated(_):
        return httpx.Response(200, json={'message': {'content': '{"answer":"Invented result [E999]","citation_ids":["E999"]}'}})
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(hallucinated), **kwargs))
    result = answer_question(graph, 'Explain trace gaps', 'urn:test:req:2')
    assert result['mode'] == 'evidence' and result['warning']


def test_explicit_native_ollama_endpoint_preserves_configured_scheme():
    for scheme in ('http', 'https'):
        configured = Settings(_env_file=None, AI_PROVIDER='ollama', AI_MODEL='test',
                              AI_BASE_URL=f'{scheme}://models.example/ollama', AI_ALLOWED_BASE_URLS=[])
        assert configured.AI_BASE_URL == f'{scheme}://models.example/ollama'
