from codegraph_core.core import CodeGraph


def test_scan_and_prompt():
    cg = CodeGraph()
    res = cg.scan(["python_backend"])  # path relative to repo root when run under pytest -k
    assert res["nodes"] >= 0
    pack = cg.prompt_context("workflow", top_k=3)
    assert "symbols" in pack
