import json
import pytest
import httpx
from pydantic import ValidationError
from api.graph_routes import LocalGraphRequest, build_graph_from_files
from core.optimization_models import OptimizationOptions, ProductContext, OpenAPIArtifact
from core.config import settings
from services.product_line_optimizer import analyze
from services.product_classification import validate_proposals


def model(prefix='reporting'):
    return ProductContext.model_validate({'family':'Independent example family',
        'capabilities':[{'id':prefix,'label':'Reporting'}],
        'features':[{'id':'export','capability_id':prefix,'label':'Export report','paths':['client/*']}],
        'products':[{'id':'basic','features':['export']}]})


def graph():
    return build_graph_from_files(LocalGraphRequest(files=[
        {'path':'client/export.js','content':'export function exportReport() { return "csv"; }'},
        {'path':'engine/calculate.py','content':'def calculate(value):\n    return value + 1\n'},
        {'path':'scripts/export_report.py','content':'def export_report():\n    return True\n'}]))


def test_independent_language_and_folder_mapping_is_not_deployment_reachability():
    result=analyze(graph(),OptimizationOptions(product_context=model()))
    c=result['classification']
    assert c['coverage']['files_with_configured_evidence']==1
    assert any(m['path']=='client/export.js' and m['feature_id']=='export' for m in c['mappings'])
    assert c['configurations'][0]['status']=='declared_constraints_satisfied'
    assert c['artifact_groups'][0]['feature_ids']==['export']
    assert c['artifact_groups'][0]['file_count']==1
    assert c['lexical_proposals'][0]['path']=='scripts/export_report.py'
    assert all(p['status']=='proposed_lexical' for p in c['lexical_proposals'])


def test_function_mapping_never_claims_sibling_function_membership():
    g=build_graph_from_files(LocalGraphRequest(files=[{'path':'math.py','content':'def first(): return 1\ndef second(): return 2\n'}]))
    node=next(n for n in g['nodes'] if n['type']=='function' and n['label']=='first')
    context=model();context.features[0].paths=[];context.features[0].function_ids=[node['id']]
    c=analyze(g,OptimizationOptions(product_context=context))['classification']
    assert len(c['mappings'])==1 and c['mappings'][0]['artifact_id']==node['id']
    assert c['coverage']['functions_with_configured_evidence']==1


def test_openapi_is_offline_sanitized_contract_evidence_not_handler_proof():
    document={'openapi':'3.0.3','servers':[{'url':'https://private.invalid?key=SECRET_SENTINEL'}],
        'paths':{'/reports':{'post':{'operationId':'exportReport','summary':'Export report','security':[{'secret':'SECRET_SENTINEL'}],
            'requestBody':{'$ref':'https://must-not-fetch.invalid/schema'},'responses':{'200':{'description':'ok'}}}}}}
    artifact=OpenAPIArtifact(id='report-api',document=document)
    context=model();context.features[0].operation_ids=['exportReport']
    result=analyze(graph(),OptimizationOptions(product_context=context,openapi_artifacts=[artifact]))
    op=result['classification']['operations'][0]
    assert op['feature_ids']==['export'] and op['status']=='contract_observed'
    assert 'SECRET_SENTINEL' not in json.dumps(result)
    assert 'must-not-fetch' not in json.dumps(result)
    assert result['assumptions']['openapi_artifacts'][0]['sha256']


def test_ambiguous_operation_names_need_qualified_document_identity():
    artifact=lambda name:OpenAPIArtifact(id=name,document={'swagger':'2.0','paths':{'/x':{'get':{'operationId':'read'}}}})
    context=model();context.features[0].operation_ids=['read']
    c=analyze(graph(),OptimizationOptions(product_context=context,openapi_artifacts=[artifact('a'),artifact('b')]))['classification']
    assert all(not op['feature_ids'] for op in c['operations'])
    assert any('ambiguous' in d for d in c['diagnostics'])


@pytest.mark.parametrize('change',[
    lambda c:c['features'][0].update(capability_id='unknown'),
    lambda c:c['features'][0].update(requires=['unknown']),
    lambda c:c['features'][0].update(kind='alternative'),
    lambda c:c['features'][0].update(excludes=['export']),
])
def test_invalid_feature_models_fail_before_assessment(change):
    c=model().model_dump();change(c)
    with pytest.raises(ValidationError):ProductContext.model_validate(c)


def test_configurations_check_mandatory_requires_excludes_and_alternatives():
    context=ProductContext.model_validate({'capabilities':[{'id':'compute','label':'Compute'}],
        'features':[{'id':'base','capability_id':'compute','label':'Base','kind':'mandatory'},
            {'id':'a','capability_id':'compute','label':'A','kind':'alternative','alternative_group':'engine','requires':['base'],'excludes':['b']},
            {'id':'b','capability_id':'compute','label':'B','kind':'alternative','alternative_group':'engine'}],
        'products':[{'id':'invalid','features':['a','b']},{'id':'valid','features':['base','a']}]})
    c=analyze(graph(),OptimizationOptions(product_context=context))['classification']
    assert len(c['configurations'][0]['errors'])==4
    assert not c['configurations'][1]['errors']
    assert c['feature_similarity'][0]['coefficient']==pytest.approx(1/3)


