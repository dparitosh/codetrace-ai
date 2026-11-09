"""Session-scoped, read-only optimization analysis and approval-gated receipts."""
import io
import base64
import hashlib
import json
import time
import zipfile
from fastapi import APIRouter, Header, HTTPException
from pydantic import Field
from api import review_routes
from api.workspace_routes import reviewed_graph
from core.config import settings
from core.optimization_models import OptimizationOptions, ProductContext
from services.product_line_optimizer import analyze, digest

optimization_router=APIRouter(tags=['Product-line optimization'])

class OptimizationRequest(OptimizationOptions):
    review_id: str = Field(min_length=1,max_length=128)
    include_llm: bool = True


def execute(request, token, export=False, ai=False, advice=False, render=None):
    store=review_routes.store
    if not store.workers.acquire(blocking=False): raise HTTPException(429,'Analysis capacity is busy')
    try:
        started=time.monotonic()
        record=store.get(token,request.review_id,export=export)
        graph=reviewed_graph(token,request.review_id)
        options=OptimizationOptions.model_validate(request.model_dump(exclude={'review_id','include_llm'}))
        if not options.units and settings.OPTIMIZATION_UNITS:
            options=options.model_copy(update={'units':settings.OPTIMIZATION_UNITS})
        if options.product_context==ProductContext() and settings.OPTIMIZATION_PRODUCT_CONTEXT!=ProductContext():
            options=options.model_copy(update={'product_context':settings.OPTIMIZATION_PRODUCT_CONTEXT})
        result=analyze(graph,options,record['result_digest'])
        render_reserve=min(settings.AI_FINAL_ANSWER_RESERVE_SECONDS,settings.REQUEST_TIMEOUT_SECONDS/4)
        model_deadline=min(started+settings.REQUEST_TIMEOUT_SECONDS-render_reserve,time.monotonic()+settings.AI_AGENT_DEADLINE_SECONDS)
        if ai:
            from services.classification_ai import propose
            deadline=model_deadline
            result['classification']['ai_review']=propose(result['classification'],store,token,deadline)
            result['receipt']['analysis_sha256']=digest({k:v for k,v in result.items() if k!='receipt'})
        if advice:
            from services.reduction_advisor import review_reductions
            deadline=model_deadline
            result['llm_review']=review_reductions(result,store,token,deadline) if request.include_llm else {'status':'not_requested'}
            result['receipt']['analysis_sha256']=digest({k:v for k,v in result.items() if k!='receipt'})
        response=render(result) if render else result
        store.info(token,touch=False)
        if time.monotonic()-started > settings.REQUEST_TIMEOUT_SECONDS: raise HTTPException(504,'Optimization exceeded the configured deadline')
        return response
    finally: store.workers.release()


@optimization_router.post('/optimization/analyze')
def analyze_optimization(request:OptimizationRequest,x_codetrace_session:str=Header(default=None)):
    result=execute(request,x_codetrace_session)
    result['preview']={'scope':'Receipt digest covers full analysis; table/recommendation lists below are previews.',
        'table_totals':{name:len(rows) for name,rows in result['matrices'].items()},'recommendation_total':len(result['recommendations'])}
    result['matrices']={name:rows[:200] for name,rows in result['matrices'].items()}
    result['recommendations']=result['recommendations'][:100]
    preview_classification(result)
    return result


def preview_classification(result):
    classification=result['classification']
    classification['preview_totals']={name:len(classification[name]) for name in ('mappings','operations','evidence','lexical_proposals')}
    for name in classification['preview_totals']: classification[name]=classification[name][:200]


@optimization_router.post('/optimization/classify-ai')
def classify_ai(request:OptimizationRequest,x_codetrace_session:str=Header(default=None)):
    result=execute(request,x_codetrace_session,ai=True)
    classification=result['classification']
    # The model's cited evidence must survive preview truncation.
    used={key for collection in ('proposals','capabilities','features') for proposal in classification.get('ai_review',{}).get(collection,[]) for key in proposal['citation_ids']}
    observed=[item for item in classification['evidence'] if item['id'] in used]
    preview_classification(result)
    classification['ai_evidence']=observed
    return {'classification':classification,'receipt':result['receipt']}


@optimization_router.post('/optimization/report')
def preview_report(request:OptimizationRequest,x_codetrace_session:str=Header(default=None)):
    def render(result):
        from services.optimization_report import report_html
        document=report_html(result,'Retained source snapshot '+str(result['receipt'].get('snapshot_id') or request.review_id))
        # Supporting files belong to the approval-gated export, not unauthenticated iframe navigation.
        for filename in ('file-unit.csv','function-unit.csv','analysis.json','call-evidence.json','receipt.json'):
            document=document.replace('href="'+filename+'"','aria-disabled="true"')
        document=document.replace('href="#','href="about:srcdoc#')
        policy="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
        document=document.replace('<head>','<head><meta http-equiv="Content-Security-Policy" content="'+policy+'">',1)
        body=document.encode('utf-8')
        if len(body)>settings.OPTIMIZATION_MAX_EXPORT_BYTES:
            raise HTTPException(413,'Report preview exceeds the configured byte limit; narrow the source or feature selectors')
        return {'html':document,'html_sha256':hashlib.sha256(body).hexdigest(),'receipt':result['receipt']}
    return execute(request,x_codetrace_session,advice=True,render=render)


@optimization_router.post('/optimization/export')
def export_optimization(request:OptimizationRequest,x_codetrace_session:str=Header(default=None)):
    def render(result):
        from services.optimization_report import assessment_documents
        documents=assessment_documents(result,'Retained source snapshot '+str(result['receipt'].get('snapshot_id') or request.review_id))
        result['receipt']['artifacts']={name:hashlib.sha256(body).hexdigest() for name,body in documents.items()}
        documents['receipt.json']=json.dumps(result['receipt'],indent=2).encode()
        if sum(map(len,documents.values()))>settings.OPTIMIZATION_MAX_EXPORT_BYTES:
            raise HTTPException(413,'Optimization export exceeds the configured byte limit')
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,body in documents.items(): archive.writestr(name,body)
        return {'filename':'product-line-analysis.zip','archive_base64':base64.b64encode(output.getvalue()).decode(), 'receipt':result['receipt']}
    return execute(request,x_codetrace_session,export=True,advice=True,render=render)
