"""Provider-neutral source graph endpoints."""

from __future__ import annotations

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
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
        path = Path(raw)
        if not raw or path.is_absolute() or ".." in path.parts:
            raise ValueError("path must be a non-empty relative source path")
        return raw[2:] if raw.startswith("./") else raw


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
    return {"nodes": nodes, "edges": edges, "metadata": {**metadata, "nodes": len(nodes), "edges": len(edges)}}


def build_graph_from_files(request: LocalGraphRequest) -> Dict[str, Any]:
    payload_size = sum(len(file.content.encode("utf-8")) for file in request.files)
    if len(request.files) > MAX_LOCAL_FILES or payload_size > MAX_LOCAL_PAYLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Local source is limited to {MAX_LOCAL_FILES} files and {MAX_LOCAL_PAYLOAD_BYTES // 1_000_000} MB")
    from graph.codegraph_integration import CodeGraph
    from codegraph_core import ScanConfig
    scan_config = ScanConfig(extensions=set(request.extensions or []) or None)
    if request.profile == "strict":
        unsupported = [file.path for file in request.files if Path(file.path).suffix.lower() not in scan_config.allowed_extensions()]
        if unsupported:
            raise HTTPException(status_code=422, detail="Strict profile only accepts configured source extensions: " + ", ".join(unsupported[:5]))
    graph = CodeGraph(scan_config)
    summary = graph.scan_sources([file.model_dump() for file in request.files])
    return _serialize_graph(graph, {**summary, "source": "local_folder", "analysis_profile": request.profile, "selected_files": len(request.files), "selected_bytes": payload_size, "source_paths": [file.path for file in request.files]})


def build_graph_from_directory(directory: Path, source: str, project_url: Optional[str] = None) -> Dict[str, Any]:
    from graph.codegraph_integration import CodeGraph
    graph = CodeGraph()
    summary = graph.scan(paths=[str(directory)])
    return _serialize_graph(graph, {**summary, "source": source, "project_url": project_url})


def _validate_gitlab_url(project_url: str) -> str:
    parsed = urlparse(project_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=400, detail="GitLab project URLs must use HTTPS")
    if parsed.hostname.lower() not in {host.lower() for host in settings.GITLAB_ALLOWED_HOSTS}:
        raise HTTPException(status_code=400, detail="GitLab host is not in GITLAB_ALLOWED_HOSTS")
    if not parsed.path.strip("/"):
        raise HTTPException(status_code=400, detail="A GitLab project path is required")
    return project_url.rstrip("/")


@graph_router.post("/local", response_model=GraphData, summary="Build a graph from local source files")
async def generate_local_graph(request: LocalGraphRequest):
    return build_graph_from_files(request)


@graph_router.post("/local/analyze", summary="Analyze local source files")
async def analyze_local_sources(request: LocalGraphRequest):
    graph = build_graph_from_files(request)
    total_lines = sum(int(node["properties"].get("loc", 0)) for node in graph["nodes"] if node["type"] == "file")
    return {"analysis_id": f"local-{int(datetime.utcnow().timestamp() * 1000)}", "status": "completed", "repository": "local-folder", "branch": "local", "results": {"summary": {"total_files": graph["metadata"].get("files", 0), "total_lines": total_lines}, "graph": graph}}


@graph_router.post("/gitlab", response_model=GraphData, summary="Build a graph from a GitLab project")
async def generate_gitlab_graph(request: GitLabGraphRequest):
    project_url = _validate_gitlab_url(str(request.project_url))
    clone_url = project_url if project_url.endswith(".git") else f"{project_url}.git"
    command = ["git", "clone", "--depth", "1"]
    if request.ref:
        command.extend(["--branch", request.ref])
    with tempfile.TemporaryDirectory(prefix="codetrace-gitlab-") as temp_dir:
        target = Path(temp_dir) / "project"
        try:
            completed = subprocess.run(command + [clone_url, str(target)], capture_output=True, text=True, timeout=60, check=False)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail="Git is required for GitLab project analysis") from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="GitLab clone timed out") from exc
        if completed.returncode != 0:
            raise HTTPException(status_code=422, detail="GitLab project could not be cloned; verify project access and URL")
        return build_graph_from_directory(target, "gitlab", project_url)


@graph_router.get("/enhanced-traceability", summary="Describe the local graph viewer")
async def enhanced_traceability_graph():
    return {"success": True, "graph_data": {"description": "Generate a local or GitLab graph to inspect source relationships.", "nodes": [], "links": []}}
