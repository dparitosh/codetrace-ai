"""Bounded, versioned source context for coding-agent integrations."""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.graph_routes import LocalGraphRequest, build_graph_from_files
from api.trace_routes import TraceManifest
from graph.traceability import materialize, neighborhood, code_uri, CT

agent_router = APIRouter(tags=["Agent Context"])
CONTEXT_SCHEMA_VERSION = "1.0"


class AgentContextRequest(LocalGraphRequest):
    query: str = Field(..., min_length=1, max_length=500, description="Coding task or question")
    max_symbols: int = Field(default=40, ge=1, le=100)
    trace_manifest: Optional[TraceManifest] = None


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
        node_map[node["id"]] = node["id"]
        architecture.add_node(node["id"], "class", node["label"], path=path, start=node["properties"].get("start"))
        architecture.add_relationship("package:" + package, node["id"], "contains")
    for node in nodes:
        if node["type"] != "function":
            continue
        properties = node["properties"]
        path = str(properties.get("path", ""))
        owner = node_map.get(str(properties.get("owner"))) or "package:" + _package_name(path)
        node_map[node["id"]] = node["id"]
        architecture.add_node(node["id"], "function", node["label"], path=path, start=properties.get("start"))
        architecture.add_relationship(owner, node["id"], "contains")
    for node in nodes:
        if node["type"] != "variable":
            continue
        properties = node["properties"]
        path = str(properties.get("path", ""))
        owner = node_map.get(str(properties.get("owner"))) or "package:" + _package_name(path)
        node_map[node["id"]] = node["id"]
        architecture.add_node(node["id"], "variable", node["label"], path=path, start=properties.get("start"), scope=properties.get("scope"))
        architecture.add_relationship(owner, node["id"], "contains")
    for edge in graph_data["edges"]:
        if edge["type"] in {"calls", "imports", "inherits_from"} and edge["source"] in node_map and edge["target"] in node_map:
            relationship = "calls" if edge["type"] == "calls" else "depends_on"
            architecture.add_relationship(node_map[edge["source"]], node_map[edge["target"]], relationship)
    return architecture.audit()


@agent_router.post("/context", summary="Build bounded source context for a coding agent")
def create_agent_context(request: AgentContextRequest) -> Dict[str, Any]:
    graph = build_graph_from_files(request)
    audit = _build_architecture_audit(graph)
    tokens = set(re.findall(r"\w+", request.query.lower()))
    candidates = [node for node in graph["nodes"] if node["type"] in {"class", "function", "variable"}]
    candidates.sort(key=lambda node: (-sum(token in (node["id"] + " " + node["label"]).lower() for token in tokens), node["id"]))
    symbols = [
        {"id": node["id"], "kind": node["type"], "name": node["properties"].get("name", node["label"]),
         "path": node["properties"].get("path"), "line": node["properties"].get("start"),
         "owner": node["properties"].get("owner"), "documented": bool(node["properties"].get("docstring"))}
        for node in candidates
    ][:request.max_symbols]
    selected = {symbol["id"] for symbol in symbols}
    relations = [edge for edge in graph["edges"] if edge["type"] in {"calls", "imports", "inherits_from"}
                 and (edge["source"] in selected or edge["target"] in selected)][:request.max_symbols * 3]
    audit_totals = {key: len(value) for key, value in audit.items() if isinstance(value, list)}
    audit = {key: value[:100] if isinstance(value, list) else value for key, value in audit.items()}
    lifecycle_trace = None
    if request.trace_manifest is not None:
        try:
            combined = materialize(graph, request.trace_manifest.model_dump(), graph['metadata']['source_digest'])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        # Anchor context at the best-ranked symbol; omit containment so a shared
        # repository/package does not imply that unrelated features are affected.
        anchor = code_uri(request.trace_manifest.repository.uri, symbols[0]['id']) if symbols else request.trace_manifest.repository.uri
        predicates = sorted({edge['type'] for edge in combined['edges'] if edge['type'] != CT + 'contains'})
        lifecycle_trace = neighborhood(combined, anchor, 'both', 6, 100, predicates or [CT + 'noRelations'])
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "query": request.query,
        "provenance": {"source": "local_folder", "selected_files": graph["metadata"]["selected_files"], "content_retention": "request-only"},
        "graph_summary": {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "files": graph["metadata"].get("files", 0)},
        "symbols": symbols,
        "relations": relations,
        "audit": audit,
        "audit_totals": audit_totals,
        "lifecycle_trace": lifecycle_trace,
        "limitations": ["Call resolution is limited to simple intra-module Python calls; uncalled functions are candidates for review.",
                        "Cross-module import resolution and complete package-cycle detection are not implemented."],
        "agent_guidance": [
            "Treat static findings as review prompts, not proof of a defect.",
            "Read the referenced file before changing code and preserve existing public contracts.",
            "Validate an intended change with the project test suite after editing.",
        ],
    }
