"""OSLC server profile plus approved publication and collaboration gateway."""
import hashlib
import json
import re
import secrets
from functools import lru_cache
from typing import Optional, Literal
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
from rdflib.namespace import RDF, RDFS, DCTERMS

from api import review_routes
from core.config import settings
from graph.traceability import TYPE_URIS, CT
from services.oslc_service import parse_rdf, server_secret
from services.oslc_client import OSLCClient
from services.oslc_store import OSLCStore, OSLC, AM, QM, TRS, LINK_PREDICATES, graph_from_body

oslc_router = APIRouter(tags=['OSLC Server'])
collaboration_router = APIRouter(tags=['OSLC Collaboration'])
KINDS = sorted(set(TYPE_URIS) | {'repository', 'package', 'file', 'module', 'class', 'function', 'method', 'variable', 'symbol', 'external_symbol', 'external_resource', 'build', 'feature', 'variant', 'product'})


@lru_cache(maxsize=1)
def publication_store():
    return OSLCStore()


def base():
    return settings.OSLC_PUBLIC_BASE_URL.rstrip('/')


def server_auth(request: Request, write=False):
    if write and not settings.OSLC_SERVER_ALLOW_WRITES:
        raise HTTPException(403, 'External OSLC resource writes are disabled')
    expected = server_secret(settings.OSLC_SERVER_WRITE_TOKEN_ENV if write else settings.OSLC_SERVER_TOKEN_ENV)
    if not expected:
        raise HTTPException(503, 'OSLC server access token is not configured')
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not secrets.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, 'OSLC bearer token is required', headers={'WWW-Authenticate': 'Bearer'})


def rdf_response(graph, request, etag=None, headers=None):
    accept = request.headers.get('Accept', '*/*')
    choices = [('text/turtle', 'turtle'), ('application/rdf+xml', 'xml'), ('application/ld+json', 'json-ld')]
    ranks = []
    for index, (media, format) in enumerate(choices):
        matches = []
        for part in accept.split(','):
            pieces = [piece.strip() for piece in part.split(';')]
            media_range = pieces[0]
            if media_range not in {media, '*/*', media.split('/')[0] + '/*'}:
                continue
            try:
                quality = next((float(piece[2:]) for piece in pieces[1:] if piece.startswith('q=')), 1.0)
            except ValueError:
                continue
            specificity = 2 if media_range == media else 1 if media_range != '*/*' else 0
            matches.append((specificity, quality))
        if matches:
            specificity, quality = max(matches)
            if quality > 0:
                ranks.append((quality, specificity, -index, media, format))
    if not ranks:
        raise HTTPException(406, 'Supported representations: text/turtle, application/rdf+xml, application/ld+json')
    _, _, _, media, format = max(ranks)
    response_headers = {'Vary': 'Accept', 'OSLC-Core-Version': '2.0', 'Cache-Control': 'private, no-cache', **(headers or {})}
    if etag:
        response_headers['ETag'] = etag
        if etag in request.headers.get('If-None-Match', '').split(',') or request.headers.get('If-None-Match') == '*':
            return Response(status_code=304, headers=response_headers)
    return Response(graph.serialize(format=format), media_type=media, headers=response_headers)


def type_for_kind(kind):
    return TYPE_URIS.get(kind, AM + 'Resource' if kind in {'repository', 'package', 'file', 'module', 'class', 'function', 'method', 'variable', 'symbol', 'external_symbol'} else CT + kind)


@oslc_router.get('/catalog')
def service_catalog(request: Request):
    server_auth(request)
    graph = Graph(); subject = URIRef(base() + '/catalog')
    graph.add((subject, RDF.type, URIRef(OSLC + 'ServiceProviderCatalog')))
    graph.add((subject, DCTERMS.title, RDFLiteral('CodeTrace lifecycle intelligence')))
    for source in settings.MANAGED_REPOSITORIES:
        uri = URIRef(base() + '/providers/' + source.id)
        graph.add((subject, URIRef(OSLC + 'serviceProvider'), uri))
        graph.add((uri, DCTERMS.title, RDFLiteral(source.label)))
    return rdf_response(graph, request)


