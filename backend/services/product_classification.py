"""Repository-independent product context and evidence mappings; no source execution.

Configured mappings are declarations, lexical/LLM matches are proposals. Neither
establishes business correctness or semantic equivalence. OpenAPI refs are never
fetched and server URLs, examples, security material and source bodies are omitted.
"""
import fnmatch
import hashlib
import json
import re
from collections import Counter, defaultdict
from fastapi import HTTPException


def tokens(value):
    return set(re.findall(r'[a-z][a-z0-9]{2,}',re.sub(r'([a-z])([A-Z])',r'\1 \2',value).lower()))


def classify(result, context, artifacts):
    operations=[]; diagnostics=[]; seen=set(); ambiguous=set()
    for artifact in artifacts:
        for path,item in artifact.document.get('paths',{}).items():
            if not isinstance(item,dict):
                diagnostics.append('Unsupported non-object path item in '+artifact.id);continue
            if '$ref' in item: diagnostics.append('Path-item reference not dereferenced in '+artifact.id)
            for method,op in item.items():
                if method.lower() not in {'get','post','put','patch','delete','head','options','trace'} or not isinstance(op,dict): continue
                if len(operations)>=500:
                    diagnostics.append('OpenAPI operations truncated at 500');break
                operation_id=op.get('operationId')
                if not isinstance(operation_id,str): operation_id=method.upper()+' '+str(path)
                key=artifact.id+':'+operation_id
                if key in seen: diagnostics.append('Duplicate operation identity: '+key);ambiguous.add(key);continue
                seen.add(key)
                operations.append({'id':key,'operation_id':operation_id[:200],'method':method.upper(),
                    'path':str(path)[:500],'summary':str(op.get('summary',''))[:500],
                    'tags':[tag[:100] for tag in op.get('tags',[])[:20] if isinstance(tag,str)] if isinstance(op.get('tags',[]),list) else [],
                    'feature_ids':[],'status':'contract_observed'})
    operation_counts=Counter(op['operation_id'] for op in operations)
    files={row['path']:row for row in result['matrices']['files'] if row['eligible']}
    functions={row['id']:row for row in result['matrices']['functions'] if row['path'] in files}
    functions_by_path=defaultdict(list)
    for key,row in functions.items(): functions_by_path[row['path']].append((key,row))
    mappings=[]; matched_features=set()
    def add_mapping(mapping):
        if len(mappings)>=20000: raise HTTPException(413,'Classification exceeds 20000 mappings; narrow feature selectors or source scope')
        mappings.append(mapping)
    # Explicit function IDs remain function-scoped; file membership is not spread to siblings.
    for feature in context.features:
        for selector in feature.paths:
            hits=[path for path in files if fnmatch.fnmatchcase(path,selector)]
            if not hits: diagnostics.append(f'{feature.id}: unmatched path selector {selector}')
            for path in hits:
                add_mapping({'artifact_id':files[path]['node_id'],'path':path,'kind':'file','feature_id':feature.id,
                    'capability_id':feature.capability_id,'status':'configured_mapping','basis':'path_selector:'+selector})
                matched_features.add(feature.id)
                for key,row in functions_by_path[path]:
                    add_mapping({'artifact_id':key,'path':path,'kind':'function','feature_id':feature.id,
                        'capability_id':feature.capability_id,'status':'configured_file_derived','basis':'file_mapping'})
        for key in feature.function_ids:
            if key not in functions: diagnostics.append(f'{feature.id}: unknown function ID {key}');continue
            add_mapping({'artifact_id':key,'path':functions[key]['path'],'kind':'function','feature_id':feature.id,
                'capability_id':feature.capability_id,'status':'configured_mapping','basis':'exact_function_id'})
            matched_features.add(feature.id)
        for operation_id in feature.operation_ids:
            hits=[op for op in operations if op['id'] not in ambiguous and (op['id']==operation_id or (op['operation_id']==operation_id and operation_counts[operation_id]==1))]
            if not hits: diagnostics.append(f'{feature.id}: missing or ambiguous operation {operation_id}')
            for op in hits:
                if feature.id not in op['feature_ids']: op['feature_ids'].append(feature.id)
                matched_features.add(feature.id)
    # Dedupe overlapping selectors without losing scope/status distinctions.
    mappings=list({(m['artifact_id'],m['feature_id'],m['status']):m for m in mappings}.values())
    profiles=defaultdict(set)
    for mapping in mappings: profiles[mapping['artifact_id']].add(mapping['feature_id'])
    grouped=defaultdict(list)
    for artifact_id,feature_ids in profiles.items(): grouped[tuple(sorted(feature_ids))].append(artifact_id)
    file_ids={r['node_id'] for r in files.values()}
    artifact_groups=[{'feature_ids':list(feature_ids),'artifact_count':len(identities),
        'file_count':sum(key in file_ids for key in identities),
        'function_count':sum(key in functions for key in identities),
        'basis':'exact_configured_feature_profile_not_semantic_equivalence'}
        for feature_ids,identities in sorted(grouped.items())]
    mapped_paths={m['path'] for m in mappings}
    candidates=[]
    feature_tokens={f.id:tokens(f.label+' '+f.description+' '+' '.join(d.text for d in context.documents if f.id in d.feature_ids)) for f in context.features}
    for path,row in sorted(files.items()):
        if path in mapped_paths: continue
        terms=tokens(path+' '+' '.join(f['name'] for _,f in functions_by_path[path]))
        scores=[(len(terms&t)/len(terms|t),fid,sorted(terms&t)) for fid,t in feature_tokens.items() if terms&t]
        if scores:
            score,fid,overlap=max(scores,key=lambda item:(item[0],item[1]))
            candidates.append({'artifact_id':row['node_id'],'path':path,'feature_id':fid,'status':'proposed_lexical',
                'similarity':round(score,6),'matched_terms':overlap,'basis':'name_token_jaccard_not_behavior'})
    candidates.sort(key=lambda p:(-p['similarity'],p['artifact_id']))
    features={f.id:f for f in context.features}; configurations=[]
    for product in context.products:
        selected=set(product.features);errors=[]
        for f in context.features:
            if f.kind=='mandatory' and f.id not in selected: errors.append('Missing mandatory feature: '+f.id)
            if f.id in selected:
                errors.extend(f.id+' requires '+key for key in f.requires if key not in selected)
                errors.extend(f.id+' excludes '+key for key in f.excludes if key in selected)
        groups={f.alternative_group for f in context.features if f.kind=='alternative'}
        for group in sorted(groups):
            if sum(f.id in selected for f in context.features if f.kind=='alternative' and f.alternative_group==group)!=1:
                errors.append('Select exactly one alternative in '+group)
        configurations.append({'id':product.id,'status':'invalid_declared_configuration' if errors else 'declared_constraints_satisfied',
            'errors':errors,'source_tests_run':False})
    similarities=[]
    for i,a in enumerate(context.products):
        for b in context.products[i+1:]:
            x,y=set(a.features),set(b.features)
            similarities.append({'source':a.id,'target':b.id,'coefficient':len(x&y)/len(x|y) if x|y else None,
                'shared_features':sorted(x&y),'basis':'declared_feature_jaccard'})
    # Source evidence only. No provider calls occur in this deterministic stage.
    evidence=[]
    for path,row in sorted(files.items()):
        evidence.append({'id':'E'+str(len(evidence)+1),'artifact_id':row['node_id'],'path':path,'kind':'file',
            'functions':[{'id':f['id'],'name':f['name']} for _,f in functions_by_path[path]][:12]})
        for key,function in functions_by_path[path]:
            evidence.append({'id':'E'+str(len(evidence)+1),'artifact_id':key,'path':path,'kind':'function',
                'name':function['name'],'start':function['start'],'end':function['end'],'basis':function['basis']})
    return {'status':'configured_model' if features else 'classification_requires_product_context',
        'family':context.family,'capabilities':[c.model_dump() for c in context.capabilities],
        'features':[f.model_dump() for f in context.features],'products':[p.model_dump() for p in context.products],
        'mappings':mappings,'artifact_groups':artifact_groups,'operations':operations,'lexical_proposals':candidates[:200],
        'proposal_total':len(candidates),'configurations':configurations,'feature_similarity':similarities,
        'documents':[{'id':d.id,'title':d.title,'feature_ids':d.feature_ids,
            'sha256':hashlib.sha256(d.text.encode()).hexdigest(),'status':'supplied_document_not_verified'} for d in context.documents],
        'coverage':{'eligible_files':len(files),'files_with_configured_evidence':len(mapped_paths),
            'functions_with_configured_evidence':len({m['artifact_id'] for m in mappings if m['kind']=='function'}),
            'files_requiring_classification':len(files)-len(mapped_paths),'unmapped_features':sorted(set(features)-matched_features)},
        'evidence':evidence,'diagnostics':diagnostics,
        'limitations':['Configured mappings are user declarations, not verified functional correctness.',
            'Lexical similarity is a review proposal, not behavioral equivalence.',
            'API operations are contract observations, not source-handler links or runtime success.',
            'Feature constraints are checked as declared; products have not been built or tested.',
            'Frontend, infrastructure, scripts and plugins can be mapped explicitly like other supported files.']}


