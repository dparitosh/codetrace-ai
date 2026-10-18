"""Managed workspace endpoints; connection locations are held only on the server."""
import time
from typing import Optional, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pydantic import SecretStr

from api import review_routes
from core.config import settings
from graph.traceability import neighborhood
from services.workspace_service import build_managed_snapshot
from services.companion_service import answer_question
from services.oslc_service import server_secret
from services.oslc_store import LINK_PREDICATES
from services.ai_connection import AIConnection, OllamaREST, connection_for, allowed_bases
from services.agent_workspace import AGENTS, GraphAgent, GraphSearch
import httpx

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


class AgentQuery(CompanionQuery):
    agent_id: Literal['trace-explorer', 'coverage-reviewer', 'change-analyst'] = 'trace-explorer'


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=1500)
    domain: str = Field(default='ALL', max_length=40)
    limit: int = Field(default=20, ge=1, le=50)
    semantic: bool = True


def ai_guard(token):
    return lambda: review_routes.store.info(token, touch=False)


@workspace_router.get('/ai/config')
def ai_configuration(x_codetrace_session: Optional[str] = Header(default=None)):
    connection = connection_for(review_routes.store, x_codetrace_session)
    return {**connection.public(), 'allowed_base_urls': allowed_bases(), 'agents': AGENTS,
            'request_timeout_seconds': settings.AI_AGENT_DEADLINE_SECONDS + 5,
            'retention': 'Session-owned; keys are never returned. SQLite profiles are encrypted and removed with their session.'}


@workspace_router.put('/ai/config')
def configure_ai(request: AIConnection, x_codetrace_session: Optional[str] = Header(default=None)):
    if request.keep_key and not request.api_key.get_secret_value():
        current = connection_for(review_routes.store, x_codetrace_session)
        request = request.model_copy(update={'api_key': SecretStr(current.api_key.get_secret_value())})
    review_routes.store.ai_profile(x_codetrace_session, request.private())
    return request.public()


@workspace_router.delete('/ai/config')
def reset_ai(x_codetrace_session: Optional[str] = Header(default=None)):
    review_routes.store.ai_profile(x_codetrace_session, clear=True)
    return {'reset': True}


@workspace_router.post('/ai/models')
def ai_models(x_codetrace_session: Optional[str] = Header(default=None)):
    store = review_routes.store
    if not store.workers.acquire(blocking=False):
        raise HTTPException(429, 'AI capacity is busy')
    try:
        rest = OllamaREST(connection_for(store, x_codetrace_session), ai_guard(x_codetrace_session))
        return {'models': rest.models()}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise HTTPException(502, 'Ollama discovery failed. Check the URL, key/header and REST availability.') from None
    finally:
        store.workers.release()


@workspace_router.post('/ai/test')
def test_ai(x_codetrace_session: Optional[str] = Header(default=None)):
    store = review_routes.store
    if not store.workers.acquire(blocking=False):
        raise HTTPException(429, 'AI capacity is busy')
    try:
        rest = OllamaREST(connection_for(store, x_codetrace_session), ai_guard(x_codetrace_session))
        names = rest.models()
        message = rest.chat([{'role': 'user', 'content': 'Return JSON {"ready":true}.'}])
        import json
        if json.loads(message.get('content', '')).get('ready') is not True:
            raise ValueError('Chat readiness response was invalid')
        dimensions = len(rest.embed(['CodeTrace connection test'])[0]) if rest.connection.embeddings_enabled else None
        return {'chat': 'ready' if isinstance(message.get('content'), str) else 'invalid',
                'embedding_dimensions': dimensions, 'available_models': names,
                'warning': 'Connectivity is verified; tool-calling quality is checked during agent execution.'}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise HTTPException(502, 'Ollama chat or embedding test failed. Ensure both selected models are installed and the key/header is correct.') from None
    finally:
        store.workers.release()


def reviewed_graph(token, review_id):
    record = review_routes.store.get(token, review_id)
    if record.get('kind') != 'graph' or 'result' not in record:
        raise HTTPException(422, 'Select a completed graph review')
    return record['result']


@workspace_router.post('/search')
def search_workspace(request: SearchQuery, x_codetrace_session: Optional[str] = Header(default=None)):
    store = review_routes.store
    if not store.workers.acquire(blocking=False):
        raise HTTPException(429, 'Search capacity is busy')
    try:
        graph = reviewed_graph(x_codetrace_session, request.review_id)
        rest = OllamaREST(connection_for(store, x_codetrace_session), ai_guard(x_codetrace_session))
        result = GraphSearch(graph, rest).search(request.query, request.domain, request.limit, request.semantic)
        store.info(x_codetrace_session, touch=False)
        return result
    finally:
        store.workers.release()


@workspace_router.post('/agent/run')
def run_graph_agent(request: AgentQuery, x_codetrace_session: Optional[str] = Header(default=None)):
    store = review_routes.store
    if not store.workers.acquire(blocking=False):
        raise HTTPException(429, 'Agent capacity is busy')
    try:
        graph = reviewed_graph(x_codetrace_session, request.review_id)
        if request.selected_id and not any(node['id'] == request.selected_id for node in graph['nodes']):
            raise HTTPException(404, 'Selected resource is not in this snapshot')
        rest = OllamaREST(connection_for(store, x_codetrace_session), ai_guard(x_codetrace_session))
        return GraphAgent(graph, rest, request.agent_id).run(request.question, request.selected_id)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(422, 'Agent could not complete within the configured evidence and execution budgets.') from None
    finally:
        store.workers.release()


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
