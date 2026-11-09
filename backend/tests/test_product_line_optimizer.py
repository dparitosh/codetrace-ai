import base64
import hashlib
import io
import json
import zipfile
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from api import review_routes
from api.graph_routes import LocalGraphRequest, build_graph_from_files
from core.config import settings
from core.optimization_models import OptimizationOptions, ProductUnit
from services.product_line_optimizer import analyze, digest, rank_order_clustering, csv_matrix

BODY = 'def work(value):\n    one = value + 1\n    two = one * 2\n    return two\n'

def snapshot():
    return build_graph_from_files(LocalGraphRequest(files=[
        {'path':'app.py','content':'import shared.a\nimport shared.b\n'},
        {'path':'shared/a.py','content':'# module a\n'+BODY},
        {'path':'shared/b.py','content':'# module b\n'+BODY},
        {'path':'tests/test_shared.py','content':BODY}]))

def options(**kw):
    return OptimizationOptions(units=[ProductUnit(id='app',entrypoints=['app.py'])],minimum_function_lines=3,wrapper_lines=1,**kw)


def test_roc_is_deterministic_and_bounded_with_disconnected_and_empty_rows():
    rows={'a':{'u1'},'b':{'u1','u2'},'c':{'u2'},'empty':set()}
    first=rank_order_clustering(rows,['u2','u1'])
    assert first==rank_order_clustering(dict(reversed(list(rows.items()))),['u1','u2'])
    assert set(first[0])==set(rows) and set(first[1])=={'u1','u2'} and first[2]<=20


def test_projection_uses_real_parser_fingerprints_and_excludes_tests():
    result=analyze(snapshot(),options())
    assert result['baseline']['files']==4 and result['baseline']['eligible_files']==3
    assert result['projection']['upper']=={'files':0,'lines':3}
    assert result['projection']['planning']=={'files':0,'lines':1}
    assert result['projection']['validated_removed_lines']==0
    assert result['candidate_count']==1
    assert result['receipt']['analysis_sha256']==digest({k:v for k,v in result.items() if k!='receipt'})
    assert next(row for row in result['matrices']['files'] if row['path']=='shared/a.py')['memberships']==['app']
    assert result['receipt']['configuration_sha256']==digest(options().model_dump())


def test_function_membership_is_not_inferred_from_file_imports():
    graph=snapshot();function=next(n['id'] for n in graph['nodes'] if n['type']=='function' and n['properties']['path']=='shared/a.py')
    result=analyze(graph,OptimizationOptions(units=[ProductUnit(id='callable',entrypoints=[function])]))
    selected=next(row for row in result['matrices']['functions'] if row['id']==function)
    assert selected['observed_call_units']==['callable']
    assert all(not row['observed_call_units'] for row in result['matrices']['functions'] if row['id']!=function)


def test_unresolved_entrypoints_are_explicit_and_duplicate_ids_rejected():
    result=analyze(snapshot(),OptimizationOptions(units=[ProductUnit(id='missing',entrypoints=['not-here.py'])]))
    assert result['diagnostics']==[{'unit':'missing','status':'unresolved_entrypoints','entrypoints':['not-here.py']}]
    with pytest.raises(HTTPException) as error:
        analyze(snapshot(),OptimizationOptions(units=[ProductUnit(id='same',entrypoints=['app.py'])]*2))
    assert error.value.status_code==422


def test_whole_file_deletions_do_not_double_count_function_spans_or_entrypoints():
    graph=build_graph_from_files(LocalGraphRequest(files=[{'path':p,'content':BODY} for p in ['a.py','b.py','c.py']]))
    result=analyze(graph,OptimizationOptions(units=[ProductUnit(id='a',entrypoints=['a.py']),ProductUnit(id='b',entrypoints=['b.py'])],minimum_function_lines=3))
    assert result['projection']['upper']['files']==1
    assert all('a.py' not in c['copies'] and 'b.py' not in c['copies'] for c in result['candidates'] if c['kind']=='identical_file')
    # Remaining protected copies can be declaration candidates, but full-file spans are not counted twice.
    assert result['projection']['upper']['lines']<=sum(n['properties']['loc'] for n in graph['nodes'] if n['type']=='file')


