"""CT-GT-CELL-1: custom rank-order incidence clustering and conservative SPLE projections.

No source execution, rewriting, generic community clustering, or mathematical
claim of semantic equivalence. All projections are unvalidated upper envelopes.
"""
import csv
import hashlib
import io
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import PurePosixPath
from fastapi import HTTPException
from core.config import settings
from core.optimization_models import OptimizationOptions, ProductUnit

VERSION = 'CT-GT-CELL-1'
CALLABLES = {'function', 'method'}

def engineering_plan():
    """Review gates, not inferred features or an executable configuration model."""
    return [
        {'stage':'Domain engineering', 'action':'Confirm the product family, business capabilities and feature owners; distinguish products from deployment services.',
         'gate':'Owner-approved feature catalogue mapped to source evidence.'},
        {'stage':'Core assets', 'action':'Review platform-core and family-shared candidates for stable contracts; retain cell-owned behavior with its domain.',
         'gate':'Consumer contract, authorization, transaction and dependency compatibility checks.'},
        {'stage':'Variability', 'action':'Specify mandatory, optional and alternative features, requires/excludes constraints and binding time; choose configuration, strategy or adapter only where justified.',
         'gate':'Explicit feature constraints and reviewed variation-point contracts; dependency overlap alone is insufficient.'},
        {'stage':'Application engineering', 'action':'Document how an approved product configuration selects, versions and assembles core assets and domain extensions.',
         'gate':'Reproducible build/deployment recipe and traceability from features to modules, interfaces and tests.'},
        {'stage':'Configuration validation', 'action':'Run common-core tests and feature-specific contracts on representative valid configurations and reject invalid combinations.',
         'gate':'Passing regression, security, failure and concurrency checks for affected configurations.'},
        {'stage':'Economic validation', 'action':'Pilot one extraction; measure maintenance effort and net source change after adding abstractions, wrappers, configuration and tests.',
         'gate':'Measured before/after results and rollback evidence; candidate counts are not realized savings.'},
    ]

def file_group_projection(result):
    """Disjoint GT cell groups; shared/unmapped files are counted once."""
    cell_for={unit:cell['id'] for cell in result['cells'] for unit in cell['units']}
    groups={cell['id']:{'id':cell['id'],'units':cell['units'],'current':0,'projected':0} for cell in result['cells']}
    for name in ('Shared across cells','Unmapped'):
        groups[name]={'id':name,'units':[],'current':0,'projected':0}
    removable=sorted({path for c in result['candidates'] if c['kind']=='identical_file' for path in c['copies']})
    selected=set(removable[:result['projection']['planning']['files']])
    for row in result['matrices']['files']:
        if not row['eligible']: continue
        cells={cell_for[unit] for unit in row['memberships'] if unit in cell_for}
        name=next(iter(cells)) if len(cells)==1 else 'Shared across cells' if cells else 'Unmapped'
        groups[name]['current']+=1
        groups[name]['projected']+=int(row['path'] not in selected)
    return [group for group in groups.values() if group['current']]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def walk(adjacency, roots):
    seen = set(roots); queue = deque(sorted(seen))
    while queue:
        for target in sorted(adjacency.get(queue.popleft(), ())):
            if target not in seen:
                seen.add(target); queue.append(target)
    return seen

def rank_order_clustering(memberships, units, maximum=20):
    """Alternating binary row/column ranks; deterministic ties, fixed pass bound."""
    rows, columns = sorted(memberships), sorted(units)
    seen = set()
    for iteration in range(maximum):
        state = (tuple(rows), tuple(columns))
        if state in seen:
            return rows, columns, iteration, False
        seen.add(state)
        next_rows = sorted(rows, key=lambda row: (-sum(1 << (len(columns)-i-1) for i, col in enumerate(columns) if col in memberships[row]), row))
        ranks = {col: sum(1 << (len(next_rows)-i-1) for i, row in enumerate(next_rows) if col in memberships[row]) for col in columns}
        next_columns = sorted(columns, key=lambda col: (-ranks[col], col))
        if (next_rows, next_columns) == (rows, columns):
            return rows, columns, iteration+1, True
        rows, columns = next_rows, next_columns
    return rows, columns, maximum, False

def is_test(path):
    p = PurePosixPath(path)
    return bool(set(p.parts) & {'tests','test','__tests__','fixtures'}) or p.name.startswith('test_') or '.test.' in p.name or '.spec.' in p.name

def analyze(graph, options=None, result_digest=None):
    options = options or OptimizationOptions()
    config = options.model_dump()
    config['openapi_artifacts']=[{'id':a.id,'sha256':digest(a.document)} for a in options.openapi_artifacts]
    nodes = {n['id']: n for n in graph['nodes']}
    files = {n['properties']['path']: n for n in graph['nodes'] if n['type']=='file' and n['properties'].get('path')}
    if len(files) > settings.OPTIMIZATION_MAX_FILES:
        raise HTTPException(413, 'Optimization file limit exceeded; select a smaller source or explicitly increase OPTIMIZATION_MAX_FILES')
    paths = set(files)
    eligible = {p for p in paths if options.include_tests or not is_test(p)}
    aliases = defaultdict(set)
    for path in paths:
        aliases[path].add(path)
        if path.endswith('.py'):
            module = path[:-3].replace('/', '.')
            aliases[module].add(path)
            if module.endswith('.__init__'): aliases[module[:-9]].add(path)
    node_path = {key:n['properties'].get('path') for key,n in nodes.items()}
    for key,n in nodes.items():
        code_id = n['properties'].get('code_id', key)
        if not node_path[key] and code_id.startswith('module:'):
            name = code_id.split('module:',1)[1].replace('/', '.')
            matches = aliases.get(name, set())
            if len(matches)==1: node_path[key]=next(iter(matches))
    dependency, call_graph = defaultdict(set), defaultdict(set)
    unresolved=[]; calls=[]
    for edge in graph['edges']:
        # Only scanner-owned predicates, never a foreign lifecycle URI with the same local name.
        kind = edge['type']
        if kind.startswith('urn:codetrace:vocab:'): kind=kind.rsplit(':',1)[-1]
        if kind not in {'imports','calls'}: continue
        source, target = edge['source'],edge['target']
        source_path, target_path = node_path.get(source), node_path.get(target)
        resolved_paths={target_path} if target_path in paths else set()
        properties=edge.get('properties',{})
        if kind=='imports' and source_path in paths:
            name=str(properties.get('name',''))
            level=properties.get('relative_level',0)
            if level:
                parent=PurePosixPath(source_path).parent.parts
                if level<=len(parent): name='.'.join((*parent[:len(parent)-level+1],name)).strip('.')
                else: name=''
            matches=aliases.get(name,set())
            if len(matches)==1: resolved_paths.update(matches)
            if not matches or all(p.endswith('/__init__.py') for p in matches):
                for imported in properties.get('imported_names',[]):
                    children=aliases.get(name+'.'+imported,set())
                    if len(children)==1: resolved_paths.update(children)
        if source_path in paths:
            dependency[source_path].update(p for p in resolved_paths if p!=source_path)
        if kind=='calls':
            resolved = nodes.get(target,{}).get('type') in CALLABLES
            if resolved: call_graph[source].add(target)
            calls.append({'source':source,'target':target,'resolved':resolved,'basis':edge.get('properties',{}).get('resolution','scanner_call_edge')})
        if source_path in paths and not resolved_paths:
            unresolved.append({'source':source_path,'target':target,'kind':kind})
    units=options.units
    if not units:
        groups=defaultdict(list)
        for path in sorted(paths): groups[path.split('/')[0] if '/' in path else '(root)'].append(path)
        if len(groups)>32: raise HTTPException(422,'More than 32 directory groups; configure explicit product/deployment units')
        units=[ProductUnit(id='directory-'+str(i+1),entrypoints=[directory+'/**' if directory!='(root)' else '(root)'],kind='structural_directory') for i,directory in enumerate(groups)]
    if len({u.id for u in units})!=len(units): raise HTTPException(422,'Optimization unit IDs must be unique')
    coverage={}; callable_coverage={}; diagnostics=[]; protected_paths={p for p in paths if PurePosixPath(p).name=='__init__.py'}
    for unit in units:
        roots=set(); function_roots=set(); missing=[]
        for value in unit.entrypoints:
            if unit.kind=='structural_directory' and (value.endswith('/**') or value=='(root)'):
                selected={p for p in paths if (p.startswith(value[:-2]) if value.endswith('/**') else '/' not in p)}
                roots.update(selected)
                if not selected: missing.append(value)
                continue
            if value in nodes and nodes[value]['type'] in CALLABLES:
                function_roots.add(value); roots.add(node_path[value])
            elif value in paths: roots.add(value)
            else: missing.append(value)
        if missing: diagnostics.append({'unit':unit.id,'status':'unresolved_entrypoints','entrypoints':missing})
        if unit.kind!='structural_directory': protected_paths.update(roots)
        coverage[unit.id]=walk(dependency,roots) & paths
        callable_coverage[unit.id]=walk(call_graph,function_roots)
    memberships={path:{u for u,covered in coverage.items() if path in covered} for path in sorted(paths)}
    row_order,col_order,passes,converged=rank_order_clustering(memberships,coverage)
    # Complete-link cell assignment: every pair must meet the overlap threshold.
    def overlap(a,b):
        x,y=coverage[a]&eligible,coverage[b]&eligible
        return len(x&y)/len(x|y) if x|y else 0
    cells=[]
    for unit in col_order:
        match=next((cell for cell in cells if all(overlap(unit,other)>=options.cell_similarity for other in cell)),None)
        if match is None: cells.append([unit])
        else: match.append(unit)
    cell_for={unit:i for i,cell in enumerate(cells) for unit in cell}
    matrix=[{'path':p,'node_id':files[p]['id'],'lines':int(files[p]['properties'].get('loc',0)),
             'file_text_sha256':files[p]['properties'].get('file_text_sha256'),
             'input_sha256':graph.get('metadata',{}).get('source_file_digests',{}).get(p),
             'parse_status':files[p]['properties'].get('parse_status'),'eligible':p in eligible,'memberships':[u for u in col_order if u in memberships[p]]} for p in row_order]
    functions=[]
    for key,n in sorted(nodes.items()):
        path=node_path.get(key)
        if n['type'] not in CALLABLES or path not in paths: continue
        functions.append({'id':key,'name':n['label'],'path':path,'start':n['properties'].get('start'),
            'end':n['properties'].get('end'),'lines':n['properties'].get('declaration_lines'),
            'fingerprint':n['properties'].get('implementation_sha256'),'basis':n['properties'].get('fingerprint_basis'),
            'file_derived_units':sorted(memberships[path]),'observed_call_units':sorted(u for u,ids in callable_coverage.items() if key in ids),
            'eligible':path in eligible and nodes.get(n['properties'].get('owner'),{}).get('type') not in CALLABLES})
    file_groups=defaultdict(list)
    for path in sorted(eligible):
        fp=files[path]['properties'].get('file_text_sha256')
        if fp and files[path]['properties'].get('nonempty',True): file_groups[fp].append(path)
    removed_files=set(); candidates=[]; removed_spans=defaultdict(list)
    for fp,group in sorted(file_groups.items()):
        if len(group)<2: continue
        group.sort(key=lambda p:(p not in protected_paths,p))
        copies=[p for p in group[1:] if p not in protected_paths]
        if not copies: continue
        removed_files.update(copies)
        lines=sum(int(files[p]['properties'].get('loc',0)) for p in copies)
        candidates.append({'id':'file-'+fp[:16],'kind':'identical_file','retained':group[0],'copies':copies,
            'gross_lines':lines,'net_upper_lines':lines,'files_upper':len(copies),
            'evidence':'Full-file text digest (Python UTF-8 BOM normalized); raw input digests retained separately. Module paths, deployment and contracts require review.'})
    fingerprints=defaultdict(list)
    for f in functions:
        if f['eligible'] and f['path'] not in removed_files and f['fingerprint'] and (f['lines'] or 0)>=options.minimum_function_lines:
            fingerprints[(PurePosixPath(f['path']).suffix,f['basis'],f['fingerprint'])].append(f)
    for (_,basis,fp),group in sorted(fingerprints.items()):
        if len(group)<2: continue
        group.sort(key=lambda f:(f['path'],f['start'] or 0,f['id']))
        copies=group[1:]; gross=0; net=0; accepted=[]
        for f in copies:
            start,end=f['start'],f['end']
            if not start or not end or any(not(end<a or start>b) for a,b in removed_spans[f['path']]): continue
            removed_spans[f['path']].append((start,end));gross+=f['lines'];net+=max(0,f['lines']-options.wrapper_lines);accepted.append(f)
        if accepted:
            candidates.append({'id':'operation-'+fp[:16],'kind':'duplicate_declaration','retained':group[0],
                'copies':accepted,'gross_lines':gross,'net_upper_lines':net,'files_upper':0,
                'evidence':basis+'; signature/global bindings, authorization and transactions are not proven equivalent.'})
    candidates.sort(key=lambda c:(-c['net_upper_lines'],c['id']))
    # Truncation is explicit and projections cover only retained candidates.
    total_candidates=len(candidates);candidates=candidates[:settings.OPTIMIZATION_MAX_CANDIDATES]
    upper_lines=sum(c['net_upper_lines'] for c in candidates);upper_files=sum(c['files_upper'] for c in candidates)
    baseline_lines=sum(int(files[p]['properties'].get('loc',0)) for p in eligible)
    recommendations=[]
    for path in row_order:
        units_for=memberships[path]
        if path not in eligible or not units_for: continue
        cross_cells=len({cell_for[u] for u in units_for})
        kind='platform_core_candidate' if len(units_for)==len(units) and len(units)>1 else 'family_shared_candidate' if len(units_for)>1 else 'cell_owned_candidate'
        recommendations.append({'path':path,'kind':kind,'units':sorted(units_for),'cross_cells':cross_cells,
            'advice': 'Review stable common behavior for a platform core; retain domain ownership and transport adapters.' if kind=='platform_core_candidate' else
                     'Separate invariant behavior from explicit variation points; preserve authorization and transaction boundaries.' if kind=='family_shared_candidate' else
                     'Keep variant-specific behavior in its owning cell; do not force it into a global utility.'})
    feature_units=defaultdict(list)
    for unit in units:
        for feature in sorted(set(unit.features)): feature_units[feature].append(unit.id)
    product_line={'status':'configured_labels_only_no_feature_constraints' if feature_units else 'feature_model_not_supplied',
        'engineering_plan':engineering_plan(),
        'feature_units':dict(sorted(feature_units.items())),
        'unmapped_units':[unit.id for unit in units if not unit.features],
        'product_variant_units':[unit.id for unit in units if unit.kind=='product_variant'],
        'required_review':['Domain analysis and feature ownership','Mandatory/optional/alternative feature constraints',
            'Cross-feature requires/excludes constraints','Representative configuration regression matrix',
            'Stable platform API versus domain-owned variation points']}
    result={'product_line':product_line,'algorithm':VERSION,'assumptions':config,'units':[u.model_dump() for u in units],
        'baseline':{'files':len(files),'eligible_files':len(eligible),'excluded_files':len(files)-len(eligible),'physical_lines':baseline_lines,'functions':len(functions)},
        'projection':{'status':'unimplemented_projection','validated_removed_files':0,'validated_removed_lines':0,
            'low':{'files':0,'lines':0},'planning':{'files':int(upper_files*options.adoption_rate),'lines':int(upper_lines*options.adoption_rate)},
            'upper':{'files':upper_files,'lines':upper_lines},'basis':'Eligible duplicate candidates only; subtract wrapper allowance, then multiply by stated adoption rate. Not measured savings.'},
        'matrices':{'files':matrix,'functions':functions,'calls':calls},
        'cells':[{'id':'cell-'+str(i+1),'units':cell} for i,cell in enumerate(cells)],
        'roc':{'passes':passes,'converged':converged,'columns':col_order,'rows':row_order},
        'candidates':candidates,'candidate_count':total_candidates,'candidates_truncated':total_candidates>len(candidates),
        'recommendations':recommendations,'diagnostics':diagnostics,
        'coverage':{'unresolved_dependency_count':len(unresolved),'unresolved_dependencies':unresolved[:200],
            'unresolved_preview_truncated':len(unresolved)>200,'fingerprinted_functions':sum(bool(f['fingerprint']) for f in functions),
            'calls_resolved':sum(c['resolved'] for c in calls),'calls_total':len(calls)},
        'limitations':['File-derived membership is not observed function execution; actual call membership requires explicit callable entrypoints.',
            'Directory units are structural proxies, not discovered deployment services or business features.',
            'Unsupported/heuristic languages can contribute file incidence and exact-file evidence; declaration projections require parser fingerprints.',
            'ROC cells and SPLE recommendations suggest ownership/commonality, not semantic equivalence or valid feature configurations.',
            'No source refactor, performance gain, test pass, security equivalence or actual deletion is established by this projection.']}
    from services.product_classification import classify
    result['classification']=classify(result,options.product_context,options.openapi_artifacts)
    result['file_groups']=file_group_projection(result)
    from services.optimization_visuals import grouping_evidence
    result['grouping_evidence']=grouping_evidence(result)
    result['receipt']={'schema_version':1,'algorithm':VERSION,'generated_at':datetime.now(timezone.utc).isoformat(),
        'snapshot_id':graph.get('metadata',{}).get('snapshot_id'),'source_digest':graph.get('metadata',{}).get('source_digest'),
        'source_revision':graph.get('metadata',{}).get('revision'),'review_result_digest':result_digest,
        'graph_sha256':digest(graph),'configuration_sha256':digest(config),'analysis_sha256':digest(result),
        'test_status':'not_run_by_analysis','source_modified':False}
    return result

def csv_matrix(result, kind):
    stream=io.StringIO(newline='');columns=[u['id'] for u in result['units']]
    rows=result['matrices'][kind]
    fields=['path','node_id','lines','eligible','file_text_sha256','input_sha256','parse_status']+columns if kind=='files' else ['id','name','path','start','end','lines','basis','observed_call_units']+columns
    writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader()
    def safe(value):
        value=str(value) if value is not None else ''
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
    for row in rows:
        membership=row.get('memberships',row.get('file_derived_units',[]))
        writer.writerow({**{k:safe(json.dumps(v) if isinstance(v,(dict,list)) else v) for k,v in row.items()},**{col:int(col in membership) for col in columns}})
    return stream.getvalue()
