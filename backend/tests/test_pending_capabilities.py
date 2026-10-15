import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sqlite3
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import review_routes, oslc_routes
from api.review_routes import Decision
from api.workspace_routes import ManagedSync
from core.config import settings, Settings, PROJECT_ROOT
from core.connection_models import ManagedRepository, OSLCProvider, PipelineProvider
from services.git_isolation import git_command, git_environment
from services.shared_reviews import SQLiteReviewStore
from services.sbom_service import inventory, normalize, attach
from services.oslc_store import OSLCStore, RM
from services.trs_cache import collect_incremental
from services.workspace_service import pipeline_context, build_managed_snapshot
from main import app


def test_git_environment_rejects_host_command_injection(tmp_path, monkeypatch):
    monkeypatch.setenv('GIT_CONFIG_COUNT', '1')
    monkeypatch.setenv('GIT_CONFIG_KEY_0', 'core.sshCommand')
    monkeypatch.setenv('GIT_CONFIG_VALUE_0', 'evil')
    monkeypatch.setenv('GIT_ASKPASS', 'evil')
    monkeypatch.setenv('GIT_ALTERNATE_OBJECT_DIRECTORIES', 'evil')
    env = git_environment(tmp_path / 'home')
    assert 'GIT_CONFIG_COUNT' not in env and 'GIT_ASKPASS' not in env
    assert 'GIT_ALTERNATE_OBJECT_DIRECTORIES' not in env
    assert env['GIT_CONFIG_GLOBAL'] == os.devnull
    assert 'credential.helper=' in git_command()
    token_env = git_environment(tmp_path / 'home', 'test-token')
    assert token_env['GIT_CONFIG_KEY_0'] == 'http.extraHeader'
    assert 'test-token' not in ' '.join(git_command())


@pytest.mark.skipif(not shutil.which('git'), reason='Git is unavailable')
def test_real_git_ignores_global_clean_filter(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'; repo.mkdir()
    env = git_environment(tmp_path / 'safe-home')
    def git(*args):
        return subprocess.run(git_command() + ['-C', str(repo), *args], env=env, capture_output=True, text=True, check=True)
    git('init')
    (repo / '.gitattributes').write_text('*.txt filter=evil\n')
    (repo / 'test.txt').write_text('evidence\n')
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    marker = tmp_path / 'executed'
    config = tmp_path / 'unsafe.gitconfig'
    config.write_text('[filter "evil"]\n\tclean = "echo unsafe > ' + marker.as_posix() + '"\n')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(config))
    env = git_environment(tmp_path / 'safe-home')
    git('status', '--porcelain')
    assert not marker.exists()


def test_shared_sessions_decisions_limits_and_expiry(tmp_path, monkeypatch):
    clock = [100.]
    monkeypatch.setattr(settings, 'SESSION_IDLE_SECONDS', 10)
    monkeypatch.setattr(settings, 'SESSION_MAX_SECONDS', 25)
    path = tmp_path / 'reviews.sqlite'
    first = SQLiteReviewStore(path, clock=lambda: clock[0])
    second = SQLiteReviewStore(path, clock=lambda: clock[0])
    token = first.create()['token']
    request = ManagedSync(request_id='one', source_id='workspace')
    first.reserve(token, request)
    with pytest.raises(HTTPException) as error:
        second.reserve(token, request)
    assert error.value.status_code == 409
    record = second.finish(token, 'one', {'nodes': [], 'edges': []}, 0.1)
    decision = Decision(action='approved', note='reviewed', revision=0, result_digest=record['result_digest'])
    def decide(store):
        return store.decide(token, 'one', decision)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(decide, [first, second]))
    assert all(len(item['audit']) == 2 for item in results)
    first.close()
    assert second.get(token, 'one', export=True)['status'] == 'approved'
    assert token.encode() not in path.read_bytes()
    other = second.create()['token']
    with pytest.raises(HTTPException) as error:
        second.get(other, 'one')
    assert error.value.status_code == 404
    second.end(token)
    with pytest.raises(HTTPException):
        first.info(token)
    clock[0] += 11
    first.prune()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0] == 0


