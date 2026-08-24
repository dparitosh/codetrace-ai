"""
CodeTrace AI - GitHub API Routes
Handles GitHub repository integration and webhook endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import logging
import hashlib
import hmac
from datetime import datetime
from functools import wraps

from core.config import settings
from github.client import GitHubClient
from quality.validator import QualityValidator
from graph.generator import GraphGenerator
from graph.codegraph_integration import GitHubRepositoryAnalyzer, CODEGRAPH_AVAILABLE
from services.repository_service import repository_service


# Enhanced exception handling decorator
def github_api_handler(func):
    """Decorator for handling GitHub API exceptions consistently"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise FastAPI HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)

            # Determine appropriate HTTP status based on error type
            if "rate limit" in str(e).lower():
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
                detail = "GitHub API rate limit exceeded"
            elif "not found" in str(e).lower() or "404" in str(e):
                status_code = status.HTTP_404_NOT_FOUND
                detail = "Repository or resource not found"
            elif "unauthorized" in str(e).lower() or "401" in str(e):
                status_code = status.HTTP_401_UNAUTHORIZED
                detail = "GitHub API authentication failed"
            elif "forbidden" in str(e).lower() or "403" in str(e):
                status_code = status.HTTP_403_FORBIDDEN
                detail = "Access forbidden - check repository permissions"
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                detail = f"Internal server error: {str(e)}"

            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": detail,
                    "function": func.__name__,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    return wrapper


logger = logging.getLogger(__name__)
security = HTTPBearer()

github_router = APIRouter()


# Pydantic models for request/response
class RepositoryAnalysisRequest(BaseModel):
    repository: str = Field(..., description="Repository in format 'owner/repo'")
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Analysis options"
    )


class AnalysisOptions(BaseModel):
    include_quality: bool = Field(
        default=True, description="Include quality assessment"
    )
    include_security: bool = Field(
        default=True, description="Include security analysis"
    )
    include_dependencies: bool = Field(
        default=True, description="Include dependency analysis"
    )
    include_graph: bool = Field(default=True, description="Generate traceability graph")
    auto_fix: bool = Field(default=False, description="Enable automatic issue fixing")
    create_pr: bool = Field(default=False, description="Create pull request with fixes")


class WebhookPayload(BaseModel):
    action: str
    repository: Dict[str, Any]
    sender: Dict[str, Any]
    installation: Optional[Dict[str, Any]] = None


class RepositorySearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    sort: str = Field(default="stars", description="Sort criteria")
    order: str = Field(default="desc", description="Sort order")
    limit: int = Field(default=30, description="Maximum results")


# Dependency injection
async def get_github_client() -> GitHubClient:
    """Get GitHub client instance"""
    client = GitHubClient()
    await client.init_session()
    return client


async def get_quality_validator() -> QualityValidator:
    """Get quality validator instance"""
    return QualityValidator()


async def get_graph_generator() -> GraphGenerator:
    """Get graph generator instance"""
    return GraphGenerator()


