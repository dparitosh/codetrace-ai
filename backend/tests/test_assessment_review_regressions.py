"""Regression cases from the independent assessment review; no live providers."""
from api.graph_routes import LocalGraphRequest, build_graph_from_files, build_graph_from_directory
from core.optimization_models import OptimizationOptions, ProductUnit
from services.product_line_optimizer import analyze
from services.optimization_report import report_html


def graph(files):
    return build_graph_from_files(LocalGraphRequest(files=[{'path':p,'content':s} for p,s in files.items()]))


def test_lazy_conditional_and_class_imports_resolve_relative_dependencies():
    g=graph({'service/router.py': 'def handler():\n    if True:\n        from .business import view\n    return view()\nclass Config:\n    import json\n',
             'service/business.py':'from . import shared\ndef view(): return 1\n',
             'service/shared.py':'value=1\n'})
    result=analyze(g,OptimizationOptions(units=[ProductUnit(id='service',entrypoints=['service/router.py'])]))
    assert all(row['memberships']==['service'] for row in result['matrices']['files'])
    local=next(edge for edge in g['edges'] if edge['type']=='imports' and edge['properties'].get('name')=='business')
    assert local['properties']['lazy'] and local['properties']['conditional']
    assert local['properties']['import_scope']=='function'
    assert local['properties']['execution']=='static_not_observed'
    assert any(edge['properties'].get('import_scope')=='class' for edge in g['edges'])


def test_file_units_seed_declared_routes_and_main_calls_without_claiming_execution():
    g=graph({'router.py':'from fastapi import APIRouter as Router\nrouter=Router()\ndef helper(): return 1\n@router.get("/items")\ndef items(): return helper()\ndef unused(): return 2\n',
             'worker.py':'def run(): return 1\ndef unused(): return 2\nif __name__ == "__main__":\n    run()\n'})
    r=analyze(g,OptimizationOptions(units=[ProductUnit(id='http',entrypoints=['router.py']),ProductUnit(id='worker',entrypoints=['worker.py'])]))
    rows={(f['path'],f['name']):f for f in r['matrices']['functions']}
    assert rows['router.py','items']['resolved_static_call_units']==['http']
    assert rows['router.py','helper']['resolved_static_call_units']==['http']
    assert rows['worker.py','run']['resolved_static_call_units']==['worker']
    assert not rows['router.py','unused']['resolved_static_call_units']
    assert not rows['worker.py','unused']['resolved_static_call_units']
    assert all(not f['observed_call_units'] for f in rows.values())


def test_arbitrary_get_decorator_is_not_an_api_seed():
    r=analyze(graph({'a.py':'@something.get("/items")\ndef items(): return 1\n'}),
              OptimizationOptions(units=[ProductUnit(id='a',entrypoints=['a.py'])]))
    assert not r['matrices']['functions'][0]['resolved_static_call_units']


def test_nested_class_import_retains_lazy_function_provenance():
    g=graph({'a.py':'def outer():\n    class Inner:\n        import json\n    def nested():\n        import sys\n'})
    imports=[edge['properties'] for edge in g['edges'] if edge['type']=='imports']
    assert {item['lexical_scope'] for item in imports}=={'outer.Inner','outer.nested'}
    assert all(item['lazy'] for item in imports)


def test_cell_trace_includes_rejected_existing_cells_and_exact_coefficients():
    r=analyze(graph({'a.py':'x=1\n','b.py':'x=2\n'}),OptimizationOptions(units=[
        ProductUnit(id='a',entrypoints=['a.py']),ProductUnit(id='b',entrypoints=['b.py'])]))
    step=r['cell_formation']['steps'][1]
    assert step['reason']=='no_existing_cell_passed'
    assert step['considered_cells']==[{'cell':'cell-1','accepted':False,'checks':[{'unit':'a','coefficient':0.0}],
                                      'reason':'pair_below_threshold_or_missing_inventory'}]
    assert r['grouping_evidence']['formation_steps']==r['cell_formation']['steps']
    html=report_html(r,'test')
    assert 'cell-1 rejected: a=0.000' in html and 'depend on unit order' in html


def test_unresolved_edge_categories_keep_import_and_call_denominators_separate():
    r=analyze(graph({'a.py':'import json\nimport external_package\nfrom .missing import thing\ndef work(value):\n    return str(value)\ndef shadow(str):\n    return str(1)\n'}))
    c=r['coverage']
    assert c['imports_total']==3 and c['imports_resolved']==0
    assert c['calls_total']==2 and c['calls_resolved']==0
    assert c['unresolved_by_category']=={'standard_library':1,'external_or_missing_package':1,
        'unresolved_internal':1,'builtin':1,'dynamic_or_local_dispatch':1}


def test_directory_selection_exposes_excluded_types_without_reading_secrets(tmp_path):
    (tmp_path/'a.py').write_text('x=1\n')
    (tmp_path/'install.ps1').write_text('not parsed')
    (tmp_path/'services.json').write_text('{"secret":"must-not-appear"}')
    (tmp_path/'.env.local').write_text('SECRET=must-not-appear')
    r=analyze(build_graph_from_directory(tmp_path,'test'))
    c=r['coverage']['source_selection']
    assert c['unsupported_extension_counts']['.json']==1
    assert c['unsupported_extension_counts']['.ps1']==1
    assert {'.jsx','.ts','.tsx'}<=set(c['configured_extensions'])
    assert 'must-not-appear' not in str(r)
    assert 'Deployment/configuration contracts are not automatically analyzed' in report_html(r,'test')


def test_similarity_index_finds_overlap_outside_previous_200_file_subset():
    from services.optimization_visuals import grouping_evidence
    files=[{'path':f'{i:03}.py','eligible':True,'memberships':[]} for i in range(205)]
    functions=[{'path':f['path'],'eligible':True,'basis':'test','fingerprint':str(i) if i<203 else 'shared'} for i,f in enumerate(files)]
    r={'units':[],'assumptions':{'cell_similarity':.65},'matrices':{'files':files,'functions':functions}}
    e=grouping_evidence(r)
    assert e['code_scope']['search_complete']
    assert e['code_scope']['compared_files']==205
    assert e['code_similarity'][0]['source']=='203.py' and e['code_similarity'][0]['target']=='204.py'
    assert e['code_similarity'][0]['coefficient']==1


def test_similarity_index_budget_explicitly_marks_partial_search():
    from services.optimization_visuals import grouping_evidence
    r={'units':[],'assumptions':{'cell_similarity':.65},'matrices':{
        'files':[{'path':str(i),'eligible':True,'memberships':[]} for i in range(640)],
        'functions':[{'path':str(i),'eligible':True,'basis':'test','fingerprint':'same'} for i in range(640)]}}
    e=grouping_evidence(r)
    assert not e['code_scope']['search_complete']
    assert e['code_scope']['index_pair_events']==200000
    assert e['code_scope']['pairs_checked']==200000
    assert len(e['code_similarity'])==100
