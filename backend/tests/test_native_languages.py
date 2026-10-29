"""C-family syntax extraction and its graph/assessment/agent contracts."""
import pytest
from api.graph_routes import LocalGraphRequest, build_graph_from_files, build_graph_from_directory
from graph.traceability import materialize
from services.agent_workspace import GraphAgent
from services.ai_connection import AIConnection, OllamaREST
from core.config import settings


def analyze(files):
    return build_graph_from_files(LocalGraphRequest(files=[{'path': path, 'content': source} for path, source in files]))


def named(graph, name, kind=None):
    return [node for node in graph['nodes'] if node['label'] == name and (kind is None or node['type'] == kind)]


def linked(graph, source, target, relation):
    return any(edge['source'] == source and edge['target'] == target and edge['type'] == relation for edge in graph['edges'])


def test_c_functions_prototypes_fields_and_cross_file_calls():
    graph = analyze([
        ('include/math.h', 'int sum(int a, int b);\n'),
        ('src/math.c', '#include "../include/math.h"\nstruct Item { int value; };\nint sum(int a, int b);\nint sum(int a, int b) { return a+b; }'),
        ('src/main.c', '#include "../include/math.h"\nint main(void) { return sum(1,2); }'),
    ])
    summed = next(n for n in named(graph, 'sum', 'function') if n['properties']['path'] == 'src/math.c')
    assert summed['properties']['has_body'] and len([n for n in named(graph, 'sum', 'function') if n['properties']['path'] == 'src/math.c']) == 1
    assert linked(graph, named(graph, 'main', 'function')[0]['id'], summed['id'], 'calls')
    assert named(graph, 'value', 'variable')
    assert linked(graph, 'module:src/main.c', 'module:include/math.h', 'imports')
    assert all(n['properties']['parse_status'] == 'parsed' for n in graph['nodes'] if n['type'] == 'file')


def test_cpp_namespaces_methods_inheritance_and_out_of_class_definitions():
    graph = analyze([
        ('app.hpp', 'namespace Demo { class Base {}; class App: public Base { public: App() {} int Run(int x); int helper(int x) { return x; } }; }'),
        ('app.cxx', '#include "app.hpp"\nnamespace Demo { int App::Run(int x) { return helper(x); } }'),
    ])
    app = named(graph, 'App', 'class')[0]
    base = named(graph, 'Base', 'class')[0]
    run = next(n for n in named(graph, 'Run', 'function') if n['properties']['has_body'])
    helper = named(graph, 'helper', 'function')[0]
    assert linked(graph, app['id'], base['id'], 'inherits_from')
    assert linked(graph, app['id'], run['id'], 'defines')
    assert linked(graph, run['id'], helper['id'], 'calls')
    assert named(graph, 'Demo', 'package')
    assert len({n['id'] for n in graph['nodes']}) == len(graph['nodes'])


def test_csharp_file_namespace_interface_constructor_property_and_method_calls():
    graph = analyze([('App.cs', '''using System;
namespace Demo;
public interface IBase { int Run(int x); }
public class App : IBase {
    private int value;
    public int Value { get; set; }
    public App() { }
    public int Run(int x) => this.Helper(x);
    private int Helper(int x) { return x; }
}''')])
    run = next(n for n in named(graph, 'Run', 'function') if n['properties']['has_body'])
    helper = named(graph, 'Helper', 'function')[0]
    assert linked(graph, run['id'], helper['id'], 'calls')
    assert linked(graph, named(graph, 'App', 'class')[0]['id'], named(graph, 'IBase', 'class')[0]['id'], 'inherits_from')
    assert named(graph, 'App', 'function') and named(graph, 'Demo', 'package')
    assert named(graph, 'Value', 'variable')[0]['properties']['classification'] == 'property'
    functions = next(m for m in graph['source_assessments']['quality']['metrics'] if m['name'] == 'Functions')
    assert functions['value'] == 4
    assert next(m for m in graph['source_assessments']['quality']['metrics'] if m['name'] == 'Documentation coverage')['value'] is None


def test_ambiguous_overloads_unknown_receivers_and_shadowed_names_remain_unresolved():
    graph = analyze([('app.cpp', '''int calc(int x) { return x; }
float calc(float x) { return x; }
int invoke(int calc) { return calc(1); }
int start() { return calc(1); }
class App { public: int Run() { return other.Run(); } };''')])
    calls = [e for e in graph['edges'] if e['type'] == 'calls']
    assert len(calls) == 3 and all(not e['properties']['resolved'] for e in calls)
    assert all(next(n for n in graph['nodes'] if n['id'] == e['target'])['type'] == 'external_symbol' for e in calls)


