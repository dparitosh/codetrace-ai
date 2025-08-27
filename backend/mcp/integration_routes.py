"""
CodeTrace AI - MCP Integration API Routes
Real-world API endpoints using MCP for frontend and GitHub integrations
"""

import json
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import logging

from .client_example import frontend_integration, github_integration

logger = logging.getLogger(__name__)

mcp_integration_router = APIRouter()

# Request/Response Models
class RepositoryAnalysisRequest(BaseModel):
    repository_url: str = Field(..., description="GitHub repository URL")
    detailed: bool = Field(default=True, description="Include detailed analysis")

class FileInsightRequest(BaseModel):
    repository_url: str = Field(..., description="GitHub repository URL")
    file_path: str = Field(..., description="File path to analyze")

class AIPromptRequest(BaseModel):
    prompt_type: str = Field(..., description="Type of prompt (code_review, explain_code, suggest_improvements)")
    repository_url: str = Field(..., description="GitHub repository URL")
    file_path: Optional[str] = Field(default=None, description="Specific file path")
    function_name: Optional[str] = Field(default=None, description="Specific function name")
    focus_areas: Optional[List[str]] = Field(default=None, description="Areas to focus on")

class PullRequestAnalysisRequest(BaseModel):
    repository_url: str = Field(..., description="GitHub repository URL")
    pr_number: int = Field(..., description="Pull request number")

class AutomatedIssueRequest(BaseModel):
    repository_url: str = Field(..., description="GitHub repository URL")
    issue_type: str = Field(..., description="Type of issue (security, performance, quality)")

# Frontend Integration Endpoints
@mcp_integration_router.post("/frontend/repository-analysis")
async def get_repository_analysis_for_frontend(request: RepositoryAnalysisRequest):
    """Get repository analysis formatted for frontend dashboard"""
    try:
        analysis = await frontend_integration.get_repository_analysis_for_frontend(
            request.repository_url
        )
        return {
            "success": True,
            "data": analysis,
            "timestamp": analysis.get("repository", {}).get("analyzed_at")
        }
    except Exception as e:
        logger.error(f"Frontend repository analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@mcp_integration_router.post("/frontend/file-insights")
async def get_file_insights_for_frontend(request: FileInsightRequest):
    """Get code insights for specific file"""
    try:
        insights = await frontend_integration.get_code_insights_for_file(
            request.repository_url,
            request.file_path
        )
        return {
            "success": True,
            "data": insights,
            "file_path": request.file_path
        }
    except Exception as e:
        logger.error(f"File insights failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@mcp_integration_router.post("/frontend/ai-prompt")
async def generate_ai_prompt_for_frontend(request: AIPromptRequest):
    """Generate AI prompt for frontend AI assistance"""
    try:
        kwargs = {}
        if request.file_path:
            kwargs["file_path"] = request.file_path
        if request.function_name:
            kwargs["function_name"] = request.function_name
        if request.focus_areas:
            kwargs["focus_areas"] = request.focus_areas
        
        prompt = await frontend_integration.generate_ai_prompt_for_frontend(
            request.prompt_type,
            request.repository_url,
            **kwargs
        )
        return {
            "success": True,
            "data": prompt,
            "prompt_type": request.prompt_type
        }
    except Exception as e:
        logger.error(f"AI prompt generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# GitHub Integration Endpoints
@mcp_integration_router.post("/github/analyze-pr")
async def analyze_pull_request(request: PullRequestAnalysisRequest):
    """Analyze pull request using MCP capabilities"""
    try:
        analysis = await github_integration.analyze_pull_request(
            request.repository_url,
            request.pr_number
        )
        return {
            "success": True,
            "data": analysis,
            "pr_number": request.pr_number
        }
    except Exception as e:
        logger.error(f"PR analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@mcp_integration_router.post("/github/commit-insights/{commit_sha}")
async def get_commit_insights(repository_url: str, commit_sha: str):
    """Generate insights for a specific commit"""
    try:
        insights = await github_integration.generate_commit_insights(
            repository_url,
            commit_sha
        )
        return {
            "success": True,
            "data": insights,
            "commit_sha": commit_sha
        }
    except Exception as e:
        logger.error(f"Commit insights failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@mcp_integration_router.post("/github/create-automated-issue")
async def create_automated_issue(request: AutomatedIssueRequest):
    """Create automated GitHub issue based on MCP analysis"""
    try:
        issue_data = await github_integration.create_automated_issue(
            request.repository_url,
            request.issue_type
        )
        return {
            "success": True,
            "data": issue_data,
            "ready_for_github": issue_data.get("ready_for_creation", False)
        }
    except Exception as e:
        logger.error(f"Automated issue creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Real-time WebSocket endpoints for frontend
@mcp_integration_router.websocket("/frontend/live-analysis")
async def live_analysis_websocket(websocket):
    """WebSocket endpoint for real-time analysis updates"""
    await websocket.accept()
    
    try:
        while True:
            # Receive analysis request
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
            repository_url = request_data.get("repository_url")
            if not repository_url:
                await websocket.send_text(json.dumps({
                    "error": "repository_url is required"
                }))
                continue
            
            # Send progress updates
            await websocket.send_text(json.dumps({
                "status": "analyzing",
                "progress": 25,
                "message": "Starting repository analysis..."
            }))
            
            # Get analysis via MCP
            analysis = await frontend_integration.get_repository_analysis_for_frontend(
                repository_url
            )
            
            await websocket.send_text(json.dumps({
                "status": "analyzing", 
                "progress": 75,
                "message": "Processing quality metrics..."
            }))
            
            # Send final results
            await websocket.send_text(json.dumps({
                "status": "completed",
                "progress": 100,
                "data": analysis
            }))
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "status": "error",
            "error": str(e)
        }))
    finally:
        await websocket.close()

# Utility endpoints
@mcp_integration_router.get("/health")
async def integration_health_check():
    """Check health of MCP integrations"""
    try:
        # Test frontend integration
        await frontend_integration.init_session()
        frontend_status = "healthy"
        await frontend_integration.close_session()
        
        # Test GitHub integration  
        await github_integration.init_session()
        github_status = "healthy"
        await github_integration.close_session()
        
        return {
            "status": "healthy",
            "integrations": {
                "frontend": frontend_status,
                "github": github_status
            },
            "mcp_server": "connected",
            "timestamp": "2025-08-26T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Integration health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2025-08-26T00:00:00Z"
        }

@mcp_integration_router.get("/capabilities")
async def get_integration_capabilities():
    """Get available integration capabilities"""
    return {
        "frontend_capabilities": [
            "repository_analysis",
            "file_insights", 
            "ai_prompt_generation",
            "live_analysis_updates",
            "visualization_data"
        ],
        "github_capabilities": [
            "pull_request_analysis",
            "commit_insights",
            "automated_issue_creation",
            "webhook_processing",
            "ci_cd_integration"
        ],
        "mcp_features": [
            "real_time_context",
            "quality_metrics",
            "dependency_analysis",
            "code_search",
            "intelligent_prompts"
        ]
    }
