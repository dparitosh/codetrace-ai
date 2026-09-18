"""Provider-neutral source graph endpoints."""

from __future__ import annotations

import subprocess
import os
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator

from core.config import settings

graph_router = APIRouter(tags=["Graph Analysis"])
MAX_LOCAL_FILES = 500
MAX_LOCAL_PAYLOAD_BYTES = 10_000_000


class Node(BaseModel):
    id: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphData(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    metadata: Dict[str, Any]


class LocalSourceFile(BaseModel):
    path: str = Field(..., min_length=1, description="Relative source path")
    content: str = Field(..., description="UTF-8 source contents")
    size: Optional[int] = Field(default=None, ge=0)
    last_modified: Optional[int] = Field(default=None, ge=0)

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        raw = value.replace("\\", "/")
        path = PurePosixPath(raw)
        if (not path.name or path.is_absolute() or PureWindowsPath(raw).drive
                or ".." in path.parts or ":" in raw or "\x00" in raw):
            raise ValueError("path must be a non-empty relative source path")
        return path.as_posix()


class LocalGraphRequest(BaseModel):
    files: List[LocalSourceFile] = Field(..., min_length=1)
    extensions: Optional[List[str]] = None
    profile: Literal["standard", "strict"] = "standard"


class GitLabGraphRequest(BaseModel):
    project_url: HttpUrl = Field(..., description="HTTPS GitLab project URL")
    ref: Optional[str] = Field(default=None, description="Optional branch or tag")


def _serialize_graph(graph: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
    nodes = [{"id": node_id, "label": node.attrs.get("name", node_id), "type": node.type, "properties": node.attrs} for node_id, node in graph.g.nodes.items()]
    edges = [{"source": source, "target": target, "type": edge_type, "properties": attrs} for source, outgoing in graph.g.edges.items() for target, edge_type, attrs in outgoing]
    known = {node["id"] for node in nodes}
    for edge in edges:
        for endpoint in (edge["source"], edge["target"]):
            if endpoint not in known:
                nodes.append({"id": endpoint, "label": endpoint, "type": "external_symbol", "properties": {"resolved": False}})
                known.add(endpoint)
    return {"nodes": nodes, "edges": edges, "metadata": {**metadata, "nodes": len(nodes), "edges": len(edges)}}


def validate_source_limits(request: LocalGraphRequest) -> int:
    payload_size = sum(len(file.content.encode("utf-8")) for file in request.files)
    if len(request.files) > MAX_LOCAL_FILES or payload_size > MAX_LOCAL_PAYLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Local source is limited to {MAX_LOCAL_FILES} files and {MAX_LOCAL_PAYLOAD_BYTES // 1_000_000} MB")
    paths = [file.path for file in request.files]
    if len(paths) != len(set(paths)):
        raise HTTPException(status_code=422, detail="Duplicate source paths are not allowed")
    return payload_size


def build_graph_from_files(request: LocalGraphRequest) -> Dict[str, Any]:
    payload_size = validate_source_limits(request)
    from graph.codegraph_integration import CodeGraph
    from codegraph_core import ScanConfig
    scan_config = ScanConfig(extensions=set(request.extensions or []) or None)
    if request.profile == "strict":
        unsupported = [file.path for file in request.files if Path(file.path).suffix.lower() not in scan_config.allowed_extensions()]
        if unsupported:
            raise HTTPException(status_code=422, detail="Strict profile only accepts configured source extensions: " + ", ".join(unsupported[:5]))
    graph = CodeGraph(scan_config)
    summary = graph.scan_sources([file.model_dump() for file in request.files])
    digest = hashlib.sha256(json.dumps(sorted((file.path, hashlib.sha256(file.content.encode()).hexdigest()) for file in request.files)).encode()).hexdigest()
    return _serialize_graph(graph, {**summary, "source_digest": digest, "source": "local_folder", "analysis_profile": request.profile, "selected_files": len(request.files), "selected_bytes": payload_size, "source_paths": [file.path for file in request.files]})


def build_graph_from_directory(directory: Path, source: str, project_url: Optional[str] = None) -> Dict[str, Any]:
    from graph.codegraph_integration import CodeGraph
    from codegraph_core import ScanConfig
    config = ScanConfig()
    files = []
    total = 0
    for current, directories, names in os.walk(directory, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in config.excludes
                                and not (Path(current) / name).is_symlink())
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink() or path.suffix.lower() not in config.allowed_extensions():
                continue
            if path.stat().st_size > config.max_file_size:
                raise HTTPException(status_code=413, detail="Repository contains an oversized source file")
            data = path.read_bytes()
            total += len(data)
            if total > MAX_LOCAL_PAYLOAD_BYTES or len(files) >= MAX_LOCAL_FILES:
                raise HTTPException(status_code=413, detail="Repository exceeds analysis file or byte limits")
            try:
                content = data.decode('utf-8')
            except UnicodeDecodeError:
                continue
            files.append(LocalSourceFile(path=path.relative_to(directory).as_posix(), content=content))
    if not files:
        raise HTTPException(status_code=422, detail="No supported UTF-8 source files found")
    graph = build_graph_from_files(LocalGraphRequest(files=files))
    graph['metadata'].update(source=source, project_url=project_url)
    return graph


def _validate_gitlab_url(project_url: str) -> str:
    parsed = urlparse(project_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=400, detail="GitLab project URLs must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None, 443):
        raise HTTPException(status_code=400, detail="Use a plain HTTPS project URL without credentials, query, fragment, or custom port")
    if parsed.hostname.lower() not in {host.lower() for host in settings.GITLAB_ALLOWED_HOSTS}:
        raise HTTPException(status_code=400, detail="GitLab host is not in GITLAB_ALLOWED_HOSTS")
    if len(parsed.path.strip("/").split("/")) < 2 or "/-/" in parsed.path:
        raise HTTPException(status_code=400, detail="A GitLab project path is required")
    return project_url.rstrip("/")


@graph_router.post("/local", response_model=GraphData, summary="Build a graph from local source files")
def generate_local_graph(request: LocalGraphRequest):
    return build_graph_from_files(request)


@graph_router.post("/local/analyze", summary="Analyze local source files")
def analyze_local_sources(request: LocalGraphRequest):
    graph = build_graph_from_files(request)
    total_lines = sum(int(node["properties"].get("loc", 0)) for node in graph["nodes"] if node["type"] == "file")
    return {"analysis_id": f"local-{int(datetime.utcnow().timestamp() * 1000)}", "status": "completed", "repository": "local-folder", "branch": "local", "results": {"summary": {"total_files": graph["metadata"].get("files", 0), "total_lines": total_lines}, "graph": graph}}


@graph_router.post("/gitlab", response_model=GraphData, summary="Build a graph from a GitLab project")
def generate_gitlab_graph(request: GitLabGraphRequest):
    project_url = _validate_gitlab_url(str(request.project_url))
    clone_url = project_url if project_url.endswith(".git") else f"{project_url}.git"
    command = ["git", "-c", "http.followRedirects=false", "-c", "core.hooksPath=", "clone", "--depth", "1"]
    if request.ref:
        command.extend(["--branch", request.ref])
    with tempfile.TemporaryDirectory(prefix="codetrace-gitlab-") as temp_dir:
        target = Path(temp_dir) / "project"
        try:
            completed = subprocess.run(command + ["--", clone_url, str(target)], capture_output=True, text=True, timeout=60, check=False,
                                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"})
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail="Git is required for GitLab project analysis") from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="GitLab clone timed out") from exc
        if completed.returncode != 0:
            raise HTTPException(status_code=422, detail="GitLab project could not be cloned; verify project access and URL")
        return build_graph_from_directory(target, "gitlab", project_url)
