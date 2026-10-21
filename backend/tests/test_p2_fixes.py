"""Regression coverage for the reproduced October audit findings (offline)."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from rdflib import Graph, URIRef
from starlette.requests import Request

from api import review_routes
from api.review_routes import ReviewStore
from api.workspace_routes import ManagedSync
from api.oslc_routes import rdf_response
from core.config import PROJECT_ROOT, Settings, settings
from graph.traceability import materialize
from main import app
from services.ai_connection import AIConnection, OllamaREST
from services.oslc_store import OSLCStore, graph_from_body, RM
from services.workspace_service import build_managed_snapshot
from core.connection_models import ManagedRepository
from codegraph_core import CodeGraph

spec = importlib.util.spec_from_file_location('edge_audit', PROJECT_ROOT / 'scripts/audit_edge_cases.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize('case', [
    'config_collision', 'collection', 'cyclic_pages', 'export_tombstone',
    'export_outcome', 'empty_title', 'content_etag', 'spdx_license',
    'optional_bom_ref', 'python_modules', 'local_variables', 'conditional_definitions',
    'property_accessors', 'recommendation_budget', 'false_gap', 'origin_roundtrip',
    'discovery_catalog', 'trs_inline_stub', 'changed_snapshot', 'schema_type',
    'trs_incoming_recreation', 'origin_default_port', 'capacity_bypass', 'orm_source_fields',
])
def test_reproduced_edge_cases(case):
    if case == 'orm_source_fields':
        for dependency in ('sqlalchemy', 'databases', 'psycopg2'):
            pytest.importorskip(dependency)
    getattr(audit, case)()


def test_source_folder_and_explicit_catalog_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv('SOURCE_FOLDER', str(tmp_path))
    monkeypatch.delenv('MANAGED_REPOSITORIES', raising=False)
    configured = Settings(_env_file=None)
    assert configured.MANAGED_REPOSITORIES[0].path == str(tmp_path.resolve())
    monkeypatch.chdir(tmp_path)
    relative = Settings(_env_file=None, SOURCE_FOLDER='external-source')
    assert relative.SOURCE_FOLDER == PROJECT_ROOT / 'external-source'
    explicit = Settings(_env_file=None, SOURCE_FOLDER=str(tmp_path), MANAGED_REPOSITORIES=[
        {'id': 'custom', 'label': 'Explicit', 'path': 'configured-path'}])
    assert explicit.MANAGED_REPOSITORIES[0].path == 'configured-path'
    assert Settings(_env_file=None, MANAGED_REPOSITORIES=[]).MANAGED_REPOSITORIES == []


def test_language_identity_fix_preserves_python_import_links():
    scanner = CodeGraph()
    scanner.scan_sources([{'path': 'a.py', 'content': 'x=1'},
                          {'path': 'a.ts', 'content': 'function x() {}'},
                          {'path': 'b.py', 'content': 'import a'}])
    assert scanner.g.nodes['module:a'].attrs['language'] == 'python'
    assert scanner.g.nodes['module:a.ts'].attrs['language'] == 'ts'
    assert any(target == 'module:a' and kind == 'imports'
               for target, kind, _ in scanner.g.edges['module:b'])


def test_arbitrary_artifact_folder_and_relative_manifests(tmp_path, monkeypatch):
    root = tmp_path / 'Project artifacts Ω'
    root.mkdir()
    (root / 'src').mkdir()
    (root / 'src' / 'app.py').write_text('def external_artifact():\n    return 1\n', encoding='utf-8')
    (root / 'schema.sql').write_text('CREATE TABLE example (id INTEGER);', encoding='utf-8')
    (root / 'notes.txt').write_text('Unsupported text is counted, not executed.', encoding='utf-8')
    (root / 'node_modules').mkdir()
    (root / 'node_modules' / 'ignored.py').write_text('def excluded(): pass', encoding='utf-8')
    (root / 'custom-python-environment').mkdir()
    (root / 'custom-python-environment' / 'pyvenv.cfg').write_text('home = fixture', encoding='utf-8')
    (root / 'custom-python-environment' / 'dependency.py').write_text('def dependency(): pass', encoding='utf-8')
    (root / 'evidence').mkdir()
    (root / 'evidence' / 'trace.json').write_text(json.dumps({
        'repository': {'uri': 'urn:example:project', 'label': 'External artifacts'},
        'resources': [{'uri': 'urn:example:requirement', 'label': 'Requirement', 'kind': 'requirement'}]}), encoding='utf-8')
    (root / 'evidence' / 'sbom.json').write_text(json.dumps({'bomFormat': 'CycloneDX',
        'specVersion': '1.6', 'components': [{'type': 'library', 'name': 'external-package'}]}), encoding='utf-8')
    repository = ManagedRepository(id='external', label='External', path=str(root),
        uri='urn:example:project', manifest_path='evidence/trace.json', sbom_path='evidence/sbom.json')
    monkeypatch.setattr(settings, 'MANAGED_REPOSITORIES', [repository])
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', [])
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [])
    monkeypatch.chdir(tmp_path)
    with patch('services.workspace_service.raw_revision', return_value=None):
        graph = build_managed_snapshot('external')
    assert graph['metadata']['files'] == 2
    assert graph['metadata']['skipped']['excluded_directories'] == 2
    assert graph['metadata']['skipped']['unsupported'] >= 1
    assert any(node['label'] == 'external_artifact' for node in graph['nodes'])
    assert any(node['id'] == 'urn:example:requirement' for node in graph['nodes'])
    assert any(node['type'] == 'sbom_component' and node['properties']['name'] == 'external-package' for node in graph['nodes'])
    assert not any(node['label'] == 'excluded' for node in graph['nodes'])


def test_unavailable_source_does_not_fall_back_to_app_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'MANAGED_REPOSITORIES', [ManagedRepository(
        id='missing', label='Missing', path=str(tmp_path / 'does-not-exist'))])
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        build_managed_snapshot('missing')
    assert error.value.status_code == 422


@pytest.fixture
def connection_session(monkeypatch):
    store = ReviewStore()
    monkeypatch.setattr(review_routes, 'store', store)
    monkeypatch.setattr(settings, 'AI_PROVIDER', 'ollama')
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://127.0.0.1:11434')
    monkeypatch.setattr(settings, 'AI_MODEL', 'central-model')
    monkeypatch.setattr(settings, 'AI_KEY_HEADER', 'api-key')
    monkeypatch.setattr(settings, 'AI_ALLOWED_BASE_URLS', ['https://audit.invalid/ollama'])
    token = store.create()['token']
    store.reserve(token, ManagedSync(request_id='audit', source_id='workspace'))
    store.finish(token, 'audit', audit.graph([audit.node('urn:audit:r', 'function', domain='CODE')]), 0)
    client = TestClient(app)
    yield store, client, {'X-CodeTrace-Session': token}
    store.end(token)


def test_companion_honors_session_disable_and_connection(connection_session):
    _, client, headers = connection_session
    profile = {'enabled': False, 'base_url': 'https://audit.invalid/ollama',
               'model': 'session-model', 'embedding_model': 'embed-model',
               'key_header': 'api-key', 'api_key': 'synthetic-session-key'}
    assert client.put('/api/v1/workspace/ai/config', headers=headers, json=profile).status_code == 200
    body = {'review_id': 'audit', 'question': 'Explain', 'selected_id': 'urn:audit:r'}
    with patch.object(OllamaREST, 'chat', side_effect=AssertionError('disabled connection must not call a model')):
        response = client.post('/api/v1/workspace/companion', headers=headers, json=body)
    assert response.status_code == 200 and response.json()['mode'] == 'evidence'
    profile['enabled'] = True
    assert client.put('/api/v1/workspace/ai/config', headers=headers, json=profile).status_code == 200
    captured = []
    def reply(request):
        captured.append(request)
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'answer': 'A function [E1].', 'citation_ids': ['E1']})}})
    factory = httpx.Client
    with patch('services.ai_connection.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(reply), **kw)):
        response = client.post('/api/v1/workspace/companion', headers=headers, json=body)
    assert response.status_code == 200 and response.json()['model'] == 'session-model'
    assert str(captured[0].url) == 'https://audit.invalid/ollama/api/chat'
    assert captured[0].headers['api-key'] == 'synthetic-session-key'
    assert 'authorization' not in captured[0].headers
    assert json.loads(captured[0].content)['model'] == 'session-model'


def test_companion_central_connection_uses_key_header(connection_session):
    _, client, headers = connection_session
    captured = []
    factory = httpx.Client
    def reply(request):
        captured.append(request)
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'answer': 'A function [E1].', 'citation_ids': ['E1']})}})
    with patch('services.ai_connection.server_secret', return_value='synthetic-central-key'), \
         patch('services.ai_connection.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(reply), **kw)):
        response = client.post('/api/v1/workspace/companion', headers=headers,
            json={'review_id': 'audit', 'question': 'Explain', 'selected_id': 'urn:audit:r'})
    assert response.status_code == 200 and response.json()['mode'] == 'ollama'
    assert captured[0].headers['api-key'] == 'synthetic-central-key'
    assert 'authorization' not in captured[0].headers


@pytest.mark.parametrize('change', [
    {'base_url': 'https://audit.invalid/ollama'}, {'key_header': 'Authorization'}])
def test_blank_key_preserved_only_for_same_provider(connection_session, change):
    store, client, headers = connection_session
    body = {'base_url': settings.AI_BASE_URL, 'model': 'fixture', 'key_header': 'api-key', 'api_key': 'synthetic-origin-key'}
    assert client.put('/api/v1/workspace/ai/config', headers=headers, json=body).status_code == 200
    same = {**body, 'api_key': '', 'keep_key': True}
    assert client.put('/api/v1/workspace/ai/config', headers=headers, json=same).json()['key_configured']
    assert client.put('/api/v1/workspace/ai/config', headers=headers, json={**same, **change}).status_code == 200
    assert store.ai_profile(headers['X-CodeTrace-Session'])['api_key'] == ''


@pytest.mark.parametrize('payload', [[], None, 'invalid', 17])
def test_upstream_response_shape_returns_controlled_error(connection_session, payload):
    _, client, headers = connection_session
    factory = httpx.Client
    with patch('services.ai_connection.httpx.Client', side_effect=lambda **kw: factory(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=json.dumps(payload),
                headers={'Content-Type': 'application/json'})), **kw)):
        response = client.post('/api/v1/workspace/ai/models', headers=headers)
    assert response.status_code == 502


def test_representation_validators_support_conditional_writes(tmp_path):
    store = OSLCStore(tmp_path / 'publication.sqlite')
    store.publish('workspace', audit.graph([audit.node('urn:audit:r'), audit.node('urn:audit:t')]), 0, 'fixture')
    record = store.by_origin('workspace', 'urn:audit:r')
    tags = []
    for media in ('text/turtle', 'application/rdf+xml', 'application/ld+json'):
        request = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [(b'accept', media.encode())]})
        response = rdf_response(graph_from_body(record['body']), request, record['etag'])
        tags.append(response.headers['etag'])
        not_modified = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [
            (b'accept', media.encode()), (b'if-none-match', tags[-1].encode())]})
        assert rdf_response(graph_from_body(record['body']), not_modified, record['etag']).status_code == 304
        # No-op update still validates each representation's strong validator.
        store.update(record['id'], graph_from_body(record['body']), tags[-1], 'fixture')
    assert len(set(tags)) == 3


def test_scoped_provider_links_keep_context(monkeypatch):
    providers = [audit.provider('a', configuration_uri='urn:config:a'),
                 audit.provider('b', configuration_uri='urn:config:b')]
    def ingest(provider, _):
        return ([{'uri': 'urn:req', 'kind': 'requirement_collection', 'label': provider.id}],
                [{'source': {'uri': 'urn:req'}, 'target': {'uri': 'urn:external'},
                  'predicate': RM + 'decomposedBy', 'asserted_by': 'urn:provider'}],
                {'urn:req': {}}, [], {'id': provider.id})
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', providers)
    with patch.object(audit.os, 'ingest_provider', side_effect=ingest):
        resources, links, properties, _, _ = audit.os.collect_oslc('workspace')
    result = materialize(audit.graph(), {'repository': {'uri': 'urn:repo', 'label': 'Repo'},
                         'resources': resources, 'links': links}, 'digest')
    assert len({node['uri'] for node in resources}) == 2
    assert len({link['target']['uri'] for link in links}) == 2
    assert {edge['properties']['configuration_uri'] for edge in result['edges']} == {'urn:config:a', 'urn:config:b'}
    assert {value['concept_uri'] for value in properties.values()} == {'urn:req'}


def test_scoped_identity_translates_back_for_remote_proposals():
    from api import oslc_routes
    source, target = 'urn:audit:scoped-source', 'urn:audit:scoped-target'
    nodes = [audit.node(source, provider_id='p', concept_uri='https://alm.example/source'),
             audit.node(target, concept_uri='https://alm.example/target')]
    request = oslc_routes.LinkProposalRequest(review_id='review', provider_id='p',
        source=source, target=target, predicate=RM + 'decomposedBy')
    with patch.object(oslc_routes, 'session_owner', return_value='owner'), \
         patch.object(review_routes.store, 'get', return_value={'result': audit.graph(nodes), 'result_digest': 'digest'}), \
         patch.object(oslc_routes, 'writable_provider', return_value=audit.provider()), \
         patch.object(oslc_routes, 'OSLCClient') as factory, \
         patch.object(oslc_routes, 'publication_store') as publication:
        remote = factory.return_value.__enter__.return_value
        remote.prepare_link.return_value = {'already_linked': False, 'expected_etag': '"fixture"'}
        publication.return_value.propose.side_effect = lambda _, body: body
        proposal = oslc_routes.propose_link(request, 'token')
    remote.prepare_link.assert_called_once_with('https://alm.example/source', RM + 'decomposedBy', 'https://alm.example/target')
    assert proposal['source'] == 'https://alm.example/source'
    assert proposal['target'] == 'https://alm.example/target'


@pytest.mark.parametrize('route,body', [
    ('graph/local', {'files': [{'path': 'x.py', 'content': 'x=1'}]}),
    ('graph/local/analyze', {'files': [{'path': 'x.py', 'content': 'x=1'}]}),
    ('quality/local', {'files': [{'path': 'x.py', 'content': 'x=1'}]}),
    ('security/local', {'files': [{'path': 'x.py', 'content': 'x=1'}]}),
    ('agent/context', {'files': [{'path': 'x.py', 'content': 'x=1'}], 'query': 'x'}),
])
def test_direct_routes_share_capacity(connection_session, route, body):
    store, client, _ = connection_session
    held = 0
    try:
        while store.workers.acquire(blocking=False):
            held += 1
        assert client.post('/api/v1/' + route, json=body).status_code == 429
    finally:
        for _ in range(held):
            store.workers.release()
    assert client.post('/api/v1/' + route, json=body).status_code == 200