def test_native_and_heuristic_sources_have_honest_coverage():
    graph=build_graph_from_files(LocalGraphRequest(files=[{'path':'main.cpp','content':'int work(int value) {\n int one=value+1;\n return one;\n}\n'},
        {'path':'sample.java','content':'class Example { int value() { return 1; } }'}]))
    result=analyze(graph)
    assert result['baseline']['files']==2
    assert any('heuristic' in limit for limit in result['limitations'])
    assert all(not f['fingerprint'] for f in result['matrices']['functions'] if f['path'].endswith('.java'))


def test_file_limit_and_candidate_limit_are_explicit(monkeypatch):
    monkeypatch.setattr(settings,'OPTIMIZATION_MAX_FILES',1)
    with pytest.raises(HTTPException) as error:analyze(snapshot())
    assert error.value.status_code==413


def test_csv_escapes_formula_prefixes():
    graph=build_graph_from_files(LocalGraphRequest(files=[{'path':'=formula.py','content':'x=1'}]))
    result=analyze(graph)
    assert "'=formula.py" in csv_matrix(result,'files')


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(review_routes,'store',review_routes.ReviewStore())
    monkeypatch.setattr(settings,'OPTIMIZATION_UNITS',[])
    monkeypatch.setattr(settings,'AI_PROVIDER','disabled')
    client=TestClient(app)
    token=client.post('/api/v1/review/session').json()['token'];headers={'X-CodeTrace-Session':token}
    record=client.post('/api/v1/review/reviews',headers=headers,json={'request_id':'optimization-source','kind':'graph',
        'source':{'files':[{'path':'a.py','content':BODY}]}}).json()
    return client,headers,record


