import json
import subprocess
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from rdflib import URIRef

from core.config import Settings, settings
from core.connection_models import ManagedRepository, PipelineProvider
from services.oslc_store import OSLCStore, graph_from_body, RM
from services.workspace_service import read_repository, pipeline_context


def snapshot(identifier, deleted=False):
    return {'nodes': [{'id': 'urn:req:1', 'type': 'requirement', 'label': 'Requirement',
                       'properties': {'domain': 'RM', 'deleted': deleted}}],
            'edges': [], 'metadata': {'snapshot_id': identifier}}


def test_public_oslc_port_follows_configuration():
    config = Settings(_env_file=None, BACKEND_PORT=8123, FRONTEND_PORT=3123)
    assert config.OSLC_PUBLIC_BASE_URL.endswith(':8123/oslc')


def test_publication_deletion_persistence_and_stable_base(tmp_path):
    path = tmp_path / 'oslc.sqlite'
    store = OSLCStore(path)
    first = store.publish('repo', snapshot('one'), 0, 'reviewer')
    row = store.by_origin('repo', 'urn:req:1')
    old_base = store.base()
    store.publish('repo', snapshot('two', deleted=True), first['version'], 'reviewer')
    assert store.query('repo')[1] == 0
    assert store.events()[0]['action'] == 'Deletion'
    assert json.loads(store.base(old_base['id'])['members']) == [row['id']]
    with pytest.raises(HTTPException) as error:
        OSLCStore(path).resource(row['id'])
    assert error.value.status_code == 410
    assert store.event(store.events()[0]['sequence'])['action'] == 'Deletion'


def test_publication_and_resource_conflicts(tmp_path):
    store = OSLCStore(tmp_path / 'oslc.sqlite')
    store.publish('repo', snapshot('one'), 0, 'reviewer')
    with pytest.raises(HTTPException) as error:
        store.publish('repo', snapshot('two'), 0, 'reviewer')
    assert error.value.status_code == 409
    row = store.by_origin('repo', 'urn:req:1')
    graph = graph_from_body(row['body'])
    graph.add((URIRef(store.uri(row['id'])), URIRef(RM + 'implementedBy'), URIRef('urn:code:1')))
    updated = store.update(row['id'], graph, row['etag'], 'reviewer')
    with pytest.raises(HTTPException) as error:
        store.update(row['id'], graph, row['etag'], 'reviewer')
    assert error.value.status_code == 412
    assert updated['etag'] != row['etag']


def test_capacity_failure_rolls_back_publication(tmp_path, monkeypatch):
    store = OSLCStore(tmp_path / 'oslc.sqlite')
    monkeypatch.setattr(settings, 'OSLC_SERVER_MAX_BYTES', 1)
    with pytest.raises(HTTPException) as error:
        store.publish('repo', snapshot('one'), 0, 'reviewer')
    assert error.value.status_code == 507
    assert store.query('repo')[1] == 0
    assert store.events() == []
    assert store.publication('repo')['version'] == 0


def test_dirty_checkout_does_not_claim_commit_build(tmp_path):
    (tmp_path / 'a.py').write_text('x = 1\n')
    outputs = [subprocess.CompletedProcess([], 0, stdout='a' * 40),
               subprocess.CompletedProcess([], 0, stdout=' M a.py')]
    with patch('services.workspace_service.subprocess.run', side_effect=outputs):
        _, revision = read_repository(ManagedRepository(id='local', label='Local', path=str(tmp_path)))
    assert revision is None


def test_invalid_pipeline_payload_is_atomic(monkeypatch):
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [PipelineProvider(id='ci', label='CI', platform='gitlab',
        repository_id='repo', endpoint='https://gitlab.com/api/v4/projects/1/pipelines')])
    payload = json.dumps([{'id': 1, 'sha': 'abc'}, 42]).encode()
    with patch('services.workspace_service.read_response', return_value=(payload, 'application/json')):
        runs, statuses = pipeline_context('repo', 'urn:repo', 'abc')
    assert runs == []
    assert statuses[0]['status'] == 'unavailable'
