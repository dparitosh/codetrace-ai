from codegraph_core.core import CodeGraph
import pytest


def test_python_scanner_preserves_hierarchy_docstrings_variables_and_calls():
    graph = CodeGraph()
    graph.scan_sources([{"path": "src/service.py", "content": '''
VERSION = "1"

class Service:
    """Coordinates work."""
    enabled = True

    def run(self, request):
        """Run the request."""
        return helper(request)

def helper(request):
    return request
'''}])

    classes = [node for node in graph.g.nodes.values() if node.type == "class"]
    functions = [node for node in graph.g.nodes.values() if node.type == "function"]
    variables = [node for node in graph.g.nodes.values() if node.type == "variable"]
    assert classes[0].attrs["docstring"] == "Coordinates work."
    assert any(node.attrs["name"] == "request" and node.attrs["scope"] == "parameter" for node in variables)
    assert any(node.attrs["name"] == "VERSION" for node in variables)
    run_id = next(node.id for node in functions if node.attrs["name"] == "run")
    helper_id = next(node.id for node in functions if node.attrs["name"] == "helper")
    assert any(target == helper_id and relationship == "calls" for target, relationship, _ in graph.g.edges[run_id])


@pytest.mark.parametrize('body', [
    'def invoke(target):\n    target()',
    'def invoke():\n    target = lambda: None\n    target()',
    'def invoke():\n    from other import target\n    target()',
    'def invoke():\n    def target(): pass\n    target()',
])
def test_shadowed_names_do_not_resolve_to_module_function(body):
    graph = CodeGraph()
    graph.scan_sources([{'path': 'a.py', 'content': 'def target(): pass\n' + body}])
    calls = [target for edges in graph.g.edges.values() for target, relation, _ in edges if relation == 'calls']
    assert 'function:a.py::::target' not in calls


def test_nested_function_body_is_not_attributed_to_outer_function():
    graph = CodeGraph()
    graph.scan_sources([{'path': 'a.py', 'content': 'def target(): pass\ndef outer():\n    def inner():\n        target()\n'}])
    assert not any(relation == 'calls' for _, relation, _ in graph.g.edges.get('function:a.py::::outer', []))


def test_package_cycles_respect_ownership_after_cached_projection():
    from codegraph_core.graph.networkx_backend import SoftwareArchitectureGraph
    graph = SoftwareArchitectureGraph()
    for package in ('a', 'b', 'c'):
        graph.add_package(package)
        graph.add_function('package:' + package, 'run')
    first, second = 'package:a::function:run', 'package:b::function:run'
    graph.add_relationship(first, second, 'calls')
    graph.add_relationship(second, first, 'calls')
    assert [set(cycle) for cycle in graph.package_cycles()] == [{'package:a', 'package:b'}]
def test_similarity_ignores_containment_and_keeps_relation_semantics():
    from codegraph_core.graph.networkx_backend import SoftwareArchitectureGraph
    graph = SoftwareArchitectureGraph()
    package = graph.add_package('service')
    first = graph.add_function(package, 'first')
    second = graph.add_function(package, 'second')
    target = graph.add_function(package, 'target')
    assert graph.similarity(first, second) == 0
    graph.add_relationship(first, target, 'calls')
    graph.add_relationship(second, target, 'imports')
    assert graph.similarity(first, second) == 0
    graph.add_relationship(second, target, 'calls')
    assert graph.similarity(first, second) == 0.5