def test_api_session_approval_export_receipt_and_artifact_hashes(api):
    client,headers,record=api;body={'review_id':'optimization-source'}
    assert client.post('/api/v1/workspace/optimization/analyze',json=body).status_code==401
    other={'X-CodeTrace-Session':client.post('/api/v1/review/session').json()['token']}
    assert client.post('/api/v1/workspace/optimization/analyze',headers=other,json=body).status_code==404
    result=client.post('/api/v1/workspace/optimization/analyze',headers=headers,json=body)
    assert result.status_code==200,result.text
    assert result.json()['preview']['table_totals']['files']==1
    assert client.post('/api/v1/workspace/optimization/export',headers=headers,json=body).status_code==409
    approved=client.post('/api/v1/review/reviews/optimization-source/decision',headers=headers,json={
        'action':'approved','note':'Checked synthetic evidence','revision':record['revision'],'result_digest':record['result_digest']})
    assert approved.status_code==200
    exported=client.post('/api/v1/workspace/optimization/export',headers=headers,json=body)
    assert exported.status_code==200,exported.text
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported.json()['archive_base64']))) as archive:
        assert 'report.html' in archive.namelist() and 'reduction-chart.svg' in archive.namelist()
        assert b'Current and projected file quantities' in archive.read('reduction-chart.svg')
        receipt=json.loads(archive.read('receipt.json'))
        for name,expected in receipt['artifacts'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==expected
        assert receipt['review_result_digest']==record['result_digest']


def test_relative_import_and_package_membership_do_not_cross_namespaces():
    graph=build_graph_from_files(LocalGraphRequest(files=[
        {'path':'one/app.py','content':'from . import helper\n'},
        {'path':'one/helper.py','content':'def run(): return 1\n'},
        {'path':'two/helper.py','content':'def run(): return 2\n'}]))
    result=analyze(graph,OptimizationOptions(units=[ProductUnit(id='one',entrypoints=['one/app.py'])]))
    rows={row['path']:row for row in result['matrices']['files']}
    assert rows['one/helper.py']['memberships']==['one']
    assert rows['two/helper.py']['memberships']==[]


def test_automatic_directory_cells_support_more_than_32_source_files():
    graph=build_graph_from_files(LocalGraphRequest(files=[{'path':f'src/file_{i}.py','content':f'value={i}\n'} for i in range(40)]))
    result=analyze(graph)
    assert result['baseline']['files']==40 and len(result['units'])==1
    assert result['units'][0]['kind']=='structural_directory' and not result['diagnostics']
    assert all(row['memberships']==['directory-1'] for row in result['matrices']['files'])


def test_explicit_sple_features_are_retained_without_inventing_feature_constraints():
    result=analyze(snapshot(),OptimizationOptions(units=[ProductUnit(id='a',entrypoints=['app.py'],kind='product_variant',features=['braking'])]))
    assert result['product_line']['feature_units']=={'braking':['a']}
    assert result['product_line']['status']=='configured_labels_only_no_feature_constraints'
    assert len(result['product_line']['engineering_plan'])==6
    assert all(step['gate'] for step in result['product_line']['engineering_plan'])


def test_report_artifacts_have_verifiable_hashes_and_escape_source_titles(tmp_path):
    import importlib.util
    from core.config import PROJECT_ROOT
    spec=importlib.util.spec_from_file_location('product_line_report_test',PROJECT_ROOT/'scripts/product_line_analysis.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=analyze(snapshot(),options())
    module.write_artifacts(result,tmp_path,'<script>untrusted</script>')
    receipt=json.loads((tmp_path/'receipt.json').read_text(encoding='utf-8'))
    for name,expected in receipt['artifacts'].items():assert hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()==expected
    document=(tmp_path/'report.html').read_text(encoding='utf-8')
    assert '&lt;script&gt;untrusted&lt;/script&gt;' in document
    assert '<script>untrusted</script>' not in document
    assert receipt['test_status']=='not_run_by_analysis'


def test_optional_llm_sends_only_bounded_metadata_and_rejects_invented_ids(tmp_path,monkeypatch):
    import httpx,importlib.util
    from core.config import PROJECT_ROOT
    spec=importlib.util.spec_from_file_location('product_line_llm_test',PROJECT_ROOT/'scripts/product_line_analysis.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    env=tmp_path/'provider.env';env.write_text('OPENAI_API_KEY=FAKE_REVIEW_SENTINEL\nOPENAI_MODEL=gpt-5-nano\nOPENAI_BASE_URL=https://review.example/v1\n',encoding='utf-8')
    result=analyze(snapshot(),options());known=result['candidates'][0]['id'];invented=[False]
    def transport(request):
        assert request.headers['Authorization']=='Bearer FAKE_REVIEW_SENTINEL'
        payload=json.loads(request.content)
        assert 'FAKE_REVIEW_SENTINEL' not in str(payload) and payload['store'] is False
        assert 'def work' not in str(payload)
        review={'executive_review':'Review contracts first','recommendations':[{'candidate_ids':['unknown' if invented[0] else known],'assessment':'Advisory only'}]}
        return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(review)}]}]})
    original=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(transport),**kw))
    assert module.llm_review(result,env)['status']=='advisory_only'
    invented[0]=True
    with pytest.raises(ValueError,match='unknown candidate'):
        module.llm_review(result,env)


def test_file_group_chart_counts_each_eligible_file_once():
    from services.product_line_optimizer import file_group_projection
    result=analyze(snapshot(),options())
    groups=file_group_projection(result)
    assert sum(g['current'] for g in groups)==result['baseline']['eligible_files']
    assert sum(g['projected'] for g in groups)==result['baseline']['eligible_files']-result['projection']['planning']['files']
    assert all(0<=g['projected']<=g['current'] for g in groups)
    result['cells']=[{'id':'one','units':['a']},{'id':'two','units':['b']}]
    result['matrices']['files']=[{'path':'shared.py','eligible':True,'memberships':['a','b']},
        {'path':'unknown.py','eligible':True,'memberships':[]},
        {'path':'test_a.py','eligible':False,'memberships':['a']}]
    result['candidates']=[];result['projection']['planning']['files']=0
    assert file_group_projection(result)==[
        {'id':'Shared across cells','units':[],'current':1,'projected':1},
        {'id':'Unmapped','units':[],'current':1,'projected':1}]