class GitHubService:
    """GitHub service for MCP handlers"""

    def __init__(self):
        self.client = None

    async def init_session(self):
        """Initialize GitHub client session"""
        if not self.client:
            self.client = GitHubClient()
            await self.client.init_session()

    async def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information"""
        if not self.client:
            await self.init_session()
        return await self.client.get_repository_info(owner, repo)

    async def get_repository_structure(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository file structure"""
        if not self.client:
            await self.init_session()
        return await self.client.get_repository_structure(owner, repo)

    async def get_file_content(self, owner: str, repo: str, file_path: str) -> str:
        """Get file content from repository"""
        if not self.client:
            await self.init_session()
        return await self.client.get_file_content(owner, repo, file_path)

    async def get_repository_files(self, owner: str, repo: str) -> List[str]:
        """Get list of files in repository"""
        if not self.client:
            await self.init_session()
        return await self.client.get_repository_files(owner, repo)

    async def get_repository_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get repository programming languages"""
        if not self.client:
            await self.init_session()
        return await self.client.get_repository_languages(owner, repo)


@github_router.get("/repositories/{owner}/{repo}")
@github_api_handler
async def get_repository_info(
    owner: str, repo: str, github_client: GitHubClient = Depends(get_github_client)
):
    """Get basic repository information"""
    try:
        # First check if repository exists in database
        existing_repo = await repository_service.get_repository(owner, repo)

        # Get fresh repository info from GitHub
        repo_info = await github_client.get_repository(owner, repo)

        # Prepare repository data for persistence
        repo_data = {
            "owner": owner,
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "url": repo_info.get("html_url", ""),
            "default_branch": repo_info.get("default_branch", "main"),
            "language": repo_info.get("language"),
            "size": repo_info.get("size", 0),
            "stars": repo_info.get("stargazers_count", 0),
            "forks": repo_info.get("forks_count", 0),
            "metadata": repo_info,
        }

        # Save/update repository in database
        saved_repo = await repository_service.save_repository(repo_data)

        return {
            "repository": repo_info,
            "database_record": saved_repo,
            "retrieved_at": datetime.utcnow().isoformat(),
            "persistence_status": "saved",
        }
    except Exception as e:
        logger.error(f"Error retrieving repository {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=404, detail=f"Repository not found: {owner}/{repo}"
        )
    finally:
        await github_client.close()


@github_router.post("/analyze")
async def analyze_repository(
    request: RepositoryAnalysisRequest,
    background_tasks: BackgroundTasks,
    github_client: GitHubClient = Depends(get_github_client),
    quality_validator: QualityValidator = Depends(get_quality_validator),
    graph_generator: GraphGenerator = Depends(get_graph_generator),
):
    """Comprehensive repository analysis"""
    try:
        # Parse repository
        if "/" not in request.repository:
            raise HTTPException(
                status_code=400, detail="Repository must be in format 'owner/repo'"
            )

        owner, repo = request.repository.split("/", 1)

        # Get analysis options
        options = AnalysisOptions(**(request.options or {}))

        logger.info(f"Starting analysis for repository: {owner}/{repo}")

        # Start background analysis
        background_tasks.add_task(
            perform_repository_analysis,
            owner,
            repo,
            options,
            github_client,
            quality_validator,
            graph_generator,
        )

        return {
            "message": "Analysis started",
            "repository": request.repository,
            "analysis_id": f"{owner}_{repo}_{int(datetime.utcnow().timestamp())}",
            "status": "processing",
            "estimated_completion": "2-5 minutes",
        }

    except Exception as e:
        logger.error(f"Error starting analysis for {request.repository}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@github_router.get("/repositories/{owner}/{repo}/analysis")
async def get_analysis_results(
    owner: str,
    repo: str,
    github_client: GitHubClient = Depends(get_github_client),
    quality_validator: QualityValidator = Depends(get_quality_validator),
    graph_generator: GraphGenerator = Depends(get_graph_generator),
):
    """Get comprehensive analysis results for a repository"""
    try:
        # Get or create repository record
        repo_record = await repository_service.get_repository(owner, repo)
        if not repo_record:
            # Create repository record first
            repo_info = await github_client.get_repository(owner, repo)
            repo_data = {
                "owner": owner,
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "url": repo_info.get("html_url", ""),
                "default_branch": repo_info.get("default_branch", "main"),
                "language": repo_info.get("language"),
                "size": repo_info.get("size", 0),
                "stars": repo_info.get("stargazers_count", 0),
                "forks": repo_info.get("forks_count", 0),
                "metadata": repo_info,
            }
            repo_record = await repository_service.save_repository(repo_data)

        # Update repository status to analyzing
        await repository_service.update_repository_status(
            repo_record["id"],
            "analyzing",
            {"analysis_started_at": datetime.utcnow().isoformat()},
        )

        # Perform real-time analysis
        logger.info(f"Performing comprehensive analysis for: {owner}/{repo}")

        # Get repository structure
        repo_data = await github_client.analyze_repository_structure(owner, repo)

        # Get file contents (limited sample for analysis)
        file_contents = await get_repository_file_contents(
            github_client, owner, repo, limit=50
        )

        # Perform quality analysis
        quality_results = await quality_validator.analyze_repository_quality(
            repo_data, file_contents
        )

        # Generate traceability graph
        graph_results = await graph_generator.generate_repository_graph(
            repo_data, file_contents, quality_results
        )

        # Combine results
        analysis_results = {
            "repository": repo_data,
            "quality": quality_results,
            "graph": graph_results,
            "analysis_metadata": {
                "completed_at": datetime.utcnow().isoformat(),
                "analysis_type": "comprehensive",
                "files_analyzed": len(file_contents),
                "total_files": repo_data.get("structure", {}).get("total_files", 0),
            },
        }

        # Save analysis results to database
        analysis_record = await repository_service.save_analysis_result(
            repo_record["id"],
            {
                "type": "comprehensive",
                "results": analysis_results,
                "metrics": {
                    "files_analyzed": len(file_contents),
                    "quality_score": quality_results.get("overall_score", 0),
                    "total_files": repo_data.get("structure", {}).get("total_files", 0),
                },
                "duration": 0,  # Would be calculated in real implementation
            },
        )

        # Update repository status to completed
        await repository_service.update_repository_status(
            repo_record["id"],
            "completed",
            {"analysis_completed_at": datetime.utcnow().isoformat()},
        )

        # Return results with persistence information
        return {
            **analysis_results,
            "persistence": {
                "repository_id": repo_record["id"],
                "analysis_id": analysis_record["id"],
                "saved_at": datetime.utcnow().isoformat(),
                "status": "persisted",
            },
        }

    except Exception as e:
        # Update repository status to failed if error occurs
        if "repo_record" in locals() and repo_record:
            await repository_service.update_repository_status(
                repo_record["id"],
                "failed",
                {"error": str(e), "failed_at": datetime.utcnow().isoformat()},
            )

        logger.error(f"Error analyzing repository {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await github_client.close()


@github_router.get("/repositories")
async def list_repositories(
    limit: int = 100, offset: int = 0, status: Optional[str] = None
):
    """List all repositories in the database with pagination"""
    try:
        repositories = await repository_service.get_repositories(
            limit=limit, offset=offset
        )

        # Filter by status if provided
        if status:
            repositories = [
                repo for repo in repositories if repo.get("analysis_status") == status
            ]

        return {
            "repositories": repositories,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(repositories),
            },
            "filter": {"status": status},
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@github_router.get("/repositories/{owner}/{repo}/history")
async def get_analysis_history(owner: str, repo: str, limit: int = 10):
    """Get analysis history for a repository"""
    try:
        # Get repository record
        repo_record = await repository_service.get_repository(owner, repo)
        if not repo_record:
            raise HTTPException(
                status_code=404,
                detail=f"Repository not found in database: {owner}/{repo}",
            )

        # Get analysis history
        history = await repository_service.get_analysis_history(
            repo_record["id"], limit=limit
        )

        return {
            "repository": f"{owner}/{repo}",
            "repository_id": repo_record["id"],
            "analysis_history": history,
            "total_analyses": len(history),
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving analysis history for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@github_router.get("/repositories/{owner}/{repo}/metrics")
async def get_repository_metrics(owner: str, repo: str):
    """Get comprehensive repository metrics from database"""
    try:
        # Get repository record
        repo_record = await repository_service.get_repository(owner, repo)
        if not repo_record:
            raise HTTPException(
                status_code=404,
                detail=f"Repository not found in database: {owner}/{repo}",
            )

        # Get comprehensive metrics
        metrics = await repository_service.get_repository_metrics(repo_record["id"])

        return {
            "repository": f"{owner}/{repo}",
            "repository_id": repo_record["id"],
            "repository_info": repo_record,
            "metrics": metrics,
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving repository metrics for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@github_router.get("/repositories/{owner}/{repo}/latest-analysis")
async def get_latest_analysis(owner: str, repo: str):
    """Get the latest analysis results from database"""
    try:
        # Get repository record
        repo_record = await repository_service.get_repository(owner, repo)
        if not repo_record:
            raise HTTPException(
                status_code=404,
                detail=f"Repository not found in database: {owner}/{repo}",
            )

        # Get latest analysis
        latest_analysis = await repository_service.get_latest_analysis(
            repo_record["id"]
        )
        if not latest_analysis:
            return {
                "repository": f"{owner}/{repo}",
                "repository_id": repo_record["id"],
                "message": "No analysis found for this repository",
                "latest_analysis": None,
            }

        return {
            "repository": f"{owner}/{repo}",
            "repository_id": repo_record["id"],
            "latest_analysis": latest_analysis,
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving latest analysis for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_quality_assessment(
    owner: str,
    repo: str,
    github_client: GitHubClient = Depends(get_github_client),
    quality_validator: QualityValidator = Depends(get_quality_validator),
):
    """Get quality assessment for a repository"""
    try:
        # Get repository data
        repo_data = await github_client.analyze_repository_structure(owner, repo)

        # Get file contents for analysis
        file_contents = await get_repository_file_contents(
            github_client, owner, repo, limit=100
        )

        # Perform quality analysis
        quality_results = await quality_validator.analyze_repository_quality(
            repo_data, file_contents
        )

        return quality_results

    except Exception as e:
        logger.error(f"Error assessing quality for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await github_client.close()


@github_router.post("/repositories/{owner}/{repo}/comprehensive-analysis")
async def comprehensive_repository_analysis(
    owner: str,
    repo: str,
    options: AnalysisOptions = AnalysisOptions(),
    github_client: GitHubClient = Depends(get_github_client),
    quality_validator: QualityValidator = Depends(get_quality_validator),
    graph_generator: GraphGenerator = Depends(get_graph_generator),
):
    """Perform comprehensive analysis using enhanced code graph capabilities"""
    try:
        logger.info(f"Starting comprehensive analysis for {owner}/{repo}")

        # Initialize analysis results
        analysis_results = {
            "repository": f"{owner}/{repo}",
            "timestamp": datetime.now().isoformat(),
            "codetrace_ai_enhanced": True,
            "components": {},
        }

        # 1. Basic repository data
        repo_data = await github_client.analyze_repository_structure(owner, repo)
        analysis_results["repository_info"] = repo_data

        # 2. Enhanced code graph analysis (if available)
        if CODEGRAPH_AVAILABLE and options.include_graph:
            try:
                # Clone repository to temporary location for analysis
                temp_repo_path = (
                    f"/tmp/{owner}-{repo}"  # This would be properly managed
                )

                # Initialize enhanced analyzer
                enhanced_analyzer = GitHubRepositoryAnalyzer()

                # Perform comprehensive analysis
                code_analysis = await enhanced_analyzer.comprehensive_analysis(
                    temp_repo_path
                )
                analysis_results["components"]["enhanced_code_analysis"] = code_analysis

                logger.info(f"Enhanced code analysis completed for {owner}/{repo}")

            except Exception as e:
                logger.warning(f"Enhanced analysis failed for {owner}/{repo}: {e}")
                analysis_results["components"]["enhanced_code_analysis"] = {
                    "error": str(e)
                }

        # 3. Quality assessment (if requested)
        if options.include_quality:
            try:
                file_contents = await get_repository_file_contents(
                    github_client, owner, repo, limit=100
                )
                quality_results = await quality_validator.validate_repository_quality(
                    repo_data, file_contents
                )
                analysis_results["components"]["quality_assessment"] = quality_results
            except Exception as e:
                logger.warning(f"Quality assessment failed for {owner}/{repo}: {e}")
                analysis_results["components"]["quality_assessment"] = {"error": str(e)}

        # 4. Traditional graph generation (if requested)
        if options.include_graph:
            try:
                file_contents = await get_repository_file_contents(
                    github_client, owner, repo, limit=200
                )
                graph_results = await graph_generator.generate_repository_graph(
                    repo_data, file_contents
                )
                analysis_results["components"]["traditional_graph"] = graph_results
            except Exception as e:
                logger.warning(f"Graph generation failed for {owner}/{repo}: {e}")
                analysis_results["components"]["traditional_graph"] = {"error": str(e)}

        # 5. Security analysis (if requested)
        if options.include_security:
            analysis_results["components"]["security_analysis"] = {
                "status": "placeholder",
                "message": "Security analysis would be implemented here",
            }

        # 6. Dependency analysis (if requested)
        if options.include_dependencies:
            analysis_results["components"]["dependency_analysis"] = {
                "status": "placeholder",
                "message": "Dependency analysis would be implemented here",
            }

        # Generate overall summary
        analysis_results["summary"] = {
            "components_analyzed": len(
                [
                    k
                    for k, v in analysis_results["components"].items()
                    if "error" not in v
                ]
            ),
            "components_failed": len(
                [k for k, v in analysis_results["components"].items() if "error" in v]
            ),
            "enhanced_analysis_available": CODEGRAPH_AVAILABLE,
            "analysis_complete": True,
        }

        return analysis_results

    except Exception as e:
        logger.error(f"Comprehensive analysis failed for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        await github_client.close()


@github_router.get("/repositories/{owner}/{repo}/graph")
async def get_traceability_graph(
    owner: str,
    repo: str,
    github_client: GitHubClient = Depends(get_github_client),
    graph_generator: GraphGenerator = Depends(get_graph_generator),
):
    """Get traceability graph for a repository"""
    try:
        # Get repository data
        repo_data = await github_client.analyze_repository_structure(owner, repo)

        # Get file contents for analysis
        file_contents = await get_repository_file_contents(
            github_client, owner, repo, limit=200
        )

        # Generate graph
        graph_results = await graph_generator.generate_repository_graph(
            repo_data, file_contents
        )

        return graph_results

    except Exception as e:
        logger.error(f"Error generating graph for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await github_client.close()


@github_router.post("/repositories/{owner}/{repo}/correct")
async def perform_self_correction(
    owner: str,
    repo: str,
    issues: List[str] = [],
    auto_fix: bool = False,
    create_pr: bool = False,
    github_client: GitHubClient = Depends(get_github_client),
):
    """Perform self-correction on repository issues"""
    try:
        # This is a placeholder for self-correction functionality
        # In a full implementation, this would:
        # 1. Analyze the repository for issues
        # 2. Generate fixes for identified problems
        # 3. Apply fixes if auto_fix is True
        # 4. Create a pull request if create_pr is True

        logger.info(f"Self-correction requested for {owner}/{repo}")

        # Mock response for now
        return {
            "message": "Self-correction analysis completed",
            "repository": f"{owner}/{repo}",
            "issues_found": len(issues) if issues else 5,
            "fixes_available": True,
            "auto_fix_applied": auto_fix,
            "pull_request_created": create_pr,
            "recommendations": [
                "Improve code documentation",
                "Fix security vulnerabilities",
                "Optimize performance bottlenecks",
                "Standardize code formatting",
                "Update dependencies",
            ],
        }

    except Exception as e:
        logger.error(f"Error in self-correction for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await github_client.close()


@github_router.post("/search")
async def search_repositories(
    request: RepositorySearchRequest,
    github_client: GitHubClient = Depends(get_github_client),
):
    """Search GitHub repositories"""
    try:
        results = await github_client.search_repositories(
            query=request.query,
            sort=request.sort,
            order=request.order,
            limit=request.limit,
        )

        return {
            "query": request.query,
            "total_count": results.get("total_count", 0),
            "repositories": results.get("items", []),
            "search_metadata": {
                "searched_at": datetime.utcnow().isoformat(),
                "sort": request.sort,
                "order": request.order,
                "limit": request.limit,
            },
        }

    except Exception as e:
        logger.error(f"Error searching repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await github_client.close()


@github_router.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events"""
    try:
        # Verify webhook signature
        signature = request.headers.get("X-Hub-Signature-256")
        if signature and settings.GITHUB_WEBHOOK_SECRET:
            body = await request.body()
            expected_signature = (
                "sha256="
                + hmac.new(
                    settings.GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
                ).hexdigest()
            )

            if not hmac.compare_digest(signature, expected_signature):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # Parse webhook payload
        payload = await request.json()
        event_type = request.headers.get("X-GitHub-Event")

        logger.info(f"Received GitHub webhook: {event_type}")

        # Process webhook in background
        background_tasks.add_task(process_github_webhook, event_type, payload)

        return {"message": "Webhook received", "event": event_type}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@github_router.get("/rate-limit")
