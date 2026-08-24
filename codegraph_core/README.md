# codegraph_core

A portable, dependency-light code knowledge graph core. In‑memory graph, AST scanners, prompt context builder. Optional NetworkX/Matplotlib add‑ons.

Highlights
- Works standalone via CLI or as a library.
- Python AST scanner plus a configurable, language-tolerant scanner for common source files.
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
