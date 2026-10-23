"""Local conversation/dossier automation and review; external create is unavailable."""
from functools import lru_cache
from typing import Literal, Optional
import httpx

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from api import review_routes
from api.workspace_routes import reviewed_graph, ai_guard
from core.config import settings
from services.change_store import ChangeStore, FIELDS
from services.agent_workspace import GraphAgent
from services.ai_connection import OllamaREST, connection_for

change_router = APIRouter(tags=['Change dossiers'])


@lru_cache(maxsize=4)
def repository(path):
    return ChangeStore(path)


def store():
    return repository(str(settings.CHANGE_DB_PATH))


def local_session(x_codetrace_session: Optional[str] = Header(default=None)):
    # Durable local workbench is shared by local reviewers, unlike ephemeral
    # session reviews. It is not enterprise identity or independent sign-off.
    review_routes.store.info(x_codetrace_session, touch=True)
    return x_codetrace_session


class Request(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Create(Request):
    request_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    review_id: str = Field(min_length=1, max_length=128)
    selected_id: Optional[str] = Field(default=None, max_length=4096)


class Version(Request):
    revision: int = Field(ge=0)


class Edit(Version):
    title: Optional[str] = Field(default=None, max_length=180)
    problem: Optional[str] = Field(default=None, max_length=12000)
    impact: Optional[str] = Field(default=None, max_length=12000)
    scope: Optional[str] = Field(default=None, max_length=12000)
    proposal: Optional[str] = Field(default=None, max_length=12000)
    acceptance: Optional[str] = Field(default=None, max_length=12000)
    validation: Optional[str] = Field(default=None, max_length=12000)
    rollback: Optional[str] = Field(default=None, max_length=12000)


class Capture(Version):
    node_id: str = Field(min_length=1, max_length=4096)
    turn_id: str = Field(default='', max_length=128)
    agent_id: str = Field(default='', max_length=80)
    citation_id: str = Field(default='', max_length=80)


class RemoveEvidence(Version):
    evidence_id: str = Field(min_length=64, max_length=64)


class Ask(Version):
    request_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    question: str = Field(min_length=1, max_length=1500)
    selected_id: Optional[str] = Field(default=None, max_length=4096)
    agent_id: Literal['trace-explorer', 'coverage-reviewer', 'change-analyst'] = 'trace-explorer'
    automate: bool = False

    @field_validator('question')
    @classmethod
    def meaningful(cls, value):
        if not value.strip():
            raise ValueError('Enter a meaningful question')
        return value


class Decision(Version):
    action: Literal['submit', 'approve', 'reject', 'request_changes', 'revise']
    note: str = Field(default='', max_length=2000)
    acknowledged: bool = False


@change_router.get('')
def list_changes(token=Depends(local_session)):
    return store().list()


@change_router.post('')
def create_change(request: Create, token=Depends(local_session)):
    record = review_routes.store.get(token, request.review_id)
    graph = reviewed_graph(token, request.review_id)
    case_id = store().create(graph, record['result_digest'], request.selected_id, request.request_id)
    return store().get(case_id, graph=True)


@change_router.get('/{case_id}')
def get_change(case_id: str, token=Depends(local_session)):
    return store().get(case_id, graph=True)


@change_router.post('/{case_id}/edit')
def edit_change(case_id: str, request: Edit, token=Depends(local_session)):
    store().update(case_id, request.revision, request.model_dump(exclude={'revision'}, exclude_none=True, exclude_unset=True))
    return store().get(case_id)


@change_router.post('/{case_id}/evidence')
def capture_evidence(case_id: str, request: Capture, token=Depends(local_session)):
    store().capture(case_id, request.revision, request.node_id, request.turn_id, request.agent_id, request.citation_id)
    return store().get(case_id)


@change_router.post('/{case_id}/decision')
def decide_change(case_id: str, request: Decision, token=Depends(local_session)):
    store().transition(case_id, request.revision, request.action, request.note, request.acknowledged)
    return store().get(case_id)


@change_router.post('/{case_id}/evidence/remove')
def remove_evidence(case_id: str, request: RemoveEvidence, token=Depends(local_session)):
    store().remove_evidence(case_id, request.revision, request.evidence_id)
    return store().get(case_id)


@change_router.post('/{case_id}/conversation')
def conversation(case_id: str, request: Ask, token=Depends(local_session)):
    workers = review_routes.store.workers
    if not workers.acquire(blocking=False):
        raise HTTPException(429, 'Agent analysis capacity is busy')
    turn_id = attempt = None
    try:
        db = store()
        turn_id, execute, attempt = db.reserve(case_id, request.revision, request.request_id,
                                             request.question, request.selected_id, request.automate, request.agent_id)
        if not execute:
            return db.get(case_id)
        case = db.get(case_id, graph=True)
        history = [{'question': turn['question'][:1500], 'selected_id': turn.get('selected_id'),
                    'answers': [{'agent_id': analysis['agent_id'], 'text': analysis['result']['answer'][:2000]}
                                for analysis in turn.get('analyses', [])]}
                   for turn in case['turns'] if turn['state'] == 'completed'][-6:]
        connection = connection_for(review_routes.store, token)
        rest = OllamaREST(connection, ai_guard(token))
        agents = ['trace-explorer', 'coverage-reviewer', 'change-analyst'] if request.automate else [request.agent_id]
        analyses = []
        selected = request.selected_id
        draft_context = {'fields': {field: case[field][:1200] for field in FIELDS},
                         'fields_truncated': [field for field in FIELDS if len(case[field]) > 1200],
                         'evidence_ids': [{'id': item['id'], 'node_id': item['node']['id']} for item in case['evidence'][:20]],
                         'evidence_total': len(case['evidence'])}
        for agent_id in agents:
            rest.check()
            result = GraphAgent(case['graph'], rest, agent_id).run(request.question, selected, history=history, dossier_context=draft_context)
            analyses.append({'agent_id': agent_id, 'result': result})
        ai_guard(token)()
        db.finish(case_id, turn_id, analyses, attempt)
        return db.get(case_id)
    except (ValueError, TypeError, KeyError, httpx.HTTPError):
        if turn_id and attempt:
            store().fail(case_id, turn_id, attempt)
        raise HTTPException(502, 'Agent analysis could not complete; the saved turn can be retried.') from None
    except Exception:
        if turn_id and attempt:
            store().fail(case_id, turn_id, attempt)
        raise
    finally:
        workers.release()


@change_router.post('/{case_id}/external')
def submit_external(case_id: str, request: Version, token=Depends(local_session)):
    case = store().get(case_id)
    if case['state'] != 'approved' or case['revision'] != request.revision:
        raise HTTPException(409, 'Approve this exact dossier version before external submission')
    raise HTTPException(501, 'External change-request creation is not configured. Existing ALM link actions remain separate.')


@change_router.get('/{case_id}/export')
def export_change(case_id: str, token=Depends(local_session)):
    case = store().get(case_id)
    if case['state'] != 'approved':
        raise HTTPException(409, 'Approve this dossier version before export')
    frozen = next(item for item in case['versions'] if item['version'] == case['version'])
    return {'case_id': case_id, 'digest': frozen['digest'], 'dossier': frozen['dossier'], 'audit': case['audit'],
            'turns': frozen['dossier'].get('turns', []),
            'conversation_integrity': ('Frozen conversation is included in the submitted digest.'
                if 'turns' in frozen['dossier'] else
                'Legacy version: conversation contents were not frozen. Live turns are excluded because their historical contents cannot be verified.'),
            'external_submission': 'Not submitted: external change creation is not configured.'}
