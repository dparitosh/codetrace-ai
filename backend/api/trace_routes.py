"""Code index + explicit OSLC lifecycle assertions -> materialized trace KG."""

import re
from typing import Annotated, Literal, Optional, Union
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from api.graph_routes import (GraphData, LocalGraphRequest, GitLabGraphRequest,
                              build_graph_from_files, generate_gitlab_graph)
from graph.traceability import materialize, neighborhood, as_jsonld

trace_router = APIRouter(tags=['Trace Knowledge Graph'])


def absolute_uri(value):
    parsed = urlsplit(value)
    if (len(value) > 2048 or re.search(r'[\s<>"{}|\\^`]', value)
            or parsed.scheme not in {'http', 'https', 'urn'}
            or (parsed.scheme in {'http', 'https'} and (not parsed.hostname or parsed.username or parsed.password))
            or (parsed.scheme == 'urn' and ':' not in parsed.path)):
        raise ValueError('Expected an absolute HTTP(S) or URN resource identifier without credentials')
    return value


URI = Annotated[str, AfterValidator(absolute_uri)]


class TraceModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Repository(TraceModel):
    uri: URI
    label: str = Field(min_length=1, max_length=256)
    revision: Optional[str] = Field(default=None, max_length=256)


class LifecycleResource(TraceModel):
    uri: URI
    kind: Literal['requirement', 'feature', 'variant', 'test', 'product']
    label: str = Field(min_length=1, max_length=512)
    provider_uri: Optional[URI] = None


class Endpoint(TraceModel):
    uri: Optional[URI] = None
    code_id: Optional[str] = Field(default=None, min_length=1, max_length=2048)

    @model_validator(mode='after')
    def one_identity(self):
        if (self.uri is None) == (self.code_id is None):
            raise ValueError('Provide exactly one of uri or code_id')
        return self


class LifecycleLink(TraceModel):
    source: Endpoint
    predicate: URI
    target: Endpoint
    asserted_by: URI = Field(description='URI identifying the assertion provider/export')


class TraceManifest(TraceModel):
    repository: Repository
    configuration_uri: Optional[URI] = None
    resources: list[LifecycleResource] = Field(default_factory=list, max_length=2000)
    links: list[LifecycleLink] = Field(default_factory=list, max_length=5000)

    @model_validator(mode='after')
    def unique_resources(self):
        uris = [item.uri for item in self.resources]
        if len(uris) != len(set(uris)):
            raise ValueError('Duplicate lifecycle resource URIs')
        return self


class TraceRequest(TraceModel):
    source: Union[LocalGraphRequest, GitLabGraphRequest]
    manifest: TraceManifest


class TraceQueryRequest(TraceRequest):
    start: Endpoint
    direction: Literal['incoming', 'outgoing', 'both'] = 'both'
    depth: int = Field(default=4, ge=0, le=12)
    max_nodes: int = Field(default=100, ge=1, le=500)
    predicates: list[URI] = Field(default_factory=list, max_length=32)


def build_trace(request):
    if isinstance(request.source, LocalGraphRequest):
        graph = build_graph_from_files(request.source)
    else:
        graph = generate_gitlab_graph(request.source)
    try:
        return materialize(graph, request.manifest.model_dump(), graph['metadata']['source_digest'])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@trace_router.post('/materialize', response_model=GraphData)
def materialize_trace(request: TraceRequest):
    return build_trace(request)


@trace_router.post('/query', response_model=GraphData)
def query_trace(request: TraceQueryRequest):
    from graph.traceability import code_uri
    data = build_trace(request)
    start = request.start.uri or code_uri(request.manifest.repository.uri, request.start.code_id)
    try:
        return neighborhood(data, start, request.direction, request.depth, request.max_nodes, request.predicates)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Trace start node was not found') from exc


@trace_router.post('/jsonld', responses={200: {'content': {'application/ld+json': {}}}})
def export_trace(request: TraceRequest):
    return JSONResponse(content=as_jsonld(build_trace(request)), media_type='application/ld+json')
