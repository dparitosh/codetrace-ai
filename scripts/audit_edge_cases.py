"""Read-only edge-case audit. FAIL means a reproduced unmet expectation.

Run with the local test dependencies: python scripts/audit_edge_cases.py
No network calls or persistent application-store writes are made.
"""
import json
import sys
import tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'codegraph_core')]

import httpx
from fastapi import HTTPException
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, DCTERMS
from starlette.requests import Request
from codegraph_core import CodeGraph
from core.config import settings
from core.connection_models import OSLCProvider
from services import oslc_service as os, workspace_service as ws
from services.oslc_store import OSLCStore, RM
from services.sbom_service import normalize
from services.companion_service import context_evidence, answer_question
from graph.traceability import as_jsonld
from api.oslc_routes import rdf_response
from api.review_routes import ReviewStore

results = []


def check(identifier, title, action):
    try:
        action()
        results.append((identifier, 'PASS', title))
    except AssertionError as exc:
        results.append((identifier, 'FAIL', title + ': ' + str(exc)))
    except Exception as exc:
        results.append((identifier, 'ERROR', title + ': ' + type(exc).__name__))


def expect(condition, message):
    assert condition, message


def node(identifier, kind='requirement', **properties):
    return {'id': identifier, 'label': identifier, 'type': kind, 'properties': properties}


def graph(nodes=None, edges=None):
    return {'nodes': nodes or [], 'edges': edges or [], 'metadata': {'snapshot_id': 'fixture'}}


def provider(identifier='p', **kwargs):
    return OSLCProvider(id=identifier, label=identifier, domain='RM', endpoint='https://alm.example/query',
                        allowed_base_url='https://alm.example/', auth_type='none', **kwargs)


def response(content):
    return httpx.Response(200, text=content, headers={'Content-Type': 'text/turtle'})


def ingest(content):
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(content))) as client:
        return os.ingest_provider(provider(), client)


def config_collision():
    providers = [provider('a', configuration_uri='urn:config:a'), provider('b', configuration_uri='urn:config:b')]
    def collect(p, _):
        return ([{'uri': 'https://alm.example/r', 'kind': 'requirement', 'label': p.id}], [],
                {'https://alm.example/r': {'configuration_uri': p.configuration_uri}}, [], {'id': p.id})
    with patch.object(settings, 'OSLC_PROVIDERS', providers), patch.object(os, 'ingest_provider', collect):
        resources, _, _, _, _ = os.collect_oslc('workspace')
    expect(len(resources) == 2, f'two configuration versions collapsed to {len(resources)} resource')


def coverage():
    repo = SimpleNamespace(uri='urn:audit:repo', label='Repo', manifest_path=None)
    resources = [{'uri': 'urn:audit:req', 'kind': 'requirement', 'label': 'Req'},
                 {'uri': 'urn:audit:change', 'kind': 'change_request', 'label': 'Change'}]
    links = [{'source': {'uri': 'urn:audit:req'}, 'target': {'uri': 'urn:audit:change'},
              'predicate': RM + 'trackedBy', 'asserted_by': 'urn:audit:provider'}]
    code = graph(); code['metadata']['source_digest'] = 'digest'; code['metadata']['files'] = 0
    with patch.object(ws, 'repository_config', return_value=repo), patch.object(ws, 'read_repository', return_value=(code, None)), \
         patch.object(ws, 'collect_oslc', return_value=(resources, links, {}, [], [])), \
         patch.object(ws, 'pipeline_context', return_value=([], [])), patch.object(ws, '_build_architecture_audit', return_value={}):
        result = ws.build_managed_snapshot('workspace')
    expect(result['metadata']['coverage']['linked_requirements'] == 0, 'a tracking-only link counts as implementation/validation coverage')


def collection():
    data = ingest('<https://alm.example/c> a <http://open-services.net/ns/rm#RequirementCollection> .')
    expect(data[0][0]['kind'] != 'requirement', 'collection normalized as an individual requirement')


def cyclic_pages():
    content = '<https://alm.example/page> <http://open-services.net/ns/core#nextPage> <https://alm.example/query> .'
    expect(ingest(content)[4]['status'] != 'ready', 'self-looping pagination reported ready')


def export_tombstone():
    exported = as_jsonld(graph([node('urn:r', deleted=True)]))
    expect('deleted' in json.dumps(exported), 'deletion state is absent from RDF export')


def export_outcome():
    exported = as_jsonld(graph([node('urn:t', 'test_result', outcome='failed')]))
    expect('failed' in json.dumps(exported), 'test-result outcome is absent from RDF export')


