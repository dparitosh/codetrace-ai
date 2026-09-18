import subprocess
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_quality_does_not_grade_unmeasurable_input():
    response = client.post('/api/v1/quality/local', json={'files': [{'path': 'empty.py', 'content': ''}]})
    assert response.status_code == 200
    assert response.json()['overall_score'] is None
    assert response.json()['grade'] == 'N/A'


def test_ownership_does_not_count_as_coupling():
    response = client.post('/api/v1/quality/local', json={'files': [{'path': 'a.py', 'content': 'class A:\n    def run(self): pass'}]})
    assert response.json()['metrics'][0]['value'] == 0


@pytest.mark.parametrize('path', ['../a.py', '/a.py', 'C:/a.py', 'C:a.py', '.', './', 'file.py:stream', '\\\\host\\share\\a.py'])
def test_paths_are_portably_relative(path):
    response = client.post('/api/v1/graph/local', json={'files': [{'path': path, 'content': ''}]})
    assert response.status_code == 422


@pytest.mark.parametrize('endpoint', ['graph/local', 'quality/local', 'security/local', 'agent/context'])
def test_limits_apply_to_every_source_endpoint(endpoint):
    payload = {'query': 'test', 'files': [{'path': f'f{i}.py', 'content': ''} for i in range(501)]}
    assert client.post('/api/v1/' + endpoint, json=payload).status_code == 413


def test_duplicate_normalized_paths_are_rejected():
    payload = {'files': [{'path': 'src/a.py', 'content': ''}, {'path': 'src\\a.py', 'content': ''}]}
    assert client.post('/api/v1/graph/local', json=payload).status_code == 422


def test_graph_edges_have_nodes_and_excludes_apply():
    payload = {'files': [
        {'path': 'src/a.py', 'content': 'import os\nclass A(Base):\n    pass'},
        {'path': 'node_modules/b.py', 'content': 'def unwanted(): pass'},
    ]}
    response = client.post('/api/v1/graph/local', json=payload)
    assert response.status_code == 200
    graph = response.json()
    ids = {node['id'] for node in graph['nodes']}
    assert all(edge['source'] in ids and edge['target'] in ids for edge in graph['edges'])
    assert not any('unwanted' in node['id'] for node in graph['nodes'])
    assert graph['metadata']['files'] == 1


def test_audit_preserves_same_named_functions_and_query_ranking():
    payload = {'query': 'target', 'max_symbols': 1, 'files': [
        {'path': 'src/a.py', 'content': 'def run(): pass'},
        {'path': 'src/b.py', 'content': 'def run(): pass\ndef target(): pass'},
    ]}
    response = client.post('/api/v1/agent/context', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['symbols'][0]['name'] == 'target'
    assert len(data['audit']['uncalled_functions']) == 3


@pytest.mark.parametrize('url', [
    'https://user:secret@gitlab.com/group/project',
    'https://gitlab.com/group/project?token=secret',
    'https://gitlab.com/group/project/-/tree/main',
    'https://gitlab.com:8443/group/project',
    'https://example.com/group/project',
])
def test_gitlab_rejects_unsupported_urls_without_cloning(url):
    with patch('api.graph_routes.subprocess.run') as clone:
        assert client.post('/api/v1/graph/gitlab', json={'project_url': url}).status_code == 400
        clone.assert_not_called()


def test_gitlab_clone_and_scan_use_real_source(tmp_path):
    def fake_clone(command, **kwargs):
        from pathlib import Path
        destination = Path(command[-1])
        destination.mkdir()
        (destination / 'example.py').write_text('def hello(): pass', encoding='utf-8')
        assert kwargs['env']['GIT_TERMINAL_PROMPT'] == '0'
        assert 'http.followRedirects=false' in command
        return subprocess.CompletedProcess(command, 0)

    with patch('api.graph_routes.subprocess.run', side_effect=fake_clone):
        response = client.post('/api/v1/graph/gitlab', json={'project_url': 'https://gitlab.com/group/project'})
    assert response.status_code == 200
    assert any(node['label'] == 'hello' for node in response.json()['nodes'])
    assert any(node['id'] == 'file:example.py' for node in response.json()['nodes'])