def test_shared_capacity_is_global_and_released(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'MAX_CONCURRENT_ANALYSES', 1)
    first = SQLiteReviewStore(tmp_path / 'reviews.sqlite')
    second = SQLiteReviewStore(tmp_path / 'reviews.sqlite')
    assert first.workers.acquire(blocking=False)
    try:
        assert not second.workers.acquire(blocking=False)
    finally:
        first.workers.release()
    assert second.workers.acquire(blocking=False)
    second.workers.release()


def test_active_worker_reservation_survives_stale_processing_cleanup(tmp_path, monkeypatch):
    clock = [100.]
    monkeypatch.setattr(settings, 'SESSION_IDLE_SECONDS', 10000)
    monkeypatch.setattr(settings, 'SESSION_MAX_SECONDS', 10000)
    store = SQLiteReviewStore(tmp_path / 'reviews.sqlite', clock=lambda: clock[0])
    token = store.create()['token']
    assert store.workers.acquire(blocking=False)
    try:
        store.reserve(token, ManagedSync(request_id='active', source_id='repo'))
        clock[0] += 1000
        store.prune()
        assert store.list(token)[0]['status'] == 'processing'
    finally:
        store.workers.release()
    store.prune()
    assert store.list(token) == []


def test_sbom_inventory_and_approved_export(tmp_path, monkeypatch):
    (tmp_path / 'a.py').write_text('x = 1\n')
    lock = {'lockfileVersion': 3, 'packages': {'': {'name': 'root'},
            'node_modules/a': {'version': '1.0.0', 'dependencies': {'b': '^2'}},
            'node_modules/b': {'version': '2.0.0'}}}
    (tmp_path / 'package-lock.json').write_text(json.dumps(lock))
    repository = ManagedRepository(id='repo', label='Repo', path=str(tmp_path))
    sbom = inventory(tmp_path, repository)
    assert len(sbom['components']) == 2 and len(sbom['dependencies']) == 1
    monkeypatch.setattr(settings, 'MANAGED_REPOSITORIES', [repository])
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', [])
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [])
    graph = build_managed_snapshot('repo')
    assert graph['metadata']['sbom']['components'] == 2
    assert graph['metadata']['nodes'] == len(graph['nodes'])
    assert graph['metadata']['edges'] == len(graph['edges'])
    assert 'sbom_component' in oslc_routes.KINDS
    assert len([item for item in graph['nodes'] if item['type'] == 'sbom_component']) == 2
    store = review_routes.ReviewStore()
    monkeypatch.setattr(review_routes, 'store', store)
    token = store.create()['token']; headers = {'X-CodeTrace-Session': token}
    store.reserve(token, ManagedSync(request_id='graph', source_id='repo'))
    record = store.finish(token, 'graph', graph, 0)
    client = TestClient(app)
    assert client.get('/api/v1/workspace/sbom/graph', headers=headers).status_code == 409
    store.decide(token, 'graph', Decision(action='approved', revision=0, result_digest=record['result_digest']))
    assert client.get('/api/v1/workspace/sbom/graph', headers=headers).json()['document']['bomFormat'] == 'CycloneDX'


def test_sbom_rejects_duplicates_unknown_dependencies_and_escape(tmp_path):
    component = {'bom-ref': 'a', 'name': 'a'}
    document = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': [component, component]}
    with pytest.raises(ValueError): normalize(document)
    document['components'] = [component]
    document['dependencies'] = [{'ref': 'a', 'dependsOn': ['missing']}]
    with pytest.raises(ValueError): normalize(document)
    with pytest.raises(ValueError): inventory(tmp_path, ManagedRepository(id='repo', label='Repo', path=str(tmp_path), sbom_lockfiles=['../outside.json']))


def test_runtime_storage_paths_resolve_from_checkout_not_working_directory():
    config = Settings(_env_file=None, SESSION_DB_PATH='data/reviews-test.sqlite', TRS_CACHE_PATH='data/trs-test.sqlite')
    assert config.SESSION_DB_PATH == PROJECT_ROOT / 'data/reviews-test.sqlite'
    assert config.TRS_CACHE_PATH == PROJECT_ROOT / 'data/trs-test.sqlite'


