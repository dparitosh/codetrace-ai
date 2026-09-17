"""Local-source quality assessment endpoints."""

from datetime import datetime
from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from api.graph_routes import LocalGraphRequest, build_graph_from_files

quality_router = APIRouter()


class QualityMetric(BaseModel):
    name: str
    value: float
    threshold: float
    status: str
    description: str


class QualityAssessmentResponse(BaseModel):
    repository: str
    overall_score: float
    grade: str
    metrics: List[QualityMetric]
    recommendations: List[str]
    assessed_at: str


@quality_router.post("/local", response_model=QualityAssessmentResponse, summary="Assess a local source folder")
async def assess_local_quality(request: LocalGraphRequest):
    graph = build_graph_from_files(request)
    nodes, edges = graph["nodes"], graph["edges"]
    files = [node for node in nodes if node["type"] == "file"]
    functions = [node for node in nodes if node["type"] == "function"]
    classes = [node for node in nodes if node["type"] == "class"]
    coupling = round(len(edges) / max(len(files), 1), 2)
    undocumented = sum(1 for node in functions + classes if not node["properties"].get("docstring"))
    documentation = round(100 * (1 - undocumented / max(len(functions) + len(classes), 1)), 1)
    complexity_score = max(0.0, round(100 - coupling * 12, 1))
    overall = round((complexity_score + documentation) / 2, 1)
    grade = "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 70 else "D" if overall >= 60 else "F"
    metrics = [QualityMetric(name="Dependency coupling", value=coupling, threshold=3.0, status="pass" if coupling <= 3 else "warning", description="Graph edges per source file"), QualityMetric(name="Documentation coverage", value=documentation, threshold=70.0, status="pass" if documentation >= 70 else "warning", description="Symbols with parser-visible documentation"), QualityMetric(name="Functions", value=float(len(functions)), threshold=0.0, status="pass", description="Detected functions")]
    recommendations = []
    if coupling > 3: recommendations.append("Reduce highly coupled modules by extracting stable interfaces.")
    if documentation < 70: recommendations.append("Document public classes and functions to improve navigability.")
    if not recommendations: recommendations.append("No structural quality hotspot was detected in the selected source files.")
    return QualityAssessmentResponse(repository="local-folder", overall_score=overall, grade=grade, metrics=metrics, recommendations=recommendations, assessed_at=datetime.utcnow().isoformat())
