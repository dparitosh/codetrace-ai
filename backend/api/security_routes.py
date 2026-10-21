"""Local static security checks; no repository-host integration is required."""

import re
import uuid
from typing import List
from fastapi import APIRouter, Depends
from services.analysis_capacity import require_analysis_capacity
from pydantic import BaseModel
from api.graph_routes import LocalGraphRequest, validate_source_limits
from core.config import settings

security_router = APIRouter()


class SecurityFinding(BaseModel):
    rule: str
    severity: str
    file: str
    line: int
    description: str


class LocalSecurityResponse(BaseModel):
    scan_id: str
    source: str
    files_scanned: int
    findings: List[SecurityFinding]
    total_findings: int
    truncated: bool


RULES = [("possible-secret", "high", re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}"), "Possible hard-coded secret"), ("dynamic-execution", "high", re.compile(r"\b(eval|exec)\s*\("), "Dynamic code execution should be reviewed")]


@security_router.post("/local", response_model=LocalSecurityResponse, summary="Scan local source files", dependencies=[Depends(require_analysis_capacity)])
def scan_local_source(request: LocalGraphRequest):
    validate_source_limits(request)
    findings: List[SecurityFinding] = []
    total_findings = 0
    for source_file in request.files:
        for line_number, line in enumerate(source_file.content.splitlines(), start=1):
            for rule, severity, pattern, description in RULES:
                if pattern.search(line):
                    total_findings += 1
                    if len(findings) < settings.SECURITY_MAX_FINDINGS:
                        findings.append(SecurityFinding(rule=rule, severity=severity, file=source_file.path, line=line_number, description=description))
    return LocalSecurityResponse(scan_id=str(uuid.uuid4()), source="local-folder", files_scanned=len(request.files),
                                 findings=findings, total_findings=total_findings, truncated=total_findings > len(findings))