def test_classification_api_is_session_owned_and_ai_is_opt_in(api,monkeypatch):
    client,headers,record=api
    monkeypatch.setattr(settings,'AI_PROVIDER','disabled')
    context={'capabilities':[{'id':'math','label':'Calculation'}],
        'features':[{'id':'increment','label':'Increment','capability_id':'math','paths':['a.py']}],
        'products':[{'id':'demo','features':['increment']}]}
    body={'review_id':'optimization-source','product_context':context}
    assert client.post('/api/v1/workspace/optimization/classify-ai',json=body).status_code==401
    other={'X-CodeTrace-Session':client.post('/api/v1/review/session').json()['token']}
    assert client.post('/api/v1/workspace/optimization/classify-ai',headers=other,json=body).status_code==404
    response=client.post('/api/v1/workspace/optimization/analyze',headers=headers,json=body)
    assert response.status_code==200,response.text
    c=response.json()['classification']
    assert c['coverage']['files_with_configured_evidence']==1 and 'ai_review' not in c
    ai=client.post('/api/v1/workspace/optimization/classify-ai',headers=headers,json=body)
    assert ai.status_code==200,ai.text
    assert ai.json()['classification']['ai_review']['status']=='disabled'
    assert ai.json()['receipt']['review_result_digest']==record['result_digest']


def test_ai_citations_survive_preview_and_never_become_configured_mappings(api,monkeypatch):
    from services import classification_ai
    client,headers,_=api
    def proposal(c,*args):
        e=c['evidence'][-1]
        return {'status':'proposals_require_review','proposals':[{'artifact_id':e['artifact_id'],'feature_id':'proposed',
            'rationale':'Tentative','citation_ids':[e['id']]}]}
    monkeypatch.setattr(classification_ai,'propose',proposal)
    response=client.post('/api/v1/workspace/optimization/classify-ai',headers=headers,json={'review_id':'optimization-source'})
    assert response.status_code==200,response.text
    c=response.json()['classification']
    assert c['ai_evidence'] and not c['mappings']


def test_central_capability_only_context_is_used_before_feature_discovery(api,monkeypatch):
    from core.optimization_models import ProductContext
    client,headers,_=api
    monkeypatch.setattr(settings,'OPTIMIZATION_PRODUCT_CONTEXT',ProductContext.model_validate({
        'family':'Configurable customer family','capabilities':[{'id':'customer-capability','label':'Customer capability'}]}))
    result=client.post('/api/v1/workspace/optimization/analyze',headers=headers,json={'review_id':'optimization-source'})
    assert result.status_code==200,result.text
    assert result.json()['classification']['capabilities'][0]['id']=='customer-capability'


def test_in_app_report_is_session_owned_and_available_before_export_approval(api):
    client,headers,record=api;body={'review_id':'optimization-source'}
    assert client.post('/api/v1/workspace/optimization/report',json=body).status_code==401
    other={'X-CodeTrace-Session':client.post('/api/v1/review/session').json()['token']}
    assert client.post('/api/v1/workspace/optimization/report',headers=other,json=body).status_code==404
    response=client.post('/api/v1/workspace/optimization/report',headers=headers,json=body)
    assert response.status_code==200,response.text
    report=response.json()
    assert report['receipt']['review_result_digest']==record['result_digest']
    assert hashlib.sha256(report['html'].encode()).hexdigest()==report['html_sha256']
    assert 'Code similarity coefficient' in report['html'] and '<svg' in report['html']
    assert 'Content-Security-Policy' in report['html'] and "default-src 'none'" in report['html']
    assert 'href="file-unit.csv"' not in report['html']
    assert 'href="about:srcdoc#similarity"' in report['html']
    assert client.post('/api/v1/workspace/optimization/export',headers=headers,json=body).status_code==409