@oslc_router.get('/providers/{source_id}')
def service_provider(source_id: str, request: Request):
    server_auth(request)
    source = next((item for item in settings.MANAGED_REPOSITORIES if item.id == source_id), None)
    if not source:
        raise HTTPException(404, 'Managed service provider was not found')
    graph = Graph(); subject = URIRef(base() + '/providers/' + source_id)
    graph.add((subject, RDF.type, URIRef(OSLC + 'ServiceProvider')))
    graph.add((subject, DCTERMS.title, RDFLiteral(source.label)))
    for domain in ('am', 'rm', 'cm', 'qm'):
        service = BNode('service-' + domain); query = BNode('query-' + domain)
        graph.add((subject, URIRef(OSLC + 'service'), service))
        graph.add((service, RDF.type, URIRef(OSLC + 'Service')))
        graph.add((service, URIRef(OSLC + 'domain'), URIRef('http://open-services.net/ns/' + domain + '#')))
        graph.add((service, URIRef(OSLC + 'queryCapability'), query))
        graph.add((query, RDF.type, URIRef(OSLC + 'QueryCapability')))
        graph.add((query, DCTERMS.title, RDFLiteral(domain.upper() + ' resource query')))
        graph.add((query, URIRef(OSLC + 'queryBase'), URIRef(base() + '/query/' + source_id)))
        for kind in KINDS:
            type_uri = type_for_kind(kind)
            if '/ns/' + domain + '#' in type_uri:
                graph.add((query, URIRef(OSLC + 'resourceType'), URIRef(type_uri)))
                graph.add((query, URIRef(OSLC + 'resourceShape'), URIRef(base() + '/shapes/' + kind)))
    return rdf_response(graph, request)


@oslc_router.get('/shapes/{kind}')
def resource_shape(kind: str, request: Request):
    server_auth(request)
    if kind not in KINDS:
        raise HTTPException(404, 'Resource shape was not found')
    graph = Graph(); subject = URIRef(base() + '/shapes/' + kind)
    graph.add((subject, RDF.type, URIRef(OSLC + 'ResourceShape')))
    graph.add((subject, DCTERMS.title, RDFLiteral('CodeTrace ' + kind.replace('_', ' ') + ' shape')))
    graph.add((subject, URIRef(OSLC + 'describes'), URIRef(type_for_kind(kind))))
    properties = [(str(DCTERMS.title), 'title', OSLC + 'String', True, OSLC + 'Exactly-one'),
                  (str(DCTERMS.identifier), 'identifier', OSLC + 'String', True, OSLC + 'Exactly-one'),
                  (CT + 'sourceIdentity', 'sourceIdentity', OSLC + 'Resource', True, OSLC + 'Exactly-one')]
    properties.extend((predicate, predicate.split('#')[-1].split(':')[-1], OSLC + 'Resource', False, OSLC + 'Zero-or-many') for predicate in sorted(LINK_PREDICATES))
    if kind == 'test_result':
        properties.append((QM + 'status', 'status', OSLC + 'String', True, OSLC + 'Zero-or-one'))
    for index, (predicate, name, value_type, read_only, occurs) in enumerate(properties):
        prop = BNode('property-' + str(index))
        graph.add((subject, URIRef(OSLC + 'property'), prop))
        graph.add((prop, RDF.type, URIRef(OSLC + 'Property')))
        graph.add((prop, URIRef(OSLC + 'name'), RDFLiteral(name)))
        graph.add((prop, URIRef(OSLC + 'propertyDefinition'), URIRef(predicate)))
        graph.add((prop, URIRef(OSLC + 'valueType'), URIRef(value_type)))
        graph.add((prop, URIRef(OSLC + 'readOnly'), RDFLiteral(read_only)))
        graph.add((prop, URIRef(OSLC + 'occurs'), URIRef(occurs)))
    return rdf_response(graph, request)


@oslc_router.get('/resources/{resource_id}')
def get_resource(resource_id: str, request: Request):
    server_auth(request)
    record = publication_store().resource(resource_id)
    return rdf_response(graph_from_body(record['body']), request, record['etag'])


