"""Configurable, language-tolerant software graph construction."""

import ast
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class Node:
    id: str
    type: str
    attrs: Dict[str, Any] = field(default_factory=dict)


class InMemoryGraph:
    """Small graph API used by the core; NetworkX remains an optional adapter."""
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[Tuple[str, str, Dict[str, Any]]]] = {}

    def upsert_node(self, id: str, type: str, **attrs):
        if id in self.nodes:
            self.nodes[id].attrs.update(attrs)
        else:
            self.nodes[id] = Node(id=id, type=type, attrs=attrs)
        return self.nodes[id]

    def add_edge(self, src: str, dst: str, etype: str, **attrs):
        self.edges.setdefault(src, []).append((dst, etype, attrs))

    def neighbors(self, id: str) -> List[str]:
        return [dst for dst, _, _ in self.edges.get(id, [])]


@dataclass
class ScanConfig:
    extensions: Optional[Set[str]] = None
    excludes: Set[str] = field(default_factory=lambda: {
        ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
        "target", "bin", "obj", ".idea", ".pytest_cache",
    })
    max_file_size: int = 2_000_000
    include_tests: bool = True

    def allowed_extensions(self) -> Set[str]:
        return self.extensions or set(DEFAULT_EXTENSIONS)


DEFAULT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".scala", ".sh", ".sql", ".vue", ".svelte",
}


