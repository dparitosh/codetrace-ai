"""Local-source quality assessment endpoints."""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from services.analysis_capacity import require_analysis_capacity
from pydantic import BaseModel
from api.graph_routes import LocalGraphRequest, build_graph_from_files

quality_router = APIRouter()


class QualityMetric(BaseModel):
    name: str
    value: Optional[float]
    threshold: float
    status: str
    description: str


class QualityAssessmentResponse(BaseModel):
    repository: str
    overall_score: Optional[float]
    grade: str
    scoring_basis: str
    metrics: List[QualityMetric]
    recommendations: List[str]
    assessed_at: str


@quality_router.post("/local", response_model=QualityAssessmentResponse, summary="Assess a local source folder", dependencies=[Depends(require_analysis_capacity)])
def assess_local_quality(request: LocalGraphRequest):
    graph = build_graph_from_files(request)
    return assess_graph_quality(graph)


def assess_graph_quality(graph):
    """Compute metrics from the exact graph already retained in the snapshot."""
    nodes, edges = graph["nodes"], graph["edges"]
    files = [node for node in nodes if node["type"] == "file"]
    if not files:
        raise HTTPException(status_code=422, detail="No supported source files were selected")
    functions = [node for node in nodes if node["type"] == "function"]
    classes = [node for node in nodes if node["type"] == "class"]
    assessable_files = [node for node in files if node['properties'].get('nonempty', True)]
    failed_files = [node for node in files if node['properties'].get('parse_status') in {'failed', 'partial'}]
    function_count_available = bool(assessable_files) and all(
        node['properties'].get('parse_status') == 'parsed' for node in assessable_files)
    dependency_count = sum(edge['type'] in {'calls', 'imports', 'inherits_from'} for edge in edges)
    coupling = round(dependency_count / len(assessable_files), 2) if assessable_files else None
    documented_symbols = [node for node in functions + classes if node['properties'].get('language') == 'python']
    undocumented = sum(1 for node in documented_symbols if not node["properties"].get("docstring"))
    documentation = round(100 * (1 - undocumented / len(documented_symbols)), 1) if documented_symbols else None
    dependency_score = max(0.0, round(100 - coupling * 12, 1)) if coupling is not None else None
    has_structure = dependency_count > 0 or any(node['type'] in {'function', 'class', 'symbol', 'variable'} for node in nodes)
    overall = dependency_score if has_structure and not failed_files else None
    scoring_basis = ('Not scored: Source parsing failed or recovered syntax errors in one or more files. Correct the syntax and synchronize again.' if failed_files else
                     'Dependency score only: max(0, 100 - 12 × dependency edges per non-empty file). Documentation coverage is assessed separately and does not affect the score or grade.'
                     if has_structure else
                     'Not scored: no assessable symbols or dependencies were detected.')
    grade = "N/A" if overall is None else "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 70 else "D" if overall >= 60 else "F"
    metrics = [
        QualityMetric(name="Dependency coupling", value=coupling, threshold=3.0,
                      status="unavailable" if coupling is None or failed_files else "pass" if coupling <= 3 else "warning",
                      description="Detected dependency edges per non-empty source file; excludes ownership. Heuristic languages may have incomplete extraction."),
        QualityMetric(name="Documentation coverage", value=documentation, threshold=70.0,
                      status="unavailable" if documentation is None else "pass" if documentation >= 70 else "warning",
                      description="Typed Python classes/functions with docstrings; heuristic symbols are excluded"),
        QualityMetric(name="Functions", value=float(len(functions)) if function_count_available else None, threshold=0.0,
                      status="pass" if function_count_available else "unavailable",
                      description="Parsed Python/C/C++/C# callable declarations; not runtime reachability. Unavailable when non-empty files lack successful syntax parsing"),
    ]
    recommendations = []
    if failed_files:
        recommendations.append("Source parsing failed or recovered syntax errors for one or more files; partial evidence is retained for exploration, but no overall grade was assigned.")
    if coupling is not None and coupling > 3: recommendations.append("Reduce highly coupled modules by extracting stable interfaces.")
    if documentation is None:
        recommendations.append("Documentation coverage is unavailable: the current parser exposes documentation for typed Python classes/functions only.")
        if not has_structure:
            recommendations.append("No assessable symbols or dependencies were detected; no overall grade was assigned.")
    elif documentation < 70: recommendations.append("Document public classes and functions to improve navigability.")
    if not recommendations: recommendations.append("No structural quality hotspot was detected in the selected source files.")
    return QualityAssessmentResponse(repository="local-folder", overall_score=overall, grade=grade, scoring_basis=scoring_basis, metrics=metrics, recommendations=recommendations, assessed_at=datetime.now(timezone.utc).isoformat())