def validate_proposals(text, classification, supplied):
    from pydantic import BaseModel, ConfigDict, Field
    class Proposal(BaseModel):
        model_config=ConfigDict(extra='forbid')
        artifact_id: str = Field(max_length=2048)
        feature_id: str = Field(max_length=100)
        rationale: str = Field(min_length=1,max_length=2000)
        citation_ids: list[str] = Field(min_length=1,max_length=10)
    from core.optimization_models import Capability
    class SuggestedCapability(Capability):
        citation_ids: list[str] = Field(min_length=1,max_length=10)
    class SuggestedFeature(SuggestedCapability):
        capability_id: str = Field(min_length=1,max_length=100)
    class Answer(BaseModel):
        model_config=ConfigDict(extra='forbid')
        proposals: list[Proposal] = Field(max_length=50)
        capabilities: list[SuggestedCapability] = Field(default_factory=list,max_length=20)
        features: list[SuggestedFeature] = Field(default_factory=list,max_length=40)
    answer=Answer.model_validate_json(text)
    known={item['id']:item['artifact_id'] for item in supplied}
    capabilities={c['id'] for c in classification['capabilities']}
    features={f['id'] for f in classification['features']}
    for collection,existing in ((answer.capabilities,capabilities),(answer.features,features)):
        ids=[item.id for item in collection]
        if len(set(ids))!=len(ids) or set(ids)&existing: raise ValueError('Duplicate or conflicting taxonomy identifiers')
        if any(any(key not in known for key in item.citation_ids) for item in collection): raise ValueError('Unknown taxonomy evidence citation')
    if any(f.capability_id not in capabilities|{c.id for c in answer.capabilities} for f in answer.features):
        raise ValueError('Unknown proposed capability')
    features.update(f.id for f in answer.features)
    proposals=[]
    for p in answer.proposals:
        if p.feature_id not in features or any(key not in known for key in p.citation_ids): raise ValueError('Unknown feature or evidence citation')
        if not set(re.findall(r'\[(E\d+)\]',p.rationale))<=set(p.citation_ids): raise ValueError('Unobserved inline citation')
        if p.artifact_id not in {known[key] for key in p.citation_ids}: raise ValueError('Citation does not support the proposed artifact identity')
        proposals.append({**p.model_dump(),'status':'proposed_llm_requires_review'})
    return {'proposals':proposals,'capabilities':[c.model_dump() for c in answer.capabilities],
        'features':[f.model_dump() for f in answer.features]}
