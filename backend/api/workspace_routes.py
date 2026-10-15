"""Managed workspace endpoints; connection locations are held only on the server."""
import time
from typing import Optional, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api import review_routes
from core.config import settings
from graph.traceability import neighborhood
from services.workspace_service import build_managed_snapshot
from services.companion_service import answer_question
from services.oslc_service import server_secret
from services.oslc_store import LINK_PREDICATES

workspace_router = APIRouter(tags=['Managed Intelligence Workspace'])


class ManagedSync(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    source_id: str = Field(min_length=1, max_length=80)
    include_lifecycle: bool = True
    kind: Literal['graph'] = 'graph'


class CompanionQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=1500)
    selected_id: Optional[str] = Field(default=None, max_length=2048)


class ContextQuery(BaseModel):
    review_id: str
    node_id: str
    direction: str = Field(default='both', pattern=r'^(both|incoming|outgoing)$')
    depth: int = Field(default=2, ge=0, le=6)


@workspace_router.get('/catalog')
def workspace_catalog():
    return {'sources': [{'id': item.id, 'label': item.label, 'kind': item.kind, 'ref': item.ref}
                        for item in settings.MANAGED_REPOSITORIES],
            'providers': [{'id': item.id, 'label': item.label, 'domain': item.domain,
                'transport': 'file' if item.file_path else 'network',
                'allow_writes': item.allow_writes,
                'credential_configured': (bool(server_secret(item.username_env) and server_secret(item.password_env)) if item.auth_type == 'basic'
                                          else bool(server_secret(item.token_env)) if item.token_env else None)}
                for item in settings.OSLC_PROVIDERS],
            'pipelines': [{'id': item.id, 'label': item.label, 'platform': item.platform, 'repository_id': item.repository_id}
                          for item in settings.CI_PROVIDERS],
            'ai': {'provider': settings.AI_PROVIDER, 'model': settings.AI_MODEL,
                   'timeout_seconds': settings.AI_TIMEOUT_SECONDS},
            'settings': {'request_timeout_seconds': settings.REQUEST_TIMEOUT_SECONDS,
                         'collaboration_timeout_seconds': settings.OSLC_TIMEOUT_SECONDS * 3 + 15,
                         'render_nodes': settings.WORKSPACE_RENDER_NODES, 'render_edges': settings.WORKSPACE_RENDER_EDGES},
            'link_predicates': sorted(LINK_PREDICATES),
            'configuration': 'root .env.local; changes require a service restart'}


@workspace_router.post('/sync')
def sync_workspace(request: ManagedSync, x_codetrace_session: Optional[str] = Header(default=None)):
    store = review_routes.store
    if not store.workers.acquire(blocking=False):
        raise HTTPException(429, 'Analysis workers are busy. Retry shortly.')
    reserved = False
    try:
        existing = store.reserve(x_codetrace_session, request)
        if existing is not None:
            return existing
        reserved = True
        started = time.monotonic()
        graph = build_managed_snapshot(request.source_id, request.include_lifecycle)
        if time.monotonic() - started >= settings.REQUEST_TIMEOUT_SECONDS:
            raise HTTPException(504, 'Workspace sync exceeded the configured deadline. Reduce provider scope or source size.')
        return store.finish(x_codetrace_session, request.request_id, graph, time.monotonic() - started)
    except Exception:
        if reserved:
            store.abandon(x_codetrace_session, request.request_id)
        raise
    finally:
        store.workers.release()


@workspace_router.post('/context')
def resource_context(request: ContextQuery, x_codetrace_session: Optional[str] = Header(default=None)):
    record = review_routes.store.get(x_codetrace_session, request.review_id)
    if record.get('kind') != 'graph' or 'result' not in record:
        raise HTTPException(422, 'Select a completed graph review')
    try:
        return neighborhood(record['result'], request.node_id, request.direction, request.depth, 120)
    except KeyError as exc:
        raise HTTPException(404, 'Selected resource is not present in this graph') from exc


@workspace_router.post('/companion')
def workspace_companion(request: CompanionQuery, x_codetrace_session: Optional[str] = Header(default=None)):
    store = review_routes.store
    if not store.workers.acquire(blocking=False):
        raise HTTPException(429, 'Companion workers are busy. Retry shortly.')
    try:
        record = store.get(x_codetrace_session, request.review_id)
        if record.get('kind') != 'graph' or 'result' not in record:
            raise HTTPException(422, 'Select a completed graph review')
        graph = record['result']
        if request.selected_id and not any(node['id'] == request.selected_id for node in graph['nodes']):
            raise HTTPException(404, 'Selected resource is not present in this graph')
        answer = answer_question(graph, request.question, request.selected_id)
        store.info(x_codetrace_session, touch=False)  # Do not disclose a late answer after expiry.
        return answer
    finally:
        store.workers.release()


@workspace_router.get('/sbom/{review_id}')
def export_sbom(review_id: str, x_codetrace_session: Optional[str] = Header(default=None)):
    record = review_routes.store.get(x_codetrace_session, review_id, export=True)
    sbom = record.get('result', {}).get('sbom')
    if not sbom:
        raise HTTPException(404, 'This review has no imported or generated SBOM')
    return sbom
