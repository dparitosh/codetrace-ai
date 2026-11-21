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
    # Index every fingerprinted file. Only files sharing a fingerprint can
    # have a positive Jaccard score; no candidate-first 200-file selection.
    postings=defaultdict(list)
    for path,patterns in sorted(fingerprints.items()):
        for pattern in sorted(patterns): postings[pattern].append(path)
    pairs=set(); events=0; maximum_events=200000; complete=True
    for pattern in sorted(postings,key=lambda key:(len(postings[key]),key)):
        for pair in combinations(postings[pattern],2):
            if events>=maximum_events:
                complete=False
                break
            events+=1; pairs.add(pair)
        if not complete: break
    code_pairs=[]
    for a,b in pairs:
        x,y=fingerprints[a],fingerprints[b];shared=x&y
        code_pairs.append({'source':a,'target':b,'coefficient':len(shared)/len(x|y),
            'shared_declarations':len(shared),'distinct_declarations':len(x|y),
            'basis':'declaration_fingerprint_jaccard_not_semantic_equivalence'})
    code_pairs.sort(key=lambda pair:(-pair['coefficient'],-pair['shared_declarations'],pair['source'],pair['target']))
    language_coverage=defaultdict(lambda:{'eligible_files':0,'fingerprinted_files':0})
    unit_coverage=defaultdict(lambda:{'eligible_files':0,'fingerprinted_files':0})
    from pathlib import PurePosixPath
    for file in files:
        for coverage,key in [(language_coverage,PurePosixPath(file['path']).suffix or '(no extension)')]+[(unit_coverage,u) for u in file['memberships'] or ['(unmapped)']]:
            coverage[key]['eligible_files']+=1
            coverage[key]['fingerprinted_files']+=int(file['path'] in fingerprints)
    # Decisions are captured by the assignment algorithm, never reconstructed
    # from the final cells. Historical reports have no decision trace.
    steps=result.get('cell_formation',{}).get('steps',[])
    return {'unit_similarity':unit_pairs,'code_similarity':code_pairs[:100],
        'code_scope':{'eligible_files':len(files),'files_with_fingerprints':len(fingerprints),
            'compared_files':len(fingerprints),'compared_paths':sorted(fingerprints),'positive_pairs':len(code_pairs),
            'pairs_checked':len(pairs),'index_pair_events':events,'pair_event_limit':maximum_events,
            'search_complete':complete,'language_coverage':dict(language_coverage),'unit_coverage':dict(unit_coverage),'retained_pairs':min(100,len(code_pairs)),
            'truncated':not complete or len(code_pairs)>100},
        'formation_steps':steps,'threshold':result['assumptions']['cell_similarity']}