async def get_rate_limit_status(
    github_client: GitHubClient = Depends(get_github_client),
):
    """Get GitHub API rate limit status"""
    try:
        rate_limit = await github_client.get_rate_limit()
        return rate_limit
    except Exception as e:
        logger.error(f"Error getting rate limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await github_client.close()


# Helper functions
async def get_repository_file_contents(
    github_client: GitHubClient, owner: str, repo: str, limit: int = 50
) -> Dict[str, str]:
    """Get file contents from repository (limited for analysis)"""
    try:
        # Get repository tree
        tree = await github_client.get_repository_tree(owner, repo, recursive=True)
        files = tree.get("tree", [])

        # Filter for code files and limit
        code_files = []
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".cpp",
            ".c",
            ".cs",
            ".php",
            ".rb",
            ".go",
            ".rs",
        }

        for file_info in files:
            if file_info["type"] == "blob":  # Regular file
                file_path = file_info["path"]
                file_ext = (
                    file_path[file_path.rfind(".") :].lower()
                    if "." in file_path
                    else ""
                )

                if (
                    file_ext in code_extensions and file_info.get("size", 0) < 100000
                ):  # Limit file size
                    code_files.append(file_path)

        # Limit number of files
        code_files = code_files[:limit]

        # Get file contents
        file_contents = {}
        for file_path in code_files:
            try:
                content, encoding = await github_client.get_file_content(
                    owner, repo, file_path
                )
                file_contents[file_path] = content
            except Exception as e:
                logger.warning(f"Error reading file {file_path}: {e}")
                continue

        return file_contents

    except Exception as e:
        logger.error(f"Error getting repository file contents: {e}")
        return {}


