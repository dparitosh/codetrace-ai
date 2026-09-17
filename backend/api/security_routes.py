"""Local static security checks; no repository-host integration is required."""

import re
import uuid
from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from api.graph_routes import LocalGraphRequest

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


RULES = [("possible-secret", "high", re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}"), "Possible hard-coded secret"), ("dynamic-execution", "high", re.compile(r"\b(eval|exec)\s*\("), "Dynamic code execution should be reviewed")]


@security_router.post("/local", response_model=LocalSecurityResponse, summary="Scan local source files")
async def scan_local_source(request: LocalGraphRequest):
    findings: List[SecurityFinding] = []
    for source_file in request.files:
        for line_number, line in enumerate(source_file.content.splitlines(), start=1):
            for rule, severity, pattern, description in RULES:
                if pattern.search(line):
                    findings.append(SecurityFinding(rule=rule, severity=severity, file=source_file.path, line=line_number, description=description))
    return LocalSecurityResponse(scan_id=str(uuid.uuid4()), source="local-folder", files_scanned=len(request.files), findings=findings[:200])