def test_document_evidence_contributes_only_to_review_proposals():
    context=model();context.features[0].label='Output';context.features[0].paths=[]
    from core.optimization_models import DocumentEvidence
    context.documents=[DocumentEvidence(id='requirements',title='Exports',text='export report',feature_ids=['export'])]
    c=analyze(graph(),OptimizationOptions(product_context=context))['classification']
    assert c['lexical_proposals'] and not c['mappings']
    assert c['documents'][0]['status']=='supplied_document_not_verified'


def test_model_taxonomy_and_mappings_require_known_evidence_and_valid_references():
    c=analyze(graph())['classification'];e=c['evidence'][0]
    response={'capabilities':[{'id':'new','label':'New capability','citation_ids':[e['id']]}],
        'features':[{'id':'new-feature','label':'New feature','capability_id':'new','citation_ids':[e['id']]}],
        'proposals':[{'artifact_id':e['artifact_id'],'feature_id':'new-feature','rationale':'Tentative name-based mapping','citation_ids':[e['id']]}]}
    assert validate_proposals(json.dumps(response),c,[e])['proposals'][0]['status']=='proposed_llm_requires_review'
    response['proposals'][0]['artifact_id']='invented'
    with pytest.raises(ValueError,match='artifact identity'):validate_proposals(json.dumps(response),c,[e])
    response['proposals'][0]['artifact_id']=e['artifact_id'];response['features'][0]['citation_ids']=['E999']
    with pytest.raises(ValueError,match='taxonomy evidence'):validate_proposals(json.dumps(response),c,[e])


class Store:
    def info(self,*args,**kwargs):return {}
    def ai_profile(self,*args,**kwargs):return None


def test_disabled_ai_never_calls_network(monkeypatch):
    from services.classification_ai import propose
    monkeypatch.setattr(settings,'AI_PROVIDER','disabled')
    monkeypatch.setattr(httpx,'Client',lambda **kw:pytest.fail('No network call allowed'))
    assert propose(analyze(graph())['classification'],Store(),'token',float('inf'))['status']=='disabled'


def test_openai_compatible_model_is_configurable_and_untrusted_output_rejected(monkeypatch):
    import time
    from services.classification_ai import propose
    monkeypatch.setattr(settings,'AI_PROVIDER','openai-compatible')
    monkeypatch.setattr(settings,'AI_BASE_URL','http://fixture.invalid/v1')
    monkeypatch.setattr(settings,'AI_MODEL','fixture-model')
    monkeypatch.setattr(settings,'AI_TOKEN_ENV','CLASSIFICATION_TEST_KEY')
    monkeypatch.setenv('CLASSIFICATION_TEST_KEY','FAKE_SENTINEL')
    c=analyze(graph(),OptimizationOptions(product_context=model()))['classification'];bad=[False]
    def handler(request):
        payload=json.loads(request.content)
        assert str(request.url)=='http://fixture.invalid/v1/chat/completions'
        assert payload['model']=='fixture-model'
        assert 'FAKE_SENTINEL' not in str(payload) and 'def calculate' not in str(payload)
        e=c['evidence'][0]
        proposal={'artifact_id':e['artifact_id'],'feature_id':'invented' if bad[0] else 'export','rationale':'Tentative mapping','citation_ids':[e['id']]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'proposals':[proposal]})}}]})
    original=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    assert propose(c,Store(),'token',time.monotonic()+10)['status']=='proposals_require_review'
    bad[0]=True
    assert propose(c,Store(),'token',time.monotonic()+10)['status']=='failed'


def test_model_can_extend_an_existing_capability_without_reinventing_its_id(monkeypatch):
    import time
    from services.classification_ai import propose
    monkeypatch.setattr(settings,'AI_PROVIDER','openai-compatible')
    monkeypatch.setattr(settings,'AI_BASE_URL','http://fixture.invalid/v1')
    context=model();context.features=[];context.products=[]
    c=analyze(graph(),OptimizationOptions(product_context=context))['classification']
    def handler(request):
        evidence=json.loads(json.loads(request.content)['messages'][1]['content'])
        assert evidence['capabilities'][0]['id']=='reporting' and evidence['family']==context.family
        observed=evidence['evidence'][0]
        answer={'features':[{'id':'new-export','label':'Export','capability_id':'reporting','citation_ids':[observed['id']]}],
            'proposals':[{'artifact_id':observed['artifact_id'],'feature_id':'new-export','rationale':'Requires review','citation_ids':[observed['id']]}]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}]})
    original=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    result=propose(c,Store(),'token',time.monotonic()+10)
    assert result['status']=='proposals_require_review'
    assert result['features'][0]['capability_id']=='reporting' and not result['capabilities']