def test_malformed_sbom_structures_fail_explicitly(tmp_path):
    with pytest.raises(ValueError):
        normalize({'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': [{'name': 'bad', 'bom-ref': []}]})
    (tmp_path / 'package-lock.json').write_text(json.dumps({'lockfileVersion': 3, 'packages': {'node_modules/bad': []}}))
    with pytest.raises(ValueError):
        inventory(tmp_path, ManagedRepository(id='repo', label='Repo', path=str(tmp_path)))


def test_spdx_dependencies_are_directional():
    nodes, edges = normalize({'spdxVersion': 'SPDX-2.3', 'packages': [{'SPDXID': 'A', 'name': 'A'}, {'SPDXID': 'B', 'name': 'B'}],
                              'relationships': [{'spdxElementId': 'B', 'relationshipType': 'DEPENDENCY_OF', 'relatedSpdxElement': 'A'}]})
    assert len(nodes) == 2 and edges == [('A', 'B')]


def test_database_failures_are_not_empty_successes():
    pytest.importorskip('sqlalchemy')
    pytest.importorskip('databases')
    pytest.importorskip('psycopg2')
    from database.connection import EnhancedDatabase, DatabaseUnavailable
    db = EnhancedDatabase()
    with pytest.raises(DatabaseUnavailable): asyncio.run(db.fetch_all('SELECT 1'))
    db.use_fallback = True
    with pytest.raises(DatabaseUnavailable): asyncio.run(db.execute('INSERT'))
    db.use_fallback = False; db.is_connected = True
    db.database = SimpleNamespace(fetch_one=AsyncMock(side_effect=RuntimeError('network lost')))
    with pytest.raises(DatabaseUnavailable): asyncio.run(db.fetch_one('SELECT 1'))
    assert not db.is_connected


def test_ci_follows_same_endpoint_pages_and_rejects_credential_redirect(monkeypatch):
    provider = PipelineProvider(id='ci', label='CI', platform='gitlab', repository_id='repo', endpoint='https://ci.example/pipelines')
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [provider])
    page = json.dumps([{'id': 1, 'sha': 'abc'}]).encode()
    with patch('services.workspace_service.read_response', side_effect=[(page, 'application/json', '?page=2'), (b'[]', 'application/json', None)]) as read:
        runs, statuses = pipeline_context('repo', 'urn:repo', 'abc')
        assert len(runs) == 1 and statuses[0]['pages'] == 2 and statuses[0]['status'] == 'ready'
        assert read.call_args_list[1].args[1] == 'https://ci.example/pipelines?page=2'
    with patch('services.workspace_service.read_response', return_value=(page, 'application/json', 'https://attacker.example/')) as read:
        runs, statuses = pipeline_context('repo', 'urn:repo', 'abc')
        assert not runs and statuses[0]['status'] == 'unavailable' and read.call_count == 1