@oslc_router.put('/resources/{resource_id}')
async def put_resource(resource_id: str, request: Request):
    server_auth(request, write=True)
    expected = request.headers.get('If-Match')
    if not expected or expected == '*' or expected.startswith('W/'):
        raise HTTPException(428, 'A strong, exact If-Match resource ETag is required')
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > settings.OSLC_MAX_RESPONSE_BYTES:
            raise HTTPException(413, 'OSLC representation exceeds the configured size limit')
        content.extend(chunk)
    try:
        graph = parse_rdf(bytes(content), request.headers.get('Content-Type', '').split(';')[0])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record = publication_store().update(resource_id, graph, expected, 'oslc-client')
    return rdf_response(graph_from_body(record['body']), request, record['etag'])


@oslc_router.get('/query/{source_id}')
def query_resources(source_id: str, request: Request, page: int = Query(1, ge=1),
                    page_size: int = Query(50, alias='oslc.pageSize', ge=1, le=200),
                    where: Optional[str] = Query(None, alias='oslc.where', max_length=1000)):
    server_auth(request)
    if not any(item.id == source_id for item in settings.MANAGED_REPOSITORIES):
        raise HTTPException(404, 'Managed service provider was not found')
    kind = title = None
    if where:
        type_match = re.fullmatch(r'rdf:type\s*=\s*<([^<>]+)>', where)
        title_match = re.fullmatch(r'dcterms:title\s*=\s*("(?:[^"\\]|\\.)*")', where)
        if type_match:
            kinds = [value for value in KINDS if type_for_kind(value) == type_match[1]]
            kind = kinds if kinds else ['__unsupported_type__']
        elif title_match:
            title = json.loads(title_match[1])
        else:
            raise HTTPException(400, 'Supported oslc.where clauses: rdf:type=<URI> or dcterms:title="title"')
    store = publication_store()
    records, total = store.query(source_id, page, page_size, kind, title)
    graph = Graph(); subject = URIRef(base() + '/query/' + source_id)
    graph.add((subject, RDF.type, URIRef(OSLC + 'ResponseInfo')))
    graph.add((subject, URIRef(OSLC + 'totalCount'), RDFLiteral(total)))
    for record in records:
        uri = URIRef(store.uri(record['id']))
        graph.add((subject, RDFS.member, uri))
        graph += graph_from_body(record['body'])
    headers = {}
    if page * page_size < total:
        parameters = {'page': page + 1, 'oslc.pageSize': page_size}
        if where:
            parameters['oslc.where'] = where
        next_url = base() + '/query/' + source_id + '?' + urlencode(parameters)
        graph.add((subject, URIRef(OSLC + 'nextPage'), URIRef(next_url)))
        headers['Link'] = '<' + next_url + '>; rel="next"'
    return rdf_response(graph, request, headers=headers)


def change_graph(store, events):
    graph = Graph()
    for event in events:
        uri = URIRef(base() + '/trs/events/' + str(event['sequence']))
        graph.add((uri, RDF.type, URIRef(TRS + event['action'])))
        graph.add((uri, URIRef(TRS + 'changed'), URIRef(store.uri(event['resource_id']))))
        graph.add((uri, URIRef(TRS + 'order'), RDFLiteral(event['sequence'])))
        graph.add((uri, DCTERMS.created, RDFLiteral(event['at'])))
    return graph


@oslc_router.get('/trs')
def tracked_resource_set(request: Request):
    server_auth(request)
    store = publication_store(); initial = store.base(); events = store.events(limit=50)
    graph = change_graph(store, events); subject = URIRef(base() + '/trs'); log = BNode('recent-change-log')
    graph.add((subject, RDF.type, URIRef(TRS + 'TrackedResourceSet')))
    graph.add((subject, URIRef(TRS + 'base'), URIRef(base() + '/trs/base/' + str(initial['id']))))
    graph.add((subject, URIRef(TRS + 'changeLog'), log)); graph.add((log, RDF.type, URIRef(TRS + 'ChangeLog')))
    for event in events:
        graph.add((log, URIRef(TRS + 'change'), URIRef(base() + '/trs/events/' + str(event['sequence']))))
    if events and events[-1]['sequence'] > 1:
        graph.add((log, URIRef(TRS + 'previous'), URIRef(base() + '/trs/changelog?before=' + str(events[-1]['sequence'] - 1))))
    return rdf_response(graph, request)


