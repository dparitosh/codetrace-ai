#!/usr/bin/env python3
"""
CodeTrace AI - Main Application Entry Point
Independent GitHub Repository Analysis & Self-Correction Platform

This is the main FastAPI application that serves as the backend for CodeTrace AI.
It combines the proven GraphTrace analysis capabilities with GitHub integration
for a complete, standalone product.
"""

from fastapi import FastAPI, HTTPException, Depends, status, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.websockets import WebSocketDisconnect
import uvicorn
import sys
from pathlib import Path
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import jwt
import json
import gc
import psutil
import asyncio
from typing import Dict, Any
from weakref import WeakSet

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Import CodeTrace AI modules
from api.github_routes import github_router
from mcp.integration_routes import mcp_integration_router
from api.analysis_routes import analysis_router
from api.quality_routes import quality_router
from api.graph_routes import graph_router
from api.security_routes import security_router
from mcp.server import MCPServer
from core.config import settings
from core.logging_config import main_logger, track_performance
from database import enhanced_db
from database.init_db import init_database

# Setup logging
logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages application resources and cleanup"""

    def __init__(self):
        self.active_connections = WeakSet()
        self.background_tasks = set()
        self.start_time = datetime.now()
        self.logger = logging.getLogger("resource_manager")

    def add_connection(self, connection):
        """Track active connection"""
        self.active_connections.add(connection)

    def add_background_task(self, task):
        """Track background task"""
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics"""
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "available_mb": psutil.virtual_memory().available / 1024 / 1024,
        }

    async def cleanup_resources(self):
        """Clean up application resources"""
        self.logger.info("Starting resource cleanup...")

        # Cancel background tasks
        if self.background_tasks:
            self.logger.info(
                f"Cancelling {len(self.background_tasks)} background tasks"
            )
            for task in list(self.background_tasks):
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Close active connections
        active_count = len(self.active_connections)
        if active_count > 0:
            self.logger.info(f"Cleaning up {active_count} active connections")

        # Force garbage collection
        collected = gc.collect()
        self.logger.info(f"Garbage collection freed {collected} objects")

        memory_after = self.get_memory_usage()
        self.logger.info(f"Memory usage after cleanup: {memory_after['rss_mb']:.1f}MB")


# Global resource manager
resource_manager = ResourceManager()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan manager with enhanced resource management"""
    # Startup
    main_logger.info("🚀 CodeTrace AI starting up...")

    # Log initial memory usage
    initial_memory = resource_manager.get_memory_usage()
    main_logger.info(f"Initial memory usage: {initial_memory['rss_mb']:.1f}MB")

    # Initialize database with enhanced connection handling
    try:
        await init_database()
        await enhanced_db.initialize()
        status = enhanced_db.get_status()
        if status["connected"]:
            main_logger.info("✅ Database connected successfully")
        elif status["using_fallback"]:
            main_logger.warning("⚠️ Database unavailable - using fallback mode")
        else:
            main_logger.error("❌ Database connection failed")
    except Exception as e:
        main_logger.error(f"Database initialization failed: {e}")
        main_logger.info("📝 Application will continue with fallback capabilities")

    # Initialize MCP Server
    try:
        mcp_server = MCPServer()
        application.state.mcp_server = mcp_server
        application.state.resource_manager = resource_manager
        main_logger.info("✅ MCP Server initialized")
    except Exception as e:
        main_logger.warning(f"⚠️ MCP Server initialization failed: {e}")
        main_logger.info("📝 Application will continue without MCP capabilities")

    # Start background monitoring task
    monitoring_task = asyncio.create_task(monitor_resources())
    resource_manager.add_background_task(monitoring_task)

    startup_memory = resource_manager.get_memory_usage()
    main_logger.info(
        f"Startup completed. Memory usage: {startup_memory['rss_mb']:.1f}MB"
    )
    main_logger.info("✅ CodeTrace AI initialization complete")

    yield

    # Shutdown
    main_logger.info("🔄 CodeTrace AI shutting down...")

    # Cleanup MCP Server
    if hasattr(application.state, "mcp_server"):
        try:
            await application.state.mcp_server.process_request(
                {"jsonrpc": "2.0", "method": "shutdown", "params": {}}
            )
            main_logger.info("✅ MCP Server shut down")
        except Exception as e:
            main_logger.error(f"Error shutting down MCP Server: {e}")

    # Database cleanup
    try:
        await enhanced_db.disconnect()
        main_logger.info("✅ Database disconnected")
    except Exception as e:
        main_logger.error(f"Error disconnecting database: {e}")

    # Comprehensive resource cleanup
    await resource_manager.cleanup_resources()

    final_memory = resource_manager.get_memory_usage()
    main_logger.info(f"Final memory usage: {final_memory['rss_mb']:.1f}MB")
    main_logger.info("✅ CodeTrace AI shutdown complete")


async def monitor_resources():
    """Background task to monitor resource usage"""
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes

            memory = resource_manager.get_memory_usage()

            # Log memory usage if high
            if memory["percent"] > 80:
                main_logger.warning(
                    f"High memory usage: {memory['rss_mb']:.1f}MB ({memory['percent']:.1f}%)"
                )

                # Force garbage collection if memory is very high
                if memory["percent"] > 90:
                    collected = gc.collect()
                    main_logger.info(
                        f"Forced garbage collection freed {collected} objects"
                    )

            # Check for leaked connections
            active_connections = len(resource_manager.active_connections)
            if active_connections > 100:
                main_logger.warning(
                    f"High number of active connections: {active_connections}"
                )

        except asyncio.CancelledError:
            main_logger.info("Resource monitoring stopped")
            break
        except Exception as e:
            main_logger.error(f"Error in resource monitoring: {e}")
        except Exception as e:
            logger.warning("⚠️ MCP Server shutdown error: %s", str(e))

    # Cleanup connections
    try:
        await database.disconnect()
        logger.info("✅ Database disconnected")
    except Exception as e:
        logger.warning("⚠️ Database disconnect error: %s", str(e))

    logger.info("✅ CodeTrace AI shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="CodeTrace AI",
    description="GitHub Repository Analysis & Self-Correction Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Security
security = HTTPBearer()

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Static file serving for analysis outputs
analysis_dir = Path(__file__).parent / "analysis"
if analysis_dir.exists():
    app.mount("/analysis", StaticFiles(directory=str(analysis_dir)), name="analysis")


# Custom exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url),
        },
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring"""
    return {
        "status": "healthy",
        "service": "CodeTrace AI",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "api": "online",
            "database": "connected",
            "github": (
                "connected" if hasattr(app.state, "github_client") else "disconnected"
            ),
        },
    }