def test_trs_replays_modification_deletion_recreation_and_new_base(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'TRS_CACHE_PATH', tmp_path / 'trs.sqlite')
    provider = OSLCProvider(id='trs', label='TRS', domain='TRS', endpoint='https://alm.example/trs', allowed_base_url='https://alm.example/', auth_type='none')
    phase = [1]; calls = []
    prefix = '@prefix trs: <http://open-services.net/ns/core/trs#> . @prefix rm: <http://open-services.net/ns/rm#> . @prefix dc: <http://purl.org/dc/terms/> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> . '
    def response(request):
        calls.append(request.url.path)
        if request.url.path == '/trs':
            data = f'<https://alm.example/trs> a trs:TrackedResourceSet; trs:base <https://alm.example/base/{2 if phase[0] >= 5 else 1}>; trs:changeLog <https://alm.example/log> .'
        elif request.url.path.startswith('/base/'):
            data = '<https://alm.example/base/1> rdfs:member <https://alm.example/req>; trs:cutoffEvent rdf:nil .'
        elif request.url.path == '/log':
            kinds = ['Creation', 'Modification', 'Deletion', 'Creation', 'Modification', 'Modification']
            data = ' '.join(f'<https://alm.example/event/{order}> a trs:{kinds[order-1]}; trs:changed <https://alm.example/req>; trs:order {order} .' for order in range(6 if phase[0] == 6 else 1, phase[0]+1))
        elif request.url.path == '/req':
            data = f'<https://alm.example/req> a rm:Requirement; dc:title "Revision {phase[0]}" .'
        else:
            return httpx.Response(404)
        return httpx.Response(200, text=prefix + data, headers={'Content-Type': 'text/turtle'})
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        first = collect_incremental(provider, client)
        assert first[4]['sync_mode'] == 'full' and first[4]['status'] == 'ready'
        phase[0] = 2; calls.clear()
        second = collect_incremental(provider, client)
        assert second[4]['sync_mode'] == 'incremental'
        assert not any(path.startswith('/base/') for path in calls)
        assert next(item for item in second[0] if item['uri'].endswith('/req'))['label'] == 'Revision 2'
        phase[0] = 3; calls.clear()
        deleted = collect_incremental(provider, client)
        assert deleted[2]['https://alm.example/req']['deleted']
        assert '/req' not in calls
        phase[0] = 4
        recreated = collect_incremental(provider, client)
        assert not recreated[2]['https://alm.example/req'].get('deleted')
        phase[0] = 5; calls.clear()
        rebuilt = collect_incremental(provider, client)
        assert rebuilt[4]['sync_mode'] == 'full' and '/base/2' in calls
        phase[0] = 6
        lost = collect_incremental(provider, client)
        assert lost[4]['sync_mode'] == 'full' and lost[4]['checkpoint']['latest_order'] == 6


def test_partial_trs_snapshot_never_advances_a_durable_checkpoint(tmp_path, monkeypatch):
    path = tmp_path / 'trs.sqlite'
    monkeypatch.setattr(settings, 'TRS_CACHE_PATH', path)
    monkeypatch.setattr(settings, 'OSLC_MAX_PAGES', 1)
    provider = OSLCProvider(id='trs', label='TRS', domain='TRS', endpoint='https://alm.example/trs', allowed_base_url='https://alm.example/', auth_type='none')
    content = '<https://alm.example/trs> a <http://open-services.net/ns/core/trs#TrackedResourceSet>; <http://open-services.net/ns/core/trs#base> <https://alm.example/base> .'
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=content, headers={'Content-Type': 'text/turtle'}))) as client:
        assert collect_incremental(provider, client)[4]['status'] == 'partial'
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM checkpoints').fetchone()[0] == 0


@pytest.fixture
def collaboration(tmp_path, monkeypatch):
    store = review_routes.ReviewStore()
    monkeypatch.setattr(review_routes, 'store', store)
    publication = OSLCStore(tmp_path / 'publication.sqlite')
    monkeypatch.setattr(oslc_routes, 'publication_store', lambda: publication)
    provider = OSLCProvider(id='rm', label='RM', domain='RM', endpoint='https://alm.example/query', allowed_base_url='https://alm.example/', auth_type='none', allow_writes=True)
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', [provider])
    token = store.create()['token']
    graph = {'nodes': [{'id': 'https://alm.example/req', 'type': 'requirement', 'properties': {'provider_id': 'rm'}},
                       {'id': 'urn:test:code', 'type': 'file', 'properties': {}}], 'edges': [], 'metadata': {'snapshot_id': 'one'}}
    store.reserve(token, ManagedSync(request_id='graph', source_id='repo'))
    record = store.finish(token, 'graph', graph, 0)
    store.decide(token, 'graph', Decision(action='approved', revision=0, result_digest=record['result_digest']))
    return TestClient(app), {'X-CodeTrace-Session': token}, store, provider


def test_link_proposal_approval_apply_and_isolation(collaboration):
    client, headers, store, provider = collaboration
    with patch.object(oslc_routes.OSLCClient, 'prepare_link', return_value={'expected_etag': '"v1"', 'already_linked': False}):
        response = client.post('/api/v1/oslc/proposals', headers=headers, json={'review_id': 'graph', 'provider_id': 'rm', 'source': 'https://alm.example/req', 'predicate': RM + 'implementedBy', 'target': 'urn:test:code'})
    assert response.status_code == 200, response.text
    proposal = response.json(); path = '/api/v1/oslc/proposals/' + proposal['id']
    with patch.object(oslc_routes.OSLCClient, 'apply_link', return_value={'etag': '"v2"'}) as apply:
        assert client.post(path + '/apply', headers=headers, json={'version': 0}).status_code == 409
        apply.assert_not_called()
        approved = client.post(path + '/decision', headers=headers, json={'version': 0, 'action': 'approved'}).json()
        result = client.post(path + '/apply', headers=headers, json={'version': approved['version']})
        assert result.json()['status'] == 'applied'
        assert apply.call_count == 1
        assert client.post(path + '/apply', headers=headers, json={'version': approved['version']}).status_code == 409
        assert apply.call_count == 1
    other = {'X-CodeTrace-Session': store.create()['token']}
    assert client.get('/api/v1/oslc/proposals', headers=other).json() == []
    assert client.post(path + '/decision', headers=other, json={'version': 0, 'action': 'approved'}).status_code == 404
    assert 'owner_hash' not in client.get('/api/v1/oslc/proposals', headers=headers).text


def test_link_timeout_requires_reconciliation_without_write_retry(collaboration):
    client, headers, _, _ = collaboration
    with patch.object(oslc_routes.OSLCClient, 'prepare_link', return_value={'expected_etag': '"v1"', 'already_linked': False}):
        proposal = client.post('/api/v1/oslc/proposals', headers=headers, json={'review_id': 'graph', 'provider_id': 'rm', 'source': 'https://alm.example/req', 'predicate': RM + 'implementedBy', 'target': 'urn:test:code'}).json()
    path = '/api/v1/oslc/proposals/' + proposal['id']
    approved = client.post(path + '/decision', headers=headers, json={'version': 0, 'action': 'approved'}).json()
    with patch.object(oslc_routes.OSLCClient, 'apply_link', side_effect=httpx.ReadTimeout('uncertain')) as apply:
        uncertain = client.post(path + '/apply', headers=headers, json={'version': approved['version']}).json()
        assert uncertain['status'] == 'unknown'
        assert client.post(path + '/apply', headers=headers, json={'version': uncertain['version']}).status_code == 409
        assert apply.call_count == 1
    with patch.object(oslc_routes.OSLCClient, 'link_exists', return_value=True):
        reconciled = client.post(path + '/reconcile', headers=headers, json={'version': uncertain['version']})
        assert reconciled.json()['status'] == 'applied'


@pytest.mark.parametrize('outcome', ['accepted', 'conflict'])
def test_async_acceptance_and_etag_conflict_are_not_reported_as_applied(collaboration, outcome):
    client, headers, _, _ = collaboration
    with patch.object(oslc_routes.OSLCClient, 'prepare_link', return_value={'expected_etag': '"v1"', 'already_linked': False}):
        proposal = client.post('/api/v1/oslc/proposals', headers=headers, json={'review_id': 'graph', 'provider_id': 'rm', 'source': 'https://alm.example/req', 'predicate': RM + 'implementedBy', 'target': 'urn:test:code'}).json()
    path = '/api/v1/oslc/proposals/' + proposal['id']
    approved = client.post(path + '/decision', headers=headers, json={'version': 0, 'action': 'approved'}).json()
    kwargs = {'return_value': {'status_code': 202}} if outcome == 'accepted' else {
        'side_effect': httpx.HTTPStatusError('conflict', request=httpx.Request('PUT', 'https://alm.example/req'), response=httpx.Response(412))}
    with patch.object(oslc_routes.OSLCClient, 'apply_link', **kwargs):
        result = client.post(path + '/apply', headers=headers, json={'version': approved['version']}).json()
        assert result['status'] == ('unknown' if outcome == 'accepted' else 'conflict')
