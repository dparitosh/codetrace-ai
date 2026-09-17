"""Bounded, versioned source context for coding-agent integrations."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.graph_routes import LocalGraphRequest, build_graph_from_files

agent_router = APIRouter(tags=["Agent Context"])
CONTEXT_SCHEMA_VERSION = "1.0"


class AgentContextRequest(LocalGraphRequest):
    query: str = Field(..., min_length=1, max_length=500, description="Coding task or question")
    max_symbols: int = Field(default=40, ge=1, le=100)


def _package_name(path: str) -> str:
    parent = Path(path).parent.as_posix()
    return parent if parent not in {"", "."} else "root"


def _build_architecture_audit(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    """Project scanner output into the typed NetworkX architecture model."""
    from codegraph_core.graph.networkx_backend import SoftwareArchitectureGraph

    architecture = SoftwareArchitectureGraph()
    node_map: Dict[str, str] = {}
    package_by_source: Dict[str, str] = {}
    nodes = graph_data["nodes"]
    for node in nodes:
        if node["type"] != "file":
            continue
        package = _package_name(str(node["properties"].get("path", node["id"])))
        package_by_source[node["id"]] = package
        if "package:" + package not in architecture.graph:
            architecture.add_package(package)
    for node in nodes:
        if node["type"] != "class":
            continue
        path = str(node["properties"].get("path", ""))
        package = _package_name(path)
        node_map[node["id"]] = architecture.add_class(package, str(node["properties"].get("name", node["label"])), path=path, start=node["properties"].get("start"))
    for node in nodes:
        if node["type"] != "function":
            continue
        properties = node["properties"]
        path = str(properties.get("path", ""))
        owner = node_map.get(str(properties.get("owner"))) or "package:" + _package_name(path)
        node_map[node["id"]] = architecture.add_function(owner, str(properties.get("name", node["label"])), path=path, start=properties.get("start"), docstring=bool(properties.get("docstring")))
    for node in nodes:
        if node["type"] != "variable":
            continue
        properties = node["properties"]
        path = str(properties.get("path", ""))
        owner = node_map.get(str(properties.get("owner"))) or "package:" + _package_name(path)
        node_map[node["id"]] = architecture.add_variable(owner, str(properties.get("name", node["label"])), path=path, start=properties.get("start"), scope=properties.get("scope"))
    for edge in graph_data["edges"]:
        if edge["type"] in {"calls", "imports", "inherits_from"} and edge["source"] in node_map and edge["target"] in node_map:
            relationship = "calls" if edge["type"] == "calls" else "depends_on"
            architecture.add_relationship(node_map[edge["source"]], node_map[edge["target"]], relationship)
    return architecture.audit()


@agent_router.post("/context", summary="Build bounded source context for a coding agent")
async def create_agent_context(request: AgentContextRequest) -> Dict[str, Any]:
    graph = build_graph_from_files(request)
    audit = _build_architecture_audit(graph)
    symbols = [
        {"id": node["id"], "kind": node["type"], "name": node["properties"].get("name", node["label"]),
         "path": node["properties"].get("path"), "line": node["properties"].get("start"),
         "owner": node["properties"].get("owner"), "documented": bool(node["properties"].get("docstring"))}
        for node in graph["nodes"] if node["type"] in {"class", "function", "variable"}
    ][:request.max_symbols]
    relations = [edge for edge in graph["edges"] if edge["type"] in {"calls", "imports", "inherits_from"}][:request.max_symbols * 3]
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "query": request.query,
        "provenance": {"source": "local_folder", "selected_files": graph["metadata"]["selected_files"], "content_retention": "request-only"},
        "graph_summary": {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "files": graph["metadata"].get("files", 0)},
        "symbols": symbols,
        "relations": relations,
        "audit": audit,
        "agent_guidance": [
            "Treat static findings as review prompts, not proof of a defect.",
            "Read the referenced file before changing code and preserve existing public contracts.",
            "Validate an intended change with the project test suite after editing.",
        ],
    }