def test_report_preview_enforces_size_bound(api,monkeypatch):
    client,headers,_=api
    monkeypatch.setattr(settings,'OPTIMIZATION_MAX_EXPORT_BYTES',10)
    assert client.post('/api/v1/workspace/optimization/report',headers=headers,json={'review_id':'optimization-source'}).status_code==413


def test_report_and_approved_export_include_model_recommendations_without_changing_projection(api,monkeypatch):
    from services import reduction_advisor
    client,headers,record=api;calls=[]
    def advice(result,*args):
        calls.append(result['projection'].copy())
        return {'status':'advisory_only','model':'controlled-fixture','review':{
            'executive_review':'No savings are established by this synthetic source.',
            'recommendations':[{'title':'Review the module contract','action':'Confirm ownership first.',
                'rationale':'Static evidence is incomplete.','citation_ids':['E1'],'candidate_ids':[],
                'required_checks':['Run regression tests']} ]}}
    monkeypatch.setattr(reduction_advisor,'review_reductions',advice)
    body={'review_id':'optimization-source','include_llm':True}
    preview=client.post('/api/v1/workspace/optimization/report',headers=headers,json=body)
    assert preview.status_code==200 and 'Review the module contract' in preview.json()['html']
    assert len(calls)==1
    assert client.post('/api/v1/workspace/optimization/export',headers=headers,json=body).status_code==409
    assert len(calls)==1
    response=client.post('/api/v1/review/reviews/optimization-source/decision',headers=headers,json={
        'action':'approved','note':'Synthetic approval','revision':record['revision'],'result_digest':record['result_digest']})
    assert response.status_code==200
    exported=client.post('/api/v1/workspace/optimization/export',headers=headers,json=body)
    assert exported.status_code==200 and len(calls)==2
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported.json()['archive_base64']))) as archive:
        result=json.loads(archive.read('analysis.json'))
        assert result['projection']==calls[0]==calls[1]
        assert b'Review the module contract' in archive.read('report.html')
    body['include_llm']=False
    client.post('/api/v1/workspace/optimization/report',headers=headers,json=body).raise_for_status()
    assert len(calls)==2


def test_export_holds_capacity_and_rechecks_session_after_rendering(api,monkeypatch):
    from services import optimization_report
    import threading
    client,headers,record=api
    response=client.post('/api/v1/review/reviews/optimization-source/decision',headers=headers,json={
        'action':'approved','note':'Synthetic approval','revision':record['revision'],'result_digest':record['result_digest']})
    assert response.status_code==200
    monkeypatch.setattr(review_routes.store,'workers',threading.BoundedSemaphore(1))
    original=optimization_report.assessment_documents
    def end_while_rendering(result,source):
        assert not review_routes.store.workers.acquire(blocking=False), 'Rendering escaped the worker bound'
        documents=original(result,source)
        review_routes.store.end(headers['X-CodeTrace-Session'])
        return documents
    monkeypatch.setattr(optimization_report,'assessment_documents',end_while_rendering)
    response=client.post('/api/v1/workspace/optimization/export',headers=headers,json={
        'review_id':'optimization-source','include_llm':False})
    assert response.status_code==401
    assert review_routes.store.workers.acquire(blocking=False)
    review_routes.store.workers.release()


def test_report_rechecks_deadline_after_rendering(api,monkeypatch):
    from services import optimization_report
    from api import optimization_routes
    client,headers,_=api
    clock=[0.0]
    monkeypatch.setattr(optimization_routes.time,'monotonic',lambda:clock[0])
    original=optimization_report.report_html
    def slow_render(*args):
        document=original(*args)
        clock[0]=settings.REQUEST_TIMEOUT_SECONDS+1
        return document
    monkeypatch.setattr(optimization_report,'report_html',slow_render)
    response=client.post('/api/v1/workspace/optimization/report',headers=headers,json={
        'review_id':'optimization-source','include_llm':False})
    assert response.status_code==504