class CodeGraph:
    def __init__(self, config: Optional[ScanConfig] = None):
        self.g = InMemoryGraph()
        self.config = config or ScanConfig()
        self.last_scan_time: Optional[float] = None
        self.index: Dict[str, Set[str]] = {}
        self._scanners: Dict[str, Callable[[Path, str, str], None]] = {".py": self._scan_python_file}

    def register_scanner(self, extensions, scanner: Callable[[Path, str, str], None]):
        """Register a parser/scanner for one or more extensions."""
        values = [extensions] if isinstance(extensions, str) else extensions
        for extension in values:
            key = extension.lower() if extension.startswith(".") else "." + extension.lower()
            self._scanners[key] = scanner

    def scan(self, paths: List[str], excludes: Optional[List[str]] = None, *, reset: bool = True):
        excluded = set(self.config.excludes) | set(excludes or [])
        if reset:
            self.g = InMemoryGraph()
            self.index.clear()
        start = time.time()
        files_scanned = 0
        for base in paths:
            root = Path(base).resolve()
            candidates = [root] if root.is_file() else (p for p in root.rglob("*") if p.is_file())
            for path in candidates:
                if any(part in excluded for part in path.parts):
                    continue
                if path.suffix.lower() not in self.config.allowed_extensions():
                    continue
                if not self.config.include_tests and ("test" in path.stem.lower() or "tests" in path.parts):
                    continue
                try:
                    if path.stat().st_size > self.config.max_file_size:
                        continue
                    source = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                file_id = "file:" + path.as_posix()
                self.g.upsert_node(file_id, "file", path=path.as_posix(), extension=path.suffix.lower(),
                                   loc=source.count("\n") + 1)
                self._scanners.get(path.suffix.lower(), self._scan_generic_file)(path, source, file_id)
                files_scanned += 1
        self.last_scan_time = time.time()
        return {"seconds": round(self.last_scan_time - start, 3), "files": files_scanned,
                "nodes": len(self.g.nodes), "edges": sum(len(e) for e in self.g.edges.values())}

    def scan_sources(self, sources: List[Dict[str, str]], *, reset: bool = True):
        """Scan source files supplied by a client without requiring server paths."""
        if reset:
            self.g = InMemoryGraph()
            self.index.clear()
        start = time.time()
        files_scanned = 0
        for source_file in sources:
            name = str(source_file.get("path", "untitled"))
            content = str(source_file.get("content", ""))
            extension = Path(name).suffix.lower()
            if extension not in self.config.allowed_extensions() or len(content.encode("utf-8")) > self.config.max_file_size:
                continue
            path = Path(name)
            file_id = "file:" + path.as_posix()
            self.g.upsert_node(file_id, "file", path=path.as_posix(), extension=extension,
                               loc=content.count("\n") + 1)
            self._scanners.get(extension, self._scan_generic_file)(path, content, file_id)
            files_scanned += 1
        self.last_scan_time = time.time()
        return {"seconds": round(self.last_scan_time - start, 3), "files": files_scanned,
                "nodes": len(self.g.nodes), "edges": sum(len(e) for e in self.g.edges.values())}

    def prompt_context(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        scores: List[Tuple[str, float]] = []
        q = question.lower().strip()
        tokens = [t for t in re.split(r"[^a-zA-Z0-9_]+", q) if t]
        for nid, node in self.g.nodes.items():
            text = " ".join((nid, str(node.attrs.get("name", "")), str(node.attrs.get("path", "")))).lower()
            score = (3.0 if q and q in text else 0.0) + sum(1.0 for token in tokens if token in text)
            if score:
                scores.append((nid, score))
        scores.sort(key=lambda item: (-item[1], item[0]))
        picked = [nid for nid, _ in scores[:max(0, top_k)]]
        pid = "prompt:" + str(int(time.time() * 1000))
        self.g.upsert_node(pid, "prompt", question=question, ts=time.time())
        for nid in picked:
            self.g.add_edge(pid, nid, "prompted_by")
        return {"question": question, "topK": len(picked), "symbols": picked,
                "snippets": [snippet for nid in picked if (snippet := self._snippet_for(nid))]}

    def _module_id(self, path: Path) -> str:
        return "module:" + path.with_suffix("").as_posix()

    def _scan_python_file(self, p: Path, source: str, file_id: str):
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            self._scan_generic_file(p, source, file_id)
            return
        module_id = self._module_id(p)
        self.g.upsert_node(module_id, "module", name=p.stem, path=p.as_posix(), language="python")
        self.g.add_edge(file_id, module_id, "defines")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    self.g.add_edge(module_id, "module:" + item.name, "imports", name=item.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.g.add_edge(module_id, "module:" + node.module, "imports", name=node.module)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                symbol_id = f"{kind}:{p.as_posix()}::{node.name}"
                self.g.upsert_node(symbol_id, kind, name=node.name, path=p.as_posix(), start=node.lineno,
                                   language="python")
                self.g.add_edge(module_id, symbol_id, "defines")
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            self.g.add_edge(symbol_id, "symbol:" + base.id, "inherits_from", name=base.id)
                else:
                    for call in ast.walk(node):
                        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                            self.g.add_edge(symbol_id, "symbol:" + call.func.id, "calls", name=call.func.id)

    def _scan_generic_file(self, p: Path, source: str, file_id: str):
        """Best-effort scanner for languages without an installed parser."""
        module_id = self._module_id(p)
        self.g.upsert_node(module_id, "module", name=p.stem, path=p.as_posix(), language=p.suffix.lstrip("."))
        self.g.add_edge(file_id, module_id, "defines")
        for pattern in (r"(?:import|include|require|from)\s+[\"']?([A-Za-z0-9_./@:-]+)",
                        r"#include\s*[<\"]([^>\"]+)"):
            for name in re.findall(pattern, source):
                self.g.add_edge(module_id, "module:" + name, "imports", name=name)
        definition = re.compile(r"\b(?:class|interface|struct|enum|function|func|def)\s+([A-Za-z_][A-Za-z0-9_]*)")
        for match in definition.finditer(source):
            name = match.group(1)
            symbol_id = f"symbol:{p.as_posix()}::{name}"
            self.g.upsert_node(symbol_id, "symbol", name=name, path=p.as_posix(),
                               start=source.count("\n", 0, match.start()) + 1,
                               language=p.suffix.lstrip("."))
            self.g.add_edge(module_id, symbol_id, "defines")

    def _snippet_for(self, nid: str) -> Optional[Dict[str, Any]]:
        node = self.g.nodes.get(nid)
        if not node or not node.attrs.get("path"):
            return None
        try:
            lines = Path(node.attrs["path"]).read_text(encoding="utf-8", errors="ignore").splitlines()
            start = max(1, int(node.attrs.get("start", 1)) - 2)
            end = min(len(lines), start + 12)
            return {"id": nid, "path": node.attrs["path"], "start": start, "end": end,
                    "code": "\n".join(lines[start - 1:end])}
        except (OSError, ValueError):
            return None
