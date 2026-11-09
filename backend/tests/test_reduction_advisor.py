import copy
import json
from api.graph_routes import LocalGraphRequest, build_graph_from_files
from services.product_line_optimizer import analyze
from services import reduction_advisor
from services.optimization_report import report_html


def source():
    return analyze(build_graph_from_files(LocalGraphRequest(files=[{'path':'calculate.py','content':'def calculate(value):\n    return value+1\n'}])))


def test_llm_recommendations_preserve_computed_projection_and_validate_references(monkeypatch):
    result=source();before=copy.deepcopy(result['projection']);observed=result['classification']['evidence'][0]
    response={'executive_review':'No deletion candidates are established.',
        'recommendations':[{'title':'Confirm ownership','action':'Review the calculation boundary.',
            'rationale':'Static names alone do not establish variability.', 'citation_ids':[observed['id']],
            'candidate_ids':[],'required_checks':['Owner review and regression tests']} ]}
    def model(messages,*args):
        assert 'def calculate' not in str(messages)
        return {'model':'fixture-model','text':json.dumps(response)}
    monkeypatch.setattr(reduction_advisor,'model_json',model)
    review=reduction_advisor.review_reductions(result,None,'token',float('inf'))
    assert review['status']=='advisory_only' and result['projection']==before
    result['llm_review']=review
    document=report_html(result,'Example')
    assert 'Confirm ownership' in document and 'fixture-model' in document
    assert 'Projected reductions at a glance' in document
    response['recommendations'][0]['candidate_ids']=['invented-candidate']
    assert reduction_advisor.review_reductions(result,None,'token',float('inf'))['status']=='failed'


def test_unavailable_model_does_not_claim_a_review(monkeypatch):
    monkeypatch.setattr(reduction_advisor,'model_json',lambda *args:{'status':'disabled','reason':'Configure the provider'})
    result=source();result['llm_review']=reduction_advisor.review_reductions(result,None,'token',float('inf'))
    assert 'Configure the provider' in report_html(result,'Example')
    assert result['llm_review']['status']=='disabled'


def test_report_shows_reduction_percentages_and_worked_similarity_examples():
    result=source()
    result['baseline']['physical_lines']=130705
    result['projection']['planning']['lines']=11;result['projection']['upper']['lines']=22
    document=report_html(result,'Example')
    assert '130,694' in document and '0.0084%' in document and '0.0168%' in document
    assert 'J(A,B)' in document and 'Illustration only' in document and '1 ÷ 3 = 0.333' in document
