import subprocess
from pathlib import Path
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
    assert response.json()['scoring_basis'].startswith('Not scored:')


@pytest.mark.parametrize('path,content,expected', [
    ('app.js', 'import "library";\nfunction run() { return 1; }', 88),
    ('app.ts', 'function run(): number { return 1; }', 100),
    ('app.py', 'import os\n', 88),
])
def test_quality_scores_available_dependencies_without_documentation(path, content, expected):
    payload = {'files': [{'path': path, 'content': content}]}
    response = client.post('/api/v1/quality/local', json=payload)
    assert response.status_code == 200
    quality = response.json()
    assert quality['overall_score'] == expected
    assert quality['grade'] == ('A' if expected >= 90 else 'B')
    assert quality['scoring_basis'].startswith('Dependency score only:')
    assert quality['metrics'][1]['value'] is None
    assert quality['metrics'][1]['status'] == 'unavailable'
    assert not any('no overall grade' in message for message in quality['recommendations'])
    graph = client.post('/api/v1/graph/local', json=payload).json()
    snapshot_quality = graph['source_assessments']['quality']
    assert snapshot_quality['overall_score'] == quality['overall_score']
    assert snapshot_quality['scoring_basis'] == quality['scoring_basis']


@pytest.mark.parametrize('docstring,coverage', [('', 0), ('    """Documented."""\n', 100)])
def test_documentation_does_not_change_structural_score_or_grade(docstring, coverage):
    response = client.post('/api/v1/quality/local', json={'files': [
        {'path': 'app.py', 'content': f'import os\ndef run():\n{docstring}    return 1\n'}]})
    quality = response.json()
    assert response.status_code == 200
    assert quality['overall_score'] == 88
    assert quality['grade'] == 'B'
    documentation = next(metric for metric in quality['metrics'] if metric['name'] == 'Documentation coverage')
    assert documentation['value'] == coverage
    assert documentation['status'] == ('pass' if coverage == 100 else 'warning')
    assert 'assessed separately' in quality['scoring_basis']


def test_ownership_does_not_count_as_coupling():
    response = client.post('/api/v1/quality/local', json={'files': [{'path': 'a.py', 'content': 'class A:\n    def run(self): pass'}]})
    assert response.json()['metrics'][0]['value'] == 0


@pytest.mark.parametrize('comment', [
    '// import example\n',
    '/* import example\nfunction invented() {} */\n',
    '/** Documentation: import example */\n',
])
def test_javascript_comments_do_not_change_quality_or_graph(comment):
    source = 'import "library";\nfunction run() { return 1; }'
    responses = [client.post('/api/v1/graph/local', json={'files': [
        {'path': 'app.js', 'content': prefix + source}]}).json() for prefix in ['', comment]]
    before, after = [graph['source_assessments']['quality'] for graph in responses]
    assert before['overall_score'] == after['overall_score'] == 88
    assert before['grade'] == after['grade'] == 'B'
    assert before['metrics'] == after['metrics']
    assert [node['label'] for node in responses[1]['nodes'] if node['type'] == 'symbol'] == ['run']
    dependencies = [edge for edge in responses[1]['edges'] if edge['type'] == 'imports']
    assert len(dependencies) == 1


def test_literal_contents_are_not_code_and_quoted_import_target_is_preserved():
    source = ('const sample = "import invented; function fake() {}";\n'
              'const url = "https://example.org";\n'
              'import "library";\nfunction run() {}')
    graph = client.post('/api/v1/graph/local', json={'files': [{'path': 'app.js', 'content': source}]}).json()
    assert len([edge for edge in graph['edges'] if edge['type'] == 'imports']) == 1
    assert [node['label'] for node in graph['nodes'] if node['type'] == 'symbol'] == ['run']
    assert next(node for node in graph['nodes'] if node['type'] == 'symbol')['properties']['start'] == 4


@pytest.mark.parametrize('mixed', [False, True])
def test_failed_python_parsing_withholds_quality_grade(mixed):
    files = [{'path': 'broken.py', 'content': 'def broken(:\n    pass'}]
    if mixed:
        files.append({'path': 'good.py', 'content': 'def run(): pass'})
    graph = client.post('/api/v1/graph/local', json={'files': files}).json()
    quality = graph['source_assessments']['quality']
    assert quality['overall_score'] is None
    assert quality['grade'] == 'N/A'
    assert 'parsing failed' in quality['scoring_basis']
    assert any(node['type'] == 'symbol' for node in graph['nodes'])  # Exploration still works.
    assert next(node for node in graph['nodes'] if node['id'] == 'file:broken.py')['properties']['parse_status'] == 'failed'


@pytest.mark.parametrize('mixed', [False, True])
def test_function_count_is_unavailable_for_heuristic_or_mixed_sources(mixed):
    files = [{'path': 'app.js', 'content': 'function run() {}'}]
    if mixed:
        files.append({'path': 'app.py', 'content': 'def run(): pass'})
    quality = client.post('/api/v1/quality/local', json={'files': files}).json()
    functions = next(metric for metric in quality['metrics'] if metric['name'] == 'Functions')
    assert functions['value'] is None
    assert functions['status'] == 'unavailable'


def test_empty_files_do_not_inflate_quality_score():
    files = [{'path': 'app.py', 'content': 'import os\ndef run(): pass'}]
    baseline = client.post('/api/v1/quality/local', json={'files': files}).json()
    files += [{'path': f'empty{i}.py', 'content': ' \n\t'} for i in range(9)]
    padded = client.post('/api/v1/quality/local', json={'files': files}).json()
    assert baseline['overall_score'] == padded['overall_score'] == 88
    assert baseline['grade'] == padded['grade'] == 'B'
    assert baseline['metrics'] == padded['metrics']


def test_filesystem_scanner_retains_parse_and_content_evidence(tmp_path):
    from codegraph_core import CodeGraph
    from codegraph_core.core import ScanConfig
    (tmp_path / 'broken.py').write_text('def broken(:\n    pass', encoding='utf-8')
    (tmp_path / 'empty.py').write_text(' \n\t', encoding='utf-8')
    (tmp_path / 'app.js').write_text('// import fake\nimport "real";\nfunction run() {}', encoding='utf-8')
    graph = CodeGraph(ScanConfig(excludes=set()))  # This isolated fixture lives under excluded .runtime.
    graph.scan([str(tmp_path)])
    files = {Path(node.attrs['path']).name: node.attrs for node in graph.g.nodes.values() if node.type == 'file'}
    assert files['broken.py']['parse_status'] == 'failed'
    assert files['empty.py']['nonempty'] is False
    assert files['app.js']['parse_status'] == 'heuristic'
    assert sum(kind == 'imports' for edges in graph.g.edges.values() for _, kind, _ in edges) == 1


@pytest.mark.parametrize('path', ['../a.py', '/a.py', 'C:/a.py', 'C:a.py', '.', './', 'file.py:stream', '\\\\host\\share\\a.py'])
def test_paths_are_portably_relative(path):
    response = client.post('/api/v1/graph/local', json={'files': [{'path': path, 'content': ''}]})
    assert response.status_code == 422


@pytest.mark.parametrize('endpoint', ['graph/local', 'quality/local', 'security/local', 'agent/context'])
def test_limits_apply_to_every_source_endpoint(endpoint, monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, 'MAX_LOCAL_FILES', 2)
    payload = {'query': 'test', 'files': [{'path': f'f{i}.py', 'content': ''} for i in range(3)]}
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
