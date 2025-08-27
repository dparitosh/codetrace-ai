import ast
import os
import re
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set

# Minimal, stdlib graph (nodes dict + adjacency)
@dataclass
class Node:
    id: str
    type: str
    attrs: Dict[str, Any] = field(default_factory=dict)

class InMemoryGraph:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[Tuple[str, str, Dict[str, Any]]]] = {}  # src -> [(dst, type, attrs)]

    def upsert_node(self, id: str, type: str, **attrs):
        if id in self.nodes:
            self.nodes[id].attrs.update(attrs)
        else:
            self.nodes[id] = Node(id=id, type=type, attrs=attrs)
        return self.nodes[id]

    def add_edge(self, src: str, dst: str, etype: str, **attrs):
        self.edges.setdefault(src, []).append((dst, etype, attrs))

    def neighbors(self, id: str) -> List[str]:
        return [dst for (dst, _, _) in self.edges.get(id, [])]

class CodeGraph:
    def __init__(self):
        self.g = InMemoryGraph()
        self.last_scan_time: Optional[float] = None
        self.index: Dict[str, Set[str]] = {}  # term -> node ids

    # Public API
    def scan(self, paths: List[str], excludes: Optional[List[str]] = None):
        excludes = set(excludes or ["node_modules", ".venv", "__pycache__", "dist", "build"]) 
        start = time.time()
        for base in paths:
            for root, dirs, files in os.walk(base):
                if any(part in excludes for part in Path(root).parts):
                    continue
                for f in files:
                    if f.endswith(".py"):
                        self._scan_python_file(Path(root) / f)
        self.last_scan_time = time.time()
        return {"seconds": round(self.last_scan_time - start, 3), "nodes": len(self.g.nodes)}

    def prompt_context(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        # simple matching over node ids, names, and paths
        scores: List[Tuple[str, float]] = []
        q = question.lower().strip()
        q_tokens = [t for t in re.split(r"[^a-zA-Z0-9_]+", q) if t]
        for nid, node in self.g.nodes.items():
            name = node.attrs.get("name", nid).lower()
            path = node.attrs.get("path", "").lower()
            text = f"{nid.lower()} {name} {path}"
            # direct substring reward
            score = 0.0
            if q and q in text:
                score += 3.0
            # token overlap reward
            score += sum(1.0 for t in q_tokens if t and t in text)
            if score > 0:
                scores.append((nid, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        picked = [nid for nid, _ in scores[:top_k]]
        snippets = [self._snippet_for(nid) for nid in picked]
        # record prompt node
        pid = f"prompt:{int(time.time())}"
        self.g.upsert_node(pid, "prompt", question=question, ts=time.time())
        for nid in picked:
            self.g.add_edge(pid, nid, "prompted_by")
        return {
            "question": question,
            "topK": len(picked),
            "symbols": picked,
            "snippets": [s for s in snippets if s],
        }

    # Internals
    def _scan_python_file(self, p: Path):
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception:
            return
        file_id = f"file:{p.as_posix()}"
        self.g.upsert_node(file_id, "file", path=p.as_posix(), loc=src.count("\n") + 1)
        module = (p.stem)
        mod_id = f"module:{module}"
        self.g.upsert_node(mod_id, "module", name=module, path=p.as_posix())
        self.g.add_edge(file_id, mod_id, "defines")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    self.g.add_edge(mod_id, f"module:{n.name.split('.')[0]}", "imports")
            if isinstance(node, ast.ImportFrom) and node.module:
                self.g.add_edge(mod_id, f"module:{node.module.split('.')[0]}", "imports")
            if isinstance(node, ast.ClassDef):
                cid = f"class:{module}.{node.name}"
                self.g.upsert_node(cid, "class", name=node.name, path=p.as_posix(), start=node.lineno)
                self.g.add_edge(mod_id, cid, "defines")
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        self.g.add_edge(cid, f"class:{base.id}", "inherits_from")
            if isinstance(node, ast.FunctionDef):
                fid = f"func:{module}.{node.name}"
                self.g.upsert_node(fid, "function", name=node.name, path=p.as_posix(), start=node.lineno)
                self.g.add_edge(mod_id, fid, "defines")
                # best-effort calls (direct names only)
                for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
                    if isinstance(call.func, ast.Name):
                        self.g.add_edge(fid, f"func:{call.func.id}", "calls")

    def _snippet_for(self, nid: str) -> Optional[Dict[str, Any]]:
        node = self.g.nodes.get(nid)
        if not node:
            return None
        p = node.attrs.get("path")
        if not p:
            return None
        try:
            lines = Path(p).read_text(encoding="utf-8", errors="ignore").splitlines()
            start = max(1, int(node.attrs.get("start", 1)) - 2)
            end = min(len(lines), start + 12)
            return {"id": nid, "path": p, "start": start, "end": end, "code": "\n".join(lines[start-1:end])}
        except Exception:
            return None