def empty_title():
    with tempfile.TemporaryDirectory() as directory:
        store = OSLCStore(Path(directory) / 'oslc.sqlite')
        store.publish('workspace', graph([node('urn:r')]), 0, 'audit')
        _, total = store.query('workspace', title='')
    expect(total == 0, f'empty-title filter returned {total} nonempty titles')


def content_etag():
    rdf = Graph(); rdf.add((URIRef('urn:r'), DCTERMS.title, Literal('R')))
    def request(accept):
        return Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [(b'accept', accept.encode())]})
    turtle = rdf_response(rdf, request('text/turtle'), '"same"')
    xml = rdf_response(rdf, request('application/rdf+xml'), '"same"')
    expect(turtle.body == xml.body or turtle.headers['etag'] != xml.headers['etag'], 'different representation bytes share a strong ETag')


def spdx_license():
    components, _ = normalize({'spdxVersion': 'SPDX-2.3', 'packages': [{'SPDXID': 'SPDXRef-p', 'name': 'p', 'licenseDeclared': 'MIT'}]})
    expect('MIT' in json.dumps(components[0]), 'declared license discarded as NOASSERTION')


def optional_bom_ref():
    try:
        normalize({'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'components': [{'type': 'library', 'name': 'p'}]})
    except ValueError:
        expect(False, 'valid component without optional bom-ref is rejected')


def python_modules():
    scanner = CodeGraph(); scanner.scan_sources([{'path': 'a.py', 'content': 'x=1'}, {'path': 'a.ts', 'content': 'function f() {}'}])
    expect(sum(n.type == 'module' for n in scanner.g.nodes.values()) == 2, 'same-stem modules in different languages collide')


def local_variables():
    scanner = CodeGraph(); scanner.scan_sources([{'path': 'a.py', 'content': 'def f():\n    local_value = 1\n    return local_value\n'}])
    expect(any(n.type == 'variable' and n.attrs.get('name') == 'local_value' for n in scanner.g.nodes.values()), 'function-local variable missing')


def conditional_definitions():
    scanner = CodeGraph(); scanner.scan_sources([{'path': 'a.py', 'content': 'if True:\n    def f():\n        pass\n'}])
    expect(any(n.type == 'function' for n in scanner.g.nodes.values()), 'valid conditional function definition missing')


def property_accessors():
    scanner = CodeGraph(); scanner.scan_sources([{'path': 'a.py', 'content': 'class C:\n    @property\n    def value(self):\n        return 1\n    @value.setter\n    def value(self, x):\n        pass\n'}])
    expect(sum(n.type == 'function' for n in scanner.g.nodes.values()) == 2, 'getter and setter merged into one symbol')


def recommendation_budget():
    data = graph([node('urn:r', domain='RM')]); data['metadata']['coverage'] = {'unlinked_requirements': ['urn:missing:' + str(i) for i in range(2000)]}
    captured = []
    class AIClient:
        def __init__(self, **_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def stream(self, *_, **kwargs):
            captured.append(json.loads(kwargs['json']['messages'][1]['content']))
            raise httpx.ConnectError('fixture offline')
    with patch.object(settings, 'AI_PROVIDER', 'ollama'), patch('services.companion_service.httpx.Client', AIClient):
        answer_question(data, 'coverage')
    expect(len(captured[0]['coverage']['unlinked_requirements']) <= settings.AI_CONTEXT_NODES, 'entire gap-ID list bypasses the AI evidence budget')


def false_gap():
    from services.companion_service import evidence_answer
    data = graph([node('urn:a'), node('urn:b')]); data['edges'] = [{'source': 'urn:a', 'target': 'urn:b', 'type': RM+'validatedBy', 'properties': {}}]
    with patch.object(settings, 'AI_CONTEXT_NODES', 1):
        citations, edges = context_evidence(data, 'explain', 'urn:a')
        answer = evidence_answer(data, citations, edges, 'urn:a')
    expect('That is a trace gap' not in answer, 'bounded absence is asserted as a trace gap without coverage evidence')


def origin_roundtrip():
    with tempfile.TemporaryDirectory() as directory:
        store = OSLCStore(Path(directory)/'oslc.sqlite')
        store.publish('workspace', graph([node('https://alm.example/change', 'change_request', domain='CM', status='open')]), 0, 'audit')
        record = store.by_origin('workspace', 'https://alm.example/change')
        rdf = Graph().parse(data=record['body'], format='nt')
        output = os.ingest_provider(provider(), None, supplied_graph=rdf)
    expect(any(item.get('status') == 'open' for item in output[2].values()), 'published CM status cannot be re-ingested as CM status')


def read_only_cleanup():
    clock = [0.0]; store = ReviewStore(clock=lambda: clock[0]); token = store.create()['token']
    clock[0] = settings.SESSION_IDLE_SECONDS + settings.SESSION_MAX_SECONDS + 1
    try: store.info(token)
    except HTTPException as error: expect(error.status_code == 401, 'expired token accepted'); return
    expect(False, 'expired token accepted')


def discovery_catalog():
    from services.oslc_client import OSLCClient
    p = provider(discovery_url='https://alm.example/catalog')
    seen = []
    def fetch(request):
        seen.append(request.url.path)
        if request.url.path == '/catalog':
            return response('<https://alm.example/catalog> <http://open-services.net/ns/core#serviceProvider> <https://alm.example/provider> .')
        return response('<https://alm.example/capability> <http://open-services.net/ns/core#queryBase> <https://alm.example/query> .')
    with OSLCClient(p, transport=httpx.MockTransport(fetch)) as client:
        result = client.discovery()
    expect(bool(result['query_capabilities']), 'catalog serviceProvider was not followed; empty discovery reported ready')


def trs_inline_stub():
    p = OSLCProvider(id='trs', label='TRS', domain='TRS', endpoint='https://alm.example/trs', allowed_base_url='https://alm.example/', auth_type='none')
    seen = []
    def fetch(request):
        seen.append(request.url.path)
        if request.url.path == '/trs':
            return response('<https://alm.example/trs> a <http://open-services.net/ns/core/trs#TrackedResourceSet>; <http://open-services.net/ns/core/trs#base> <https://alm.example/base> .')
        if request.url.path == '/base':
            return response('<https://alm.example/base> <http://www.w3.org/2000/01/rdf-schema#member> <https://alm.example/r> . <https://alm.example/r> a <http://open-services.net/ns/rm#Requirement> .')
        return response('<https://alm.example/r> a <http://open-services.net/ns/rm#Requirement>; <http://purl.org/dc/terms/title> "Full requirement" .')
    with httpx.Client(transport=httpx.MockTransport(fetch)) as client:
        result = os.ingest_provider(p, client)
    expect('/r' in seen and any(item['label'] == 'Full requirement' for item in result[0]), 'type-only base stub suppresses retrieval of full resource')


def changed_snapshot():
    repo = SimpleNamespace(uri='urn:audit:repo', label='Repo', manifest_path=None)
    code = graph(); code['metadata'].update(source_digest='same', files=0)
    with patch.object(ws, 'repository_config', return_value=repo), patch.object(ws, 'read_repository', return_value=(code, None)), \
         patch.object(ws, 'collect_oslc', return_value=([], [], {}, [], [])), patch.object(ws, 'pipeline_context', return_value=([], [])), \
         patch.object(ws, '_build_architecture_audit', return_value={}), patch.object(ws, 'datetime') as dates:
        dates.now.side_effect = [datetime(2026, 10, 18, tzinfo=timezone.utc), datetime(2026, 10, 18, 0, 0, 1, tzinfo=timezone.utc)]
        first = ws.build_managed_snapshot('workspace'); second = ws.build_managed_snapshot('workspace')
    with tempfile.TemporaryDirectory() as directory:
        store = OSLCStore(Path(directory)/'oslc.sqlite')
        store.publish('workspace', first, 0, 'audit')
        outcome = store.publish('workspace', second, 1, 'audit')
    expect(outcome.get('changed_resources', 0) == 0, 'identical evidence republished as resource changes solely due to indexed_at/snapshot stamp')


def xml_entity_encoding():
    content = '''<?xml version="1.0" encoding="utf-16"?>
<!DOCTYPE rdf:RDF [<!ENTITY harmless "fixture-value">]>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/terms/">
<rdf:Description rdf:about="urn:audit:r"><dc:title>&harmless;</dc:title></rdf:Description></rdf:RDF>'''
    try: os.parse_rdf(content.encode('utf-16'), 'application/rdf+xml')
    except ValueError: return
    expect(False, 'UTF-16 internal entity declaration bypassed the explicit entity ban')


def schema_type():
    from api.oslc_routes import type_for_kind
    with tempfile.TemporaryDirectory() as directory:
        store = OSLCStore(Path(directory)/'oslc.sqlite')
        store.publish('workspace', graph([node('urn:audit:feature', 'feature', domain='CODE')]), 0, 'audit')
        record = store.by_origin('workspace', 'urn:audit:feature')
    rdf = Graph().parse(data=record['body'], format='nt')
    expect(URIRef(type_for_kind('feature')) in set(rdf.objects(None, RDF.type)), 'published feature type differs from its advertised shape/query type')


def endpoint_controls():
    for url in ['https://other.example/r', 'https://alm.example/../private', 'https://alm.example/%252e%252e/private']:
        try: os.allowed_url(provider(), url)
        except ValueError: continue
        expect(False, 'unsafe URL accepted')


def external_context():
    try: os.parse_rdf(b'{"@context":"https://example.invalid/context"}', 'application/ld+json')
    except ValueError: return
    expect(False, 'external JSON-LD context accepted')


def duplicate_sbom():
    try: normalize({'bomFormat':'CycloneDX','specVersion':'1.5','components':[{'name':'p','bom-ref':'r'},{'name':'q','bom-ref':'r'}]})
    except ValueError: return
    expect(False, 'duplicate component references accepted')


def unknown_sbom():
    try: normalize({'bomFormat':'CycloneDX','specVersion':'1.5','components':[{'name':'p','bom-ref':'r'}], 'dependencies':[{'ref':'r','dependsOn':['missing']}]})
    except ValueError: return
    expect(False, 'dangling dependency accepted')


def trs_incoming_recreation():
    from services.trs_cache import collect_incremental
    p = OSLCProvider(id='trs', label='TRS', domain='TRS', endpoint='https://alm.example/trs', allowed_base_url='https://alm.example/', auth_type='none')
    phase = [1]
    prefix = '@prefix trs: <http://open-services.net/ns/core/trs#> . @prefix rm: <http://open-services.net/ns/rm#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> . '
    def fetch(request):
        path = request.url.path
        if path == '/trs':
            body = '<https://alm.example/trs> a trs:TrackedResourceSet; trs:base <https://alm.example/base>; trs:changeLog <https://alm.example/log> .'
        elif path == '/base':
            body = '<https://alm.example/base> rdfs:member <https://alm.example/a>, <https://alm.example/b>; trs:cutoffEvent rdf:nil .'
        elif path == '/log':
            body = ' '.join(f'<https://alm.example/e/{i}> a trs:{action}; trs:changed <https://alm.example/b>; trs:order {i} .' for i, action in enumerate(['Creation','Deletion','Creation'][:phase[0]], 1))
        elif path == '/a':
            body = '<https://alm.example/a> a rm:Requirement; rm:decomposedBy <https://alm.example/b> .'
        else:
            body = '<https://alm.example/b> a rm:Requirement .'
        return response(prefix + body)
    with tempfile.TemporaryDirectory() as directory, patch.object(settings, 'TRS_CACHE_PATH', Path(directory)/'trs.sqlite'), httpx.Client(transport=httpx.MockTransport(fetch)) as client:
        initial = collect_incremental(p, client)
        expect(any(link['source']['uri'].endswith('/a') for link in initial[1]), 'fixture missing original link')
        phase[0] = 2; collect_incremental(p, client)
        phase[0] = 3; result = collect_incremental(p, client)
    expect(any(link['source']['uri'].endswith('/a') and link['target'].get('uri', '').endswith('/b') for link in result[1]), 'deleting/recreating target permanently loses unchanged source assertion')


def origin_default_port():
    try: os.allowed_url(provider(), 'https://alm.example:443/resource')
    except ValueError: expect(False, 'equivalent explicit default port rejected as another origin')


def capacity_bypass():
    from api.graph_routes import LocalGraphRequest, generate_local_graph
    from api import review_routes
    held = []
    try:
        while review_routes.store.workers.acquire(blocking=False): held.append(True)
        try:
            generate_local_graph(LocalGraphRequest(files=[{'path':'a.py','content':'x=1'}]))
        except HTTPException as error:
            expect(error.status_code == 429, 'capacity rejection must return HTTP 429')
        else:
            expect(False, 'direct graph route computed while all configured analysis permits were exhausted')
    finally:
        for _ in held: review_routes.store.workers.release()


def git_local_filter():
    from services.git_isolation import git_command, git_environment
    with tempfile.TemporaryDirectory(prefix='codetrace-audit-filter-') as directory:
        root = Path(directory); repo = root/'repo'; repo.mkdir()
        marker = root/'filter-ran'
        helper = root/'filter.py'
        helper.write_text('import sys\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("audit fixture")\nsys.stdout.write(sys.stdin.read())\n', encoding='utf-8')
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
        git('init')
        git('config', 'filter.audit.clean', '"' + sys.executable.replace('\\','/') + '" "' + str(helper).replace('\\','/') + '"')
        (repo/'.gitattributes').write_text('*.py filter=audit\n', encoding='utf-8')
        (repo/'a.py').write_text('x=1\n', encoding='utf-8'); git('add', '.')
        marker.unlink(missing_ok=True)
        (repo/'a.py').write_text('x=2\n', encoding='utf-8')
        import os as system_os, time
        system_os.utime(repo/'a.py', (time.time() + 3, time.time() + 3))
        from services.workspace_service import read_repository
        from core.connection_models import ManagedRepository
        read_repository(ManagedRepository(id='audit', label='Audit', path=str(repo)))
        expect(not marker.exists(), 'managed repository inspection executed a repository-local clean filter')


def orm_source_fields():
    import asyncio
    import sqlalchemy
    from sqlalchemy.orm import sessionmaker
    from database.connection import Base
    from database.models import Repository
    from database.enhanced_models import EnhancedGraphNode
    from services.repository_service import RepositoryService
    engine = sqlalchemy.create_engine('sqlite://')
    try:
        Base.metadata.create_all(engine)
        service = RepositoryService(); service.Session = sessionmaker(bind=engine)
        with service.get_session() as session, session.begin():
            session.add(Repository(id=1, owner='audit', name='fixture', full_name='audit/fixture', url='urn:audit:repo'))
        asyncio.run(service.save_analysis_result(1, {'graph': graph([node('urn:audit:file', 'file', path='src/file.py', start=7)])}))
        with service.get_session() as session:
            stored = session.query(EnhancedGraphNode).one()
            expect(stored.file_path == 'src/file.py' and stored.line_number == 7, 'typed source-location columns are empty despite properties.path/start in the active graph contract')
    finally: engine.dispose()


if __name__ == '__main__':
    cases = [
        ('A01', 'Configuration-scoped resource identity', config_collision),
        ('A02', 'Requirement implementation/validation coverage', coverage),
        ('A03', 'Requirement collection domain type', collection),
        ('A04', 'Cyclic OSLC page completeness', cyclic_pages),
        ('A05', 'JSON-LD deletion evidence', export_tombstone),
        ('A06', 'JSON-LD QM outcome evidence', export_outcome),
        ('A07', 'Exact empty-title query', empty_title),
        ('A08', 'Representation-specific strong ETags', content_etag),
        ('A09', 'SPDX declared license preservation', spdx_license),
        ('A10', 'CycloneDX optional references', optional_bom_ref),
        ('A11', 'Same-stem source identities', python_modules),
        ('A12', 'Function-local variable extraction', local_variables),
        ('A13', 'Conditional Python definitions', conditional_definitions),
        ('A14', 'Python property accessor identities', property_accessors),
        ('A15', 'AI coverage context budget', recommendation_budget),
        ('A16', 'Bounded retrieval gap claims', false_gap),
        ('A17', 'CM publication round trip', origin_roundtrip),
        ('A18', 'Expired session access rejection', read_only_cleanup),
        ('A19', 'Service catalog discovery traversal', discovery_catalog),
        ('A20', 'TRS inline stub dereferencing', trs_inline_stub),
        ('A21', 'Unchanged evidence TRS churn', changed_snapshot),
        ('A22', 'RDF/XML encoded entity rejection', xml_entity_encoding),
        ('A23', 'Publication shape/type consistency', schema_type),
        ('A24', 'Origin and traversal URL restrictions', endpoint_controls),
        ('A25', 'Remote JSON-LD context rejection', external_context),
        ('A26', 'Duplicate SBOM references', duplicate_sbom),
        ('A27', 'Dangling SBOM dependencies', unknown_sbom),
        ('A28', 'TRS incoming links after target recreation', trs_incoming_recreation),
        ('A29', 'Equivalent HTTPS default-port origins', origin_default_port),
        ('A30', 'Analysis concurrency across direct routes', capacity_bypass),
        ('A31', 'Repository-local Git filter isolation', git_local_filter),
        ('A33', 'ORM source-location mapping', orm_source_fields),
    ]
    for identifier, title, action in cases:
        check(identifier, title, action)
    for row in results: print(' | '.join(row))
    print(json.dumps({'checked': len(results), 'unmet_expectations': sum(row[1] == 'FAIL' for row in results)}))
