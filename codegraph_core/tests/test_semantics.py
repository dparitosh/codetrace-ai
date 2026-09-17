from codegraph_core.core import CodeGraph


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
