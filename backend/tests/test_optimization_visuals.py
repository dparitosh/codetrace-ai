from api.graph_routes import LocalGraphRequest, build_graph_from_files
from core.optimization_models import OptimizationOptions, ProductUnit
from services.product_line_optimizer import analyze
from services.optimization_report import report_html


def test_coefficients_are_distinct_and_cell_decisions_expose_their_checks():
    graph=build_graph_from_files(LocalGraphRequest(files=[
        {'path':'a.py','content':'def work(): return 1\n'},
        {'path':'b.py','content':'def work(): return 1\ndef other(): return 2\n'}]))
    result=analyze(graph,OptimizationOptions(cell_similarity=.5,units=[
        ProductUnit(id='all',entrypoints=['a.py','b.py']),ProductUnit(id='one',entrypoints=['b.py'])]))
    evidence=result['grouping_evidence']
    assert evidence['unit_similarity'][0]['coefficient']==.5
    assert evidence['code_similarity'][0]['coefficient']==.5
    assert len(result['cells'])==1
    assert evidence['formation_steps'][1]['checks'][0]['coefficient']==.5
    document=report_html(result,'Example')
    assert 'Before: alphabetical order' in document and 'After: rank-order clustering' in document
    assert 'Code similarity coefficient' in document and '0.500' in document
    assert '<svg' in document and 'Supporting evidence' in document
    assert '<details><summary>Technical coverage' in document


def test_missing_evidence_is_not_reported_as_zero_similarity():
    graph=build_graph_from_files(LocalGraphRequest(files=[{'path':'a.py','content':'value=1\n'}]))
    result=analyze(graph,OptimizationOptions(units=[ProductUnit(id='missing-a',entrypoints=['x.py']),ProductUnit(id='missing-b',entrypoints=['y.py'])]))
    assert result['grouping_evidence']['unit_similarity'][0]['coefficient'] is None
    assert result['grouping_evidence']['code_scope']['compared_files']==0
    assert 'N/A' in report_html(result,'Example')


def test_code_overlap_scope_is_bounded_without_inventing_uncompared_scores():
    from services.optimization_visuals import grouping_evidence
    count=210
    result={'units':[],'cells':[],'assumptions':{'cell_similarity':.65},'roc':{'columns':[]},'candidates':[],
        'matrices':{'files':[{'path':str(i),'eligible':True,'memberships':[]} for i in range(count)],
            'functions':[{'path':str(i),'eligible':True,'basis':'test','fingerprint':'same'} for i in range(count)]}}
    evidence=grouping_evidence(result)
    assert evidence['code_scope']['compared_files']==200
    assert evidence['code_scope']['files_with_fingerprints']==210
    assert evidence['code_scope']['truncated']
    assert len(evidence['code_similarity'])==100