@oslc_router.get('/trs/events/{sequence}')
def trs_event(sequence: int, request: Request):
    server_auth(request)
    store = publication_store()
    return rdf_response(change_graph(store, [store.event(sequence)]), request)


@oslc_router.get('/trs/base/{base_id}')
def trs_base(base_id: int, request: Request, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200)):
    server_auth(request)
    store = publication_store(); record = store.base(base_id); members = json.loads(record['members'])
    subject = URIRef(base() + '/trs/base/' + str(base_id)); graph = Graph()
    graph.add((subject, RDF.type, URIRef('http://www.w3.org/ns/ldp#Container')))
    graph.add((subject, URIRef(TRS + 'cutoffEvent'), URIRef(base() + '/trs/events/' + str(base_id)) if base_id else RDF.nil))
    for resource_id in members[(page - 1) * page_size:page * page_size]:
        graph.add((subject, URIRef('http://www.w3.org/ns/ldp#contains'), URIRef(store.uri(resource_id))))
    headers = {}
    if page * page_size < len(members):
        next_url = str(subject) + '?' + urlencode({'page': page + 1, 'page_size': page_size})
        headers['Link'] = '<' + next_url + '>; rel="next"'
    return rdf_response(graph, request, headers=headers)


@oslc_router.get('/trs/changelog')
def trs_changelog(request: Request, before: Optional[int] = Query(None, ge=1)):
    server_auth(request)
    store = publication_store(); events = store.events(before, 50)
    graph = change_graph(store, events); subject = URIRef(base() + '/trs/changelog' + ('?before=' + str(before) if before else ''))
    graph.add((subject, RDF.type, URIRef(TRS + 'ChangeLog')))
    for event in events:
        graph.add((subject, URIRef(TRS + 'change'), URIRef(base() + '/trs/events/' + str(event['sequence']))))
    if events and events[-1]['sequence'] > 1:
        graph.add((subject, URIRef(TRS + 'previous'), URIRef(base() + '/trs/changelog?before=' + str(events[-1]['sequence'] - 1))))
    return rdf_response(graph, request)


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_id: str = Field(min_length=1, max_length=128)
    expected_version: int = Field(ge=0)


def session_owner(token):
    review_routes.store.info(token, touch=True)
    return hashlib.sha256(token.encode()).hexdigest()


@collaboration_router.get('/status')
def publication_status(source_id: str, x_codetrace_session: Optional[str] = Header(None)):
    session_owner(x_codetrace_session)
    if not any(item.id == source_id for item in settings.MANAGED_REPOSITORIES):
        raise HTTPException(404, 'Managed source was not found')
    return {**publication_store().publication(source_id), 'public_catalog': base() + '/catalog',
            'read_access_configured': bool(server_secret(settings.OSLC_SERVER_TOKEN_ENV)),
            'external_writes_enabled': settings.OSLC_SERVER_ALLOW_WRITES}


@collaboration_router.post('/publish')
def publish_snapshot(request: PublishRequest, x_codetrace_session: Optional[str] = Header(None)):
    owner = session_owner(x_codetrace_session)
    record = review_routes.store.get(x_codetrace_session, request.review_id, export=True)
    graph = record.get('result'); source_id = graph.get('metadata', {}).get('source_id') if graph else None
    if record['kind'] != 'graph' or not source_id:
        raise HTTPException(422, 'Only an approved managed graph can be published')
    return publication_store().publish(source_id, graph, request.expected_version, owner)


@collaboration_router.get('/discovery/{provider_id}')
def discover_provider(provider_id: str, x_codetrace_session: Optional[str] = Header(None)):
    session_owner(x_codetrace_session)
    provider = next((item for item in settings.OSLC_PROVIDERS if item.id == provider_id), None)
    if provider is None or not provider.endpoint:
        raise HTTPException(404, 'Network OSLC provider was not found')
    try:
        with OSLCClient(provider) as client:
            return client.discovery()
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, 'Service discovery failed. Check central provider settings and credentials.') from exc