# Additional health endpoint for frontend compatibility
@app.get("/api/health")
async def api_health_check():
    """Health check endpoint for frontend API calls"""
    return await health_check()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "CodeTrace AI",
        "description": "GitHub Repository Analysis & Self-Correction Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api_base": "/api/v1",
        "github": "https://github.com/codetrace-ai",
        "website": "https://codetrace.ai",
    }


# API version info
@app.get("/api/v1")
async def api_info():
    """API version information"""
    return {
        "api_version": "v1",
        "service": "CodeTrace AI",
        "endpoints": {
            "github": "/api/v1/github",
            "analysis": "/api/v1/analysis",
            "quality": "/api/v1/quality",
            "graph": "/api/v1/graph",
            "security": "/api/v1/security",
        },
        "authentication": "Bearer token required",
        "rate_limits": {"requests_per_minute": 100, "requests_per_hour": 1000},
    }


# Include API routers
# Include routers
app.include_router(github_router, prefix="/api/v1/github", tags=["GitHub Integration"])
app.include_router(
    mcp_integration_router, prefix="/api/v1/mcp", tags=["MCP Integrations"]
)
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["Code Analysis"])
app.include_router(
    quality_router, prefix="/api/v1/quality", tags=["Quality Assessment"]
)
app.include_router(graph_router, prefix="/api/v1/graph", tags=["Graph Generation"])
app.include_router(
    security_router, prefix="/api/v1/security", tags=["Security & Compliance"]
)


# MCP Server endpoints
@app.websocket("/mcp")
async def mcp_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP communication"""
    await websocket.accept()

    if not hasattr(app.state, "mcp_server"):
        await websocket.close(code=1000, reason="MCP Server not available")
        return

    mcp_server = app.state.mcp_server
    mcp_server.connections.append(websocket)

    try:
        while True:
            # Receive request
            data = await websocket.receive_text()
            request_data = json.loads(data)

            # Process request
            response = await mcp_server.process_request(request_data)

            # Send response
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        logger.info("MCP WebSocket disconnected")
    except Exception as e:
        logger.error("MCP WebSocket error: %s", str(e))
    finally:
        if websocket in mcp_server.connections:
            mcp_server.connections.remove(websocket)


@app.post("/mcp")
async def mcp_http_endpoint(request_data: Dict[str, Any]):
    """HTTP endpoint for MCP communication"""
    if not hasattr(app.state, "mcp_server"):
        raise HTTPException(status_code=503, detail="MCP Server not available")

    mcp_server = app.state.mcp_server
    response = await mcp_server.process_request(request_data)
    return JSONResponse(content=response)


@app.get("/mcp/info")
async def mcp_server_info():
    """Get MCP server information"""
    if not hasattr(app.state, "mcp_server"):
        raise HTTPException(status_code=503, detail="MCP Server not available")

    mcp_server = app.state.mcp_server
    return mcp_server.server_info.dict()


# Authentication dependency
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Validate API token and return user information"""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Validate JWT token
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return {
            "user_id": payload.get("sub"),
            "permissions": payload.get("permissions", ["read"]),
        }
    except jwt.InvalidTokenError as e:
        # For development mode, allow demo access with specific token
        if not settings.DEBUG or credentials.credentials != "demo-token":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        return {"user_id": "demo_user", "permissions": ["read", "write"]}


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )
