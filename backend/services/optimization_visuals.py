"""Bounded, evidence-labelled coefficients and grouping views for business reports."""
from collections import defaultdict
from itertools import combinations


def grouping_evidence(result):
    files=[row for row in result['matrices']['files'] if row['eligible']]
    footprints={u['id']:{f['path'] for f in files if u['id'] in f['memberships']} for u in result['units']}
    unit_pairs=[]
    for a,b in combinations(footprints,2):
        x,y=footprints[a],footprints[b];union=x|y
        unit_pairs.append({'source':a,'target':b,'coefficient':len(x&y)/len(union) if union else None,
            'shared_files':len(x&y),'distinct_files':len(union),'basis':'dependency_file_jaccard'})
    fingerprints=defaultdict(set)
    paths={f['path'] for f in files}
    for function in result['matrices']['functions']:
        if function['path'] in paths and function.get('eligible') and function.get('fingerprint'):
            fingerprints[function['path']].add((function['basis'],function['fingerprint']))
    # All-pairs is bounded independently of repository size. Uncompared files are not scored zero.
    candidate_paths=set()
    for candidate in result['candidates']:
        retained=candidate['retained'];candidate_paths.add(retained if isinstance(retained,str) else retained['path'])
        candidate_paths.update(copy if isinstance(copy,str) else copy['path'] for copy in candidate['copies'])
    compared=sorted(fingerprints,key=lambda p:(p not in candidate_paths,-len(fingerprints[p]),p))[:200]
    code_pairs=[]
    for a,b in combinations(compared,2):
        x,y=fingerprints[a],fingerprints[b];shared=x&y
        if shared: code_pairs.append({'source':a,'target':b,'coefficient':len(shared)/len(x|y),
            'shared_declarations':len(shared),'distinct_declarations':len(x|y),
            'basis':'declaration_fingerprint_jaccard_not_semantic_equivalence'})
    code_pairs.sort(key=lambda pair:(-pair['coefficient'],-pair['shared_declarations'],pair['source'],pair['target']))
    cells={u:c['id'] for c in result['cells'] for u in c['units']}
    steps=[]; inserted=defaultdict(list)
    for unit in result['roc']['columns']:
        cell=cells[unit];previous=inserted[cell]
        checks=[]
        for other in previous:
            x,y=footprints[unit],footprints[other];union=x|y
            checks.append({'unit':other,'coefficient':len(x&y)/len(union) if union else None})
        steps.append({'unit':unit,'cell':cell,'action':'joined' if previous else 'created','checks':checks})
        previous.append(unit)
    return {'unit_similarity':unit_pairs,'code_similarity':code_pairs[:100],
        'code_scope':{'eligible_files':len(files),'files_with_fingerprints':len(fingerprints),
            'compared_files':len(compared),'compared_paths':compared,'positive_pairs':len(code_pairs),
            'pairs_checked':len(compared)*(len(compared)-1)//2,'retained_pairs':min(100,len(code_pairs)),
            'truncated':len(compared)<len(fingerprints) or len(code_pairs)>100},
        'formation_steps':steps,'threshold':result['assumptions']['cell_similarity']}