def test_comments_and_literals_do_not_create_fake_symbols_or_calls():
    graph = analyze([('app.cs', '''// public class Fake { int Bad() { Danger(); } }
class Real { string text = "class Fake2 { void Bad2() {} }";
int Run() { return 1; } }''')])
    assert named(graph, 'Real', 'class') and named(graph, 'Run', 'function')
    assert not named(graph, 'Fake') and not named(graph, 'Fake2') and not named(graph, 'Bad')
    assert not [e for e in graph['edges'] if e['type'] == 'calls']


@pytest.mark.parametrize('path,source', [('broken.c', 'int run( { return 1;'),
    ('broken.cpp', 'class App { public: int Run( { }'), ('Broken.cs', 'class App { public int Run( { }')])
def test_recovered_syntax_does_not_receive_an_overall_quality_grade(path, source):
    graph = analyze([(path, source)])
    file = next(n for n in graph['nodes'] if n['type'] == 'file')
    assert file['properties']['parse_status'] == 'partial'
    assert graph['source_assessments']['quality']['overall_score'] is None


def test_native_facts_reach_materialized_graph_and_offline_agent(monkeypatch):
    graph = analyze([('app.c', 'int helper(void) { return 1; }\nint run(void) { return helper(); }')])
    manifest = {'repository': {'uri': 'urn:test:native', 'label': 'Native fixture'}, 'resources': [], 'links': []}
    combined = materialize(graph, manifest, graph['metadata']['source_digest'])
    run = named(combined, 'run', 'function')[0]
    assert run['properties']['extraction'] == 'tree_sitter'
    monkeypatch.setattr(settings, 'AI_BASE_URL', 'http://127.0.0.1:1434')
    monkeypatch.setattr(settings, 'AI_ALLOWED_BASE_URLS', [])
    rest = OllamaREST(AIConnection(base_url=settings.AI_BASE_URL, enabled=False))
    answer = GraphAgent(combined, rest).run('Explain calls', run['id'])
    assert answer['mode'] == 'evidence' and answer['relations']
    assert any(e['predicate'].endswith('calls') for e in answer['relations'])


def test_managed_native_folder_uses_relative_paths_and_excludes_build_artifacts(tmp_path):
    (tmp_path / 'Program.cs').write_text('class App { int Run() { return 1; } }')
    (tmp_path / 'obj').mkdir(); (tmp_path / 'obj/Generated.cs').write_text('class Ignore {}')
    graph = build_graph_from_directory(tmp_path, 'managed')
    assert named(graph, 'Run', 'function') and not named(graph, 'Ignore', 'class')
    assert next(n for n in graph['nodes'] if n['type'] == 'file')['properties']['path'] == 'Program.cs'


def test_const_and_reference_overloads_retain_distinct_identities():
    graph = analyze([('app.cpp', 'class App { public: int Get() { return 1; } int Get() const { return 2; } };\nint f(int& x) { return x; } int f(int x) { return x; }')])
    assert len(named(graph, 'Get', 'function')) == 2
    assert len(named(graph, 'f', 'function')) == 2


def test_missing_grammar_reports_heuristic_fallback(monkeypatch):
    from codegraph_core import native_scanner
    def unavailable(_):
        raise ImportError('fixture unavailable')
    monkeypatch.setattr(native_scanner, 'grammar', unavailable)
    graph = analyze([('app.cpp', 'class App { int Run() { return 1; } };')])
    file = next(n for n in graph['nodes'] if n['type'] == 'file')
    assert file['properties']['parse_status'] == 'heuristic'
    assert 'unavailable' in file['properties']['parser_warning']
    assert not named(graph, 'Run', 'function')


def test_include_outside_selection_does_not_bind_to_same_named_root_header():
    graph = analyze([('app.c', '#include "../../secret.h"\nint run(void) { return 1; }'), ('secret.h', 'int secret(void);')])
    imports = [e for e in graph['edges'] if e['type'] == 'imports']
    assert imports and all(not e['properties']['resolved'] for e in imports)


def test_static_internal_function_and_deferred_lambda_calls_are_not_global_links():
    graph = analyze([('private.c', 'static int hidden(void) { return 1; }'),
                     ('app.c', 'int run(void) { return hidden(); }'),
                     ('lambda.cpp', 'int helper() { return 1; } int start() { auto later = []() { return helper(); }; return 0; }')])
    call = next(e for e in graph['edges'] if e['type'] == 'calls')
    assert not call['properties']['resolved']
    assert len([e for e in graph['edges'] if e['type'] == 'calls']) == 1


