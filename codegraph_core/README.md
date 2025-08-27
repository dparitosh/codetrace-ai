# codegraph_core

A portable, dependency-light code knowledge graph core. In‑memory graph, AST scanners, prompt context builder. Optional NetworkX/Matplotlib add‑ons.

Highlights
- Works standalone via CLI or as a library.
- Default: Python AST scanner; pluggable scanners for JS/TS, C/C++, Java, C#.
- Pure stdlib core; optional extras (`networkx`, `matplotlib`, `squarify`) for graphs/treemaps.

## Quick start
- Library
```python
from codegraph_core import CodeGraph
cg = CodeGraph()
cg.scan(paths=["./python_backend"])  # Python first
pack = cg.prompt_context("Where is workflow DB service created?", top_k=5)
print(pack)
```
- CLI
```bash
python -m codegraph_core scan --paths python_backend --summary
python -m codegraph_core prompt --q "impact of changing workflow_models" --top-k 5
```

## Design
- Core graph: Dict-based adjacency to avoid hard deps. Optional NetworkX adapter.
- Scanners: Python AST in v1; adapters for other languages can plug in.
- Prompt: small, ranked context with minimal code spans.

## License
MIT
