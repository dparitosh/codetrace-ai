# codegraph_core

A portable, dependency-light code knowledge graph core. In‑memory graph, AST scanners, prompt context builder. Optional NetworkX/Matplotlib add‑ons.

Highlights
- Works standalone via CLI or as a library.
- Python AST scanner, optional Tree-sitter C/C++/C# syntax parsers, and a configurable structural scanner for other source files.

The application installer includes the native parsers. Standalone core users can install the `native` extra (`pip install '.[native]'`, Python 3.10+). Native extraction includes namespaces, types, callable declarations, parameters, variables, include/using links and inheritance. Calls bind only when the supported lexical and arity rules select a unique target; unresolved and ambiguous calls remain explicit. This is syntax analysis, without compiler binding, macro/build-condition evaluation, project metadata, virtual dispatch or deferred lambda calls. Missing grammars fall back to structural extraction with a file warning; recovered syntax errors mark the file partial.
- Pure stdlib core; optional extras (`networkx`, `matplotlib`, `squarify`) for graphs/treemaps.

## Quick start
- Library
```python
from codegraph_core import CodeGraph, ScanConfig
cg = CodeGraph(ScanConfig(extensions={".py", ".ts", ".tsx"}))
cg.scan(paths=["./my-repository"])
pack = cg.prompt_context("Where is workflow DB service created?", top_k=5)
print(pack)
```
- CLI
```bash
python -m codegraph_core scan --paths python_backend --summary
python -m codegraph_core scan --paths ./my-repository --extensions .py .ts --summary
python -m codegraph_core prompt --q "impact of changing workflow_models" --top-k 5
```

## Design
- Core graph: Dict-based adjacency to avoid hard deps. Optional NetworkX adapter.
- Scanners: register a real parser for any extension with `register_scanner`; unknown configured source types still produce file/module/definition/import relationships.
- NetworkX: exports a `MultiDiGraph` by default so parallel relationships are preserved.
- Prompt: small, ranked context with minimal code spans.

## License
MIT