def test_native_managed_snapshot_includes_methods_in_shared_graph(tmp_path, monkeypatch):
    from core.connection_models import ManagedRepository
    from services.workspace_service import build_managed_snapshot
    (tmp_path / 'App.cs').write_text('namespace Demo { class App { int Helper() { return 1; } int Run() { return Helper(); } } }')
    monkeypatch.setattr(settings, 'MANAGED_REPOSITORIES', [ManagedRepository(id='native', label='Native fixture', path=str(tmp_path))])
    monkeypatch.setattr(settings, 'OSLC_PROVIDERS', [])
    monkeypatch.setattr(settings, 'CI_PROVIDERS', [])
    graph = build_managed_snapshot('native', include_lifecycle=False)
    methods = [n for n in graph['nodes'] if n['type'] == 'method']
    assert {n['label'] for n in methods} == {'Run', 'Helper'}
    assert any(e['type'].endswith('calls') for e in graph['edges'])
    assert graph['source_assessments']['quality']['overall_score'] is not None


def test_local_function_calls_preserve_scope_and_explicit_this():
    graph = analyze([('App.cs', '''class App {
int Helper() { return 1; }
int Run() { int Helper() { return this.Helper(); } return Helper(); }
int Other(int Helper) { return this.Helper(); }
}''')])
    helpers = {node['properties']['qualified_name']: node for node in named(graph, 'Helper', 'function')}
    assert linked(graph, named(graph, 'Run', 'function')[0]['id'], helpers['App.Run.Helper']['id'], 'calls')
    assert linked(graph, helpers['App.Run.Helper']['id'], helpers['App.Helper']['id'], 'calls')
    assert linked(graph, named(graph, 'Other', 'function')[0]['id'], helpers['App.Helper']['id'], 'calls')
    combined = materialize(graph, {'repository': {'uri': 'urn:test:scope', 'label': 'Scope'}, 'resources': [], 'links': []}, graph['metadata']['source_digest'])
    local = next(n for n in combined['nodes'] if n['properties'].get('qualified_name') == 'App.Run.Helper')
    assert local['type'] == 'function'
    assert named(combined, 'Run', 'method')


@pytest.mark.parametrize('path,source,name', [
    ('App.cs', 'class App { int Read<T>() { return 1; } int Read<T,U>() { return 2; } }', 'Read'),
    ('app.cpp', 'int read(int (&a)[2]) { return 1; } int read(int (&a)[3]) { return 2; }', 'read'),
    ('app.cpp', 'typedef int unsignedint; int read(unsigned int a) { return 1; } int read(unsignedint a) { return 2; }', 'read'),
])
def test_complete_native_signature_retains_overloads_and_quality_count(path, source, name):
    graph = analyze([(path, source)])
    overloads = named(graph, name, 'function')
    assert len(overloads) == len({n['id'] for n in overloads}) == 2
    assert next(m for m in graph['source_assessments']['quality']['metrics'] if m['name'] == 'Functions')['value'] == 2


def test_native_declarator_shape_ignores_parameter_names_and_whitespace():
    graph = analyze([('app.cpp', 'int read(int (&first)[2]); int read(int ( & second )[2]) { return 1; }')])
    assert len(named(graph, 'read', 'function')) == 1
    assert named(graph, 'read', 'function')[0]['properties']['has_body']


def test_all_comma_declarators_preserve_functions_variables_and_initializer_calls():
    graph = analyze([('app.c', 'int first(void), second(void); int run(void) { int a = first(), b = second(); return a+b; }')])
    assert {node['label'] for node in graph['nodes'] if node['type'] == 'function'} == {'first', 'second', 'run'}
    assert {node['label'] for node in graph['nodes'] if node['type'] == 'variable'} == {'a', 'b'}
    calls = [e for e in graph['edges'] if e['type'] == 'calls']
    assert len(calls) == 2 and all(e['properties']['resolved'] for e in calls)


def test_cpp_name_hiding_stops_before_arity_filter_but_explicit_global_still_works():
    graph = analyze([('app.cpp', 'int read() { return 1; } namespace N { int read(int x) { return x; } int run() { return read(); } int explicit_run() { return ::read(); } }')])
    calls = {next(n for n in graph['nodes'] if n['id'] == edge['source'])['label']: edge for edge in graph['edges'] if edge['type'] == 'calls'}
    assert not calls['run']['properties']['resolved']
    assert calls['explicit_run']['properties']['resolved']
    assert next(n for n in graph['nodes'] if n['id'] == calls['explicit_run']['target'])['properties']['qualified_name'] == 'read'
