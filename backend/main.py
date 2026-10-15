"""CodeTrace AI local-first FastAPI application."""

from contextlib import asynccontextmanager
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import gc
import logging
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from api.graph_routes import graph_router
from api.agent_routes import agent_router
from api.trace_routes import trace_router
from api.quality_routes import quality_router
from api.security_routes import security_router
from api.review_routes import review_router, store as review_store
from api.workspace_routes import workspace_router
from api.oslc_routes import oslc_router, collaboration_router
from core.config import settings

logger = logging.getLogger("codetrace")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.create_directories()
    logger.info("CodeTrace AI local source service started")
    async def expire_sessions():
        while True:
            await asyncio.sleep(min(30, settings.SESSION_IDLE_SECONDS))
            await asyncio.to_thread(review_store.prune)
    sweeper = asyncio.create_task(expire_sessions())
    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper
        if hasattr(review_store, 'close'):
            review_store.close()
        else:
            with review_store.lock:
                review_store.sessions.clear()
                review_store.bytes = 0
        gc.collect()
        logger.info("CodeTrace AI local source service stopped")


app = FastAPI(
    title="CodeTrace AI",
    description="Local-first source-code analysis with optional GitLab project ingestion.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Graph Analysis", "description": "Generate dependency graphs from local folders or GitLab projects."},
        {"name": "Quality Assessment", "description": "Assess local source structure."},
        {"name": "Security & Compliance", "description": "Run local static security checks."},
        {"name": "Agent Context", "description": "Return bounded, versioned source context for coding agents."},
    ],
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware('http')
async def private_review_responses(request, call_next):
    if request.url.path.startswith(('/api/v1/review/', '/api/v1/workspace/', '/api/v1/oslc/')):
        origin = request.headers.get('origin')
        if origin is not None and origin not in settings.CORS_ORIGINS:
            return JSONResponse({'error': 'Review requests must come from an allowed origin.'}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith(('/api/v1/review/', '/api/v1/workspace/', '/api/v1/oslc/')):
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, headers=exc.headers, content={"error": exc.detail, "status_code": exc.status_code, "timestamp": datetime.now(timezone.utc).isoformat(), "path": str(request.url)})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "CodeTrace AI", "version": "1.0.0", "timestamp": datetime.now(timezone.utc).isoformat(), "components": {"api": "online", "source_analysis": "ready"}}


@app.get("/api/health")
async def api_health_check():
    return await health_check()


@app.get("/")
async def root():
    return {"service": "CodeTrace AI", "description": "Local source-code analysis and GitLab-compatible dependency visualization", "docs": "/docs", "health": "/health", "source_modes": ["local-folder", "gitlab"]}


@app.get("/api/v1")
async def api_info():
    return {"api_version": "v1", "endpoints": {"local_graph": "/api/v1/graph/local", "gitlab_graph": "/api/v1/graph/gitlab", "local_quality": "/api/v1/quality/local", "local_security": "/api/v1/security/local", "agent_context": "/api/v1/agent/context"}}


@app.get("/api/v1/capabilities")
async def capabilities():
    """Stable feature manifest so clients can select supported product features."""
    return {"schema_version": "1.0", "features": [
        {"id": "source.local-folder", "enabled": True},
        {"id": "source.gitlab", "enabled": True},
        {"id": "analysis.semantic-graph", "enabled": True},
        {"id": "analysis.networkx-audit", "enabled": True},
        {"id": "agent.bounded-context", "enabled": True},
        {"id": "trace.lifecycle-knowledge-graph", "enabled": True},
        {"id": "trace.jsonld-export", "enabled": True},
    ]}


app.include_router(graph_router, prefix="/api/v1/graph", tags=["Graph Analysis"])
app.include_router(quality_router, prefix="/api/v1/quality", tags=["Quality Assessment"])
app.include_router(security_router, prefix="/api/v1/security", tags=["Security & Compliance"])
app.include_router(agent_router, prefix="/api/v1/agent", tags=["Agent Context"])
app.include_router(trace_router, prefix="/api/v1/trace", tags=["Trace Knowledge Graph"])
app.include_router(review_router, prefix='/api/v1/review', tags=['Review and Approval'])
app.include_router(workspace_router, prefix='/api/v1/workspace', tags=['Managed Intelligence Workspace'])
app.include_router(oslc_router, prefix='/oslc', tags=['OSLC Server'])
app.include_router(collaboration_router, prefix='/api/v1/oslc', tags=['OSLC Collaboration'])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