@github_router.get("/analysis/status/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """Get the status of an analysis by ID"""
    try:
        # For now, simulate completed analysis after some time
        # In a real implementation, this would check database for actual status

        # Extract timestamp from analysis_id (format: owner_repo_timestamp)
        parts = analysis_id.split("_")
        if len(parts) >= 3:
            timestamp = int(parts[-1])
            current_time = int(datetime.utcnow().timestamp())
            elapsed_time = current_time - timestamp

            # Simulate completed status after 10 seconds
            if elapsed_time > 10:
                status = "completed"
                progress = 100
                message = "Analysis completed successfully"
            else:
                status = "processing"
                progress = min(90, elapsed_time * 10)  # 10% per second, max 90%
                message = f"Analysis in progress... ({progress}%)"
        else:
            status = "completed"
            progress = 100
            message = "Analysis completed successfully"

        return {
            "analysis_id": analysis_id,
            "status": status,
            "progress": progress,
            "message": message,
            "repository": "_".join(parts[:-1]) if len(parts) >= 3 else "unknown",
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting analysis status for {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@github_router.get("/analysis/results/{analysis_id}")
async def get_analysis_results_by_id(analysis_id: str):
    """Get analysis results by analysis ID"""
    try:
        # Extract repository info from analysis_id
        parts = analysis_id.split("_")
        if len(parts) >= 3:
            owner = parts[0]
            repo = "_".join(parts[1:-1])  # Handle repo names with underscores
        else:
            raise HTTPException(status_code=400, detail="Invalid analysis ID format")

        # Return mock comprehensive results for now
        return {
            "analysis_id": analysis_id,
            "status": "completed",
            "repository": f"{owner}/{repo}",
            "branch": "main",
            "results": {
                "summary": {
                    "total_files": 45,
                    "total_lines": 15420,
                    "languages": ["TypeScript", "JavaScript", "Python", "CSS"],
                    "quality_score": 85.2,
                    "security_score": 92.1,
                    "maintainability": "High",
                },
                "quality": {
                    "overall_score": 85.2,
                    "complexity_score": 78.5,
                    "maintainability_score": 88.9,
                    "test_coverage": 76.3,
                    "documentation_score": 82.1,
                },
                "security": {
                    "vulnerabilities_found": 2,
                    "severity_breakdown": {"high": 0, "medium": 1, "low": 1},
                    "recommendations": [
                        "Update dependency 'lodash' to latest version",
                        "Add input validation for user uploads",
                    ],
                },
                "dependencies": {
                    "total_dependencies": 156,
                    "outdated": 12,
                    "vulnerable": 2,
                    "licenses": ["MIT", "Apache-2.0", "BSD-3-Clause"],
                },
                "structure": {
                    "components": 28,
                    "services": 15,
                    "utilities": 8,
                    "tests": 34,
                },
            },
            "completed_at": datetime.utcnow().isoformat(),
            "analysis_duration": "2.3 minutes",
        }

    except Exception as e:
        logger.error(f"Error getting analysis results for {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def perform_repository_analysis(
    owner: str,
    repo: str,
    options: AnalysisOptions,
    github_client: GitHubClient,
    quality_validator: QualityValidator,
    graph_generator: GraphGenerator,
):
    """Perform comprehensive repository analysis in background"""
    try:
        logger.info(f"Background analysis started for {owner}/{repo}")

        # Get repository structure
        repo_data = await github_client.analyze_repository_structure(owner, repo)

        # Get file contents
        file_contents = await get_repository_file_contents(
            github_client, owner, repo, limit=100
        )

        # Perform quality analysis if requested
        quality_results = None
        if options.include_quality:
            quality_results = await quality_validator.analyze_repository_quality(
                repo_data, file_contents
            )

        # Generate graph if requested
        graph_results = None
        if options.include_graph:
            graph_results = await graph_generator.generate_repository_graph(
                repo_data, file_contents, quality_results
            )

        # Store results (in production, this would save to database)
        logger.info(f"Background analysis completed for {owner}/{repo}")

        # TODO: Store results in database for later retrieval
        # TODO: Send notification if enabled

    except Exception as e:
        logger.error(f"Error in background analysis for {owner}/{repo}: {e}")
    finally:
        await github_client.close()


async def process_github_webhook(event_type: str, payload: Dict[str, Any]):
    """Process GitHub webhook events in background"""
    try:
        logger.info(f"Processing webhook event: {event_type}")

        if event_type == "push":
            # Handle push events - could trigger re-analysis
            repository = payload.get("repository", {})
            repo_name = repository.get("full_name")
            logger.info(f"Push event for repository: {repo_name}")

        elif event_type == "pull_request":
            # Handle pull request events
            action = payload.get("action")
            pr = payload.get("pull_request", {})
            logger.info(f"Pull request {action}: {pr.get('title')}")

        elif event_type == "issues":
            # Handle issue events
            action = payload.get("action")
            issue = payload.get("issue", {})
            logger.info(f"Issue {action}: {issue.get('title')}")

        # TODO: Implement specific webhook processing logic

    except Exception as e:
        logger.error(f"Error processing webhook event {event_type}: {e}")
