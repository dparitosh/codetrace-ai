"""Local-source quality assessment endpoints."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
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
    metrics: List[QualityMetric]
    recommendations: List[str]
    assessed_at: str


@quality_router.post("/local", response_model=QualityAssessmentResponse, summary="Assess a local source folder")
def assess_local_quality(request: LocalGraphRequest):
    graph = build_graph_from_files(request)
    nodes, edges = graph["nodes"], graph["edges"]
    files = [node for node in nodes if node["type"] == "file"]
    if not files:
        raise HTTPException(status_code=422, detail="No supported source files were selected")
    functions = [node for node in nodes if node["type"] == "function"]
    classes = [node for node in nodes if node["type"] == "class"]
    coupling = round(sum(edge['type'] in {'calls', 'imports', 'inherits_from'} for edge in edges) / len(files), 2)
    undocumented = sum(1 for node in functions + classes if not node["properties"].get("docstring"))
    documentation = round(100 * (1 - undocumented / (len(functions) + len(classes))), 1) if functions or classes else None
    complexity_score = max(0.0, round(100 - coupling * 12, 1))
    overall = round((complexity_score + documentation) / 2, 1) if documentation is not None else None
    grade = "N/A" if overall is None else "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 70 else "D" if overall >= 60 else "F"
    metrics = [QualityMetric(name="Dependency coupling", value=coupling, threshold=3.0, status="pass" if coupling <= 3 else "warning", description="Dependency edges per source file; excludes ownership"), QualityMetric(name="Documentation coverage", value=documentation, threshold=70.0, status="unavailable" if documentation is None else "pass" if documentation >= 70 else "warning", description="Symbols with parser-visible documentation"), QualityMetric(name="Functions", value=float(len(functions)), threshold=0.0, status="pass", description="Detected functions")]
    recommendations = []
    if coupling > 3: recommendations.append("Reduce highly coupled modules by extracting stable interfaces.")
    if documentation is None: recommendations.append("No class/function documentation metric is available for this selection; no overall grade was assigned.")
    elif documentation < 70: recommendations.append("Document public classes and functions to improve navigability.")
    if not recommendations: recommendations.append("No structural quality hotspot was detected in the selected source files.")
    return QualityAssessmentResponse(repository="local-folder", overall_score=overall, grade=grade, metrics=metrics, recommendations=recommendations, assessed_at=datetime.utcnow().isoformat())
