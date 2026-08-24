"""
CodeTrace AI - Graph Generation API Routes
Handles traceability graph and visualization endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Import required modules for GitHub integration
try:
    from github.client import GitHubClient
    from graph.generator import GraphGenerator

    GITHUB_INTEGRATION_AVAILABLE = True
except ImportError:
    GITHUB_INTEGRATION_AVAILABLE = False

logger = logging.getLogger(__name__)

graph_router = APIRouter(tags=["Graph Analysis"])


class Node(BaseModel):
    """Graph node model"""

    id: str
    label: str
    type: str  # file, function, class, module
    properties: Dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    """Graph edge model"""

    source: str
    target: str
    type: str  # depends_on, calls, imports, inherits
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphData(BaseModel):
    """Complete graph data model"""

    nodes: List[Node]
    edges: List[Edge]
    metadata: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Standard error payload exposed in the OpenAPI schema."""

    detail: str = Field(..., description="Human-readable error description")


class GraphGenerationRequest(BaseModel):
    """Request model specifically for frontend compatibility"""

    repository_url: str = Field(
        ...,
        min_length=1,
        description="HTTPS GitHub repository URL to analyze",
        examples=["https://github.com/openai/codex"],
    )
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional options"
    )


class GraphRequest(BaseModel):
    """Request model for graph generation"""

    repository: str = Field(..., description="Repository to analyze")
    graph_type: str = Field(
        default="dependency", description="Type of graph to generate"
    )
    depth: int = Field(default=3, description="Maximum depth for traversal")
    include_external: bool = Field(
        default=False, description="Include external dependencies"
    )


class LocalSourceFile(BaseModel):
    path: str = Field(..., min_length=1, description="Relative source path")
    content: str = Field(..., description="UTF-8 source contents")


class LocalGraphRequest(BaseModel):
    files: List[LocalSourceFile] = Field(..., min_length=1, description="Source files to scan")
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional file extensions, such as .py or .ts",
        examples=[[".py", ".ts"]],
    )


@graph_router.post(
    "/local",
    response_model=GraphData,
    status_code=status.HTTP_200_OK,
    summary="Build a graph from local source files",
    operation_id="buildLocalGraph",
    responses={500: {"model": ErrorResponse, "description": "Graph generation failed"}},
)
async def generate_local_graph(request: LocalGraphRequest):
    """Build a graph from source files selected in the browser."""
    try:
        from graph.codegraph_integration import CodeGraph
        from codegraph_core import ScanConfig

        extensions = set(request.extensions or []) or None
        graph = CodeGraph(ScanConfig(extensions=extensions))
        summary = graph.scan_sources([item.model_dump() for item in request.files])
        nodes = [
            {"id": node_id, "label": node.attrs.get("name", node_id), "type": node.type,
             "properties": node.attrs}
            for node_id, node in graph.g.nodes.items()
        ]
        edges = [
            {"source": source, "target": target, "type": edge_type, "properties": attrs}
            for source, outgoing in graph.g.edges.items()
            for target, edge_type, attrs in outgoing
        ]
        return {"nodes": nodes, "edges": edges,
                "metadata": {**summary, "source": "local_folder", "graph_type": "dependency"}}
    except Exception as exc:
        logger.exception("Failed to generate local graph")
        raise HTTPException(status_code=500, detail=f"Local graph generation failed: {exc}") from exc


@graph_router.post(
    "/dependency",
    response_model=GraphData,
    status_code=status.HTTP_200_OK,
    summary="Build a dependency graph from a GitHub repository",
    operation_id="buildDependencyGraph",
    responses={400: {"model": ErrorResponse, "description": "Invalid repository URL"}, 500: {"model": ErrorResponse, "description": "Graph generation failed"}},
)
async def generate_dependency_graph(request: GraphGenerationRequest):
    """Generate a dependency graph for a repository"""
    try:
        logger.info(f"=== DEPENDENCY GRAPH REQUEST ===")
        logger.info(f"Request received: {request}")
        logger.info(f"Repository URL: {request.repository_url}")

        # Parse repository URL with comprehensive GitHub URL support
        repository_url = request.repository_url.strip()
        owner = None
        repo = None
        branch = None
        path = None

        logger.info(f"Processing URL: {repository_url}")

        if repository_url.startswith("https://github.com/"):
            # Remove the base URL
            url_path = repository_url.replace("https://github.com/", "").strip("/")
            path_parts = url_path.split("/")

            logger.info(f"URL path parts: {path_parts}")

            if len(path_parts) >= 2:
                owner = path_parts[0]
                repo = path_parts[1]

                # Check if URL contains branch or tree information
                if len(path_parts) > 2:
                    if path_parts[2] == "tree" and len(path_parts) > 3:
                        # Format: owner/repo/tree/branch_name
                        branch = path_parts[3]
                        if len(path_parts) > 4:
                            # Format: owner/repo/tree/branch_name/path/to/folder
                            path = "/".join(path_parts[4:])
                    elif path_parts[2] == "blob" and len(path_parts) > 4:
                        # Format: owner/repo/blob/branch_name/path/to/file
                        branch = path_parts[3]
                        path = "/".join(path_parts[4:])
                    else:
                        # Other GitHub URL formats
                        branch = "main"  # Default branch
                else:
                    branch = "main"  # Default branch

                repository = f"{owner}/{repo}"
            else:
                raise HTTPException(status_code=400, detail="Invalid GitHub URL format")
        else:
            raise HTTPException(
                status_code=400, detail="Only GitHub repositories are supported"
            )

        logger.info(
            f"Generating dependency graph for repository: {repository}, branch: {branch}, path: {path}"
        )

        # If GitHub integration is available, try to use real data
        if GITHUB_INTEGRATION_AVAILABLE:
            try:
                github_client = GitHubClient()
                await github_client.init_session()

                # Get repository info to verify access
                repo_info = await github_client.get_repository(owner, repo)

                # Get repository structure for the specific branch
                repo_data = await github_client.analyze_repository_structure(
                    owner, repo, branch=branch
                )

                # Generate real dependency graph based on repository structure
                nodes = []
                edges = []

                # Create nodes from repository structure
                if "structure" in repo_data:
                    files = repo_data["structure"].get("files", [])

                    # Filter files by path if specified
                    if path:
                        files = [f for f in files if f.get("path", "").startswith(path)]

                    # Limit to code files and reasonable number for visualization
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
                        ".json",
                        ".yaml",
                        ".yml",
                        ".md",
                    }

                    for file_info in files[
                        :50
                    ]:  # Limit to first 50 files for performance
                        file_path = file_info.get("path", "")
                        file_ext = (
                            file_path[file_path.rfind(".") :].lower()
                            if "." in file_path
                            else ""
                        )

                        if file_ext in code_extensions:
                            nodes.append(
                                Node(
                                    id=file_path,
                                    label=file_path.split("/")[-1],
                                    type="file",
                                    properties={
                                        "path": file_path,
                                        "size": file_info.get("size", 0),
                                        "repository": repository,
                                        "branch": branch,
                                        "extension": file_ext,
                                        "full_path": f"{repository}/{file_path}",
                                    },
                                )
                            )

                # Create edges based on file relationships
                for i, node in enumerate(nodes):
                    node_path = node.properties.get("path", "")
                    node_dir = "/".join(node_path.split("/")[:-1])

                    # Connect files in the same directory
                    for j, other_node in enumerate(nodes):
                        if i != j:
                            other_path = other_node.properties.get("path", "")
                            other_dir = "/".join(other_path.split("/")[:-1])

                            # Files in same directory have weak connection
                            if node_dir == other_dir and node_dir:
                                edges.append(
                                    Edge(
                                        source=node.id,
                                        target=other_node.id,
                                        type="same_directory",
                                        properties={
                                            "relationship": "directory_proximity",
                                            "weight": 0.3,
                                        },
                                    )
                                )

                            # Check for potential import relationships based on file names
                            elif node_path.endswith(
                                (".py", ".js", ".ts")
                            ) and other_path.endswith((".py", ".js", ".ts")):
                                # Simple heuristic for imports
                                if (
                                    other_node.label.replace(
                                        other_node.properties.get("extension", ""), ""
                                    )
                                    in node.label
                                ):
                                    edges.append(
                                        Edge(
                                            source=node.id,
                                            target=other_node.id,
                                            type="potential_import",
                                            properties={
                                                "relationship": "likely_dependency",
                                                "weight": 0.7,
                                            },
                                        )
                                    )

                await github_client.close()

                metadata = {
                    "repository": repository,
                    "repository_url": repository_url,
                    "branch": branch,
                    "path": path,
                    "graph_type": "dependency",
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "generated_at": datetime.utcnow().isoformat(),
                    "data_source": "github_api",
                    "success": True,
                }

            except Exception as github_error:
                logger.warning(f"GitHub API failed, using mock data: {github_error}")
                # Fall back to mock data
                nodes, edges, metadata = generate_mock_graph_data(
                    repository, repository_url, branch, path
                )
        else:
            # Use mock data if GitHub integration not available
            nodes, edges, metadata = generate_mock_graph_data(
                repository, repository_url, branch, path
            )

        return GraphData(nodes=nodes, edges=edges, metadata=metadata)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating dependency graph: {e}")
        raise HTTPException(
            status_code=500, detail=f"Graph generation failed: {str(e)}"
        )


def generate_mock_graph_data(
    repository: str, repository_url: str, branch: str = None, path: str = None
):
    """Generate mock graph data for demonstration"""

    # Create mock nodes based on common file patterns
    base_files = ["main.py", "utils.py", "config.py", "requirements.txt", "README.md"]

    if path:
        # If path is specified, create files within that path
        base_files = [f"{path}/{file}" for file in base_files]

    nodes = []
    for file_path in base_files:
        file_name = file_path.split("/")[-1]
        file_ext = file_name[file_name.rfind(".") :].lower() if "." in file_name else ""

        nodes.append(
            Node(
                id=file_path,
                label=file_name,
                type="file",
                properties={
                    "path": file_path,
                    "repository": repository,
                    "branch": branch or "main",
                    "extension": file_ext,
                    "lines": 100 + len(file_name) * 5,  # Mock line count
                    "full_path": f"{repository}/{file_path}",
                },
            )
        )

    # Add some directory-specific files if analyzing a specific path
    if path and "src" in path.lower():
        src_files = ["app.py", "models.py", "views.py"]
        for file_name in src_files:
            file_path = f"{path}/{file_name}"
            nodes.append(
                Node(
                    id=file_path,
                    label=file_name,
                    type="file",
                    properties={
                        "path": file_path,
                        "repository": repository,
                        "branch": branch or "main",
                        "extension": ".py",
                        "lines": 150,
                        "full_path": f"{repository}/{file_path}",
                    },
                )
            )

    edges = []
    # Create connections between files
    for i, node in enumerate(nodes[:-1]):
        if i < len(nodes) - 1:
            edges.append(
                Edge(
                    source=node.id,
                    target=nodes[i + 1].id,
                    type="imports",
                    properties={"relationship": "dependency", "weight": 0.5},
                )
            )

    metadata = {
        "repository": repository,
        "repository_url": repository_url,
        "branch": branch or "main",
        "path": path,
        "graph_type": "dependency",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "generated_at": datetime.utcnow().isoformat(),
        "data_source": "mock_data",
        "success": True,
    }

    return nodes, edges, metadata


@graph_router.post("/generate", response_model=GraphData)
async def generate_graph(request: GraphRequest):
    """Generate a traceability graph for a repository"""
    try:
        # Mock graph generation for now
        nodes = [
            Node(
                id="main.py",
                label="main.py",
                type="file",
                properties={"lines": 150, "functions": 5},
            ),
            Node(
                id="utils.py",
                label="utils.py",
                type="file",
                properties={"lines": 80, "functions": 8},
            ),
            Node(
                id="config.py",
                label="config.py",
                type="file",
                properties={"lines": 45, "functions": 2},
            ),
            Node(
                id="main.main_function",
                label="main_function",
                type="function",
                properties={"complexity": 3, "lines": 25},
            ),
            Node(
                id="utils.helper_function",
                label="helper_function",
                type="function",
                properties={"complexity": 2, "lines": 15},
            ),
        ]

        edges = [
            Edge(
                source="main.py",
                target="utils.py",
                type="imports",
                properties={"import_type": "from_import"},
            ),
            Edge(
                source="main.py",
                target="config.py",
                type="imports",
                properties={"import_type": "import"},
            ),
            Edge(
                source="main.main_function",
                target="utils.helper_function",
                type="calls",
                properties={"call_count": 3},
            ),
        ]

        metadata = {
            "repository": request.repository,
            "graph_type": request.graph_type,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "generated_at": datetime.utcnow().isoformat(),
            "max_depth": request.depth,
            "includes_external": request.include_external,
        }

        return GraphData(nodes=nodes, edges=edges, metadata=metadata)
    except Exception as e:
        logger.error(f"Error generating graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.post("/test-integration")
async def test_complete_integration(request: GraphGenerationRequest):
    """Comprehensive test of the entire GitHub integration pipeline"""
    try:
        logger.info(f"=== COMPREHENSIVE INTEGRATION TEST ===")
        logger.info(f"Request: {request}")

        # Step 1: Check GitHub token
        from core.config import settings

        github_token_status = "✅ Configured" if settings.GITHUB_TOKEN else "❌ Missing"
        logger.info(f"GitHub Token: {github_token_status}")

        # Step 2: Parse URL
        repository_url = request.repository_url.strip()
        logger.info(f"Repository URL: {repository_url}")

        # Step 3: Validate URL format
        if not repository_url.startswith("https://github.com/"):
            return {
                "success": False,
                "error": "URL must start with https://github.com/",
                "validation_details": {
                    "received_url": repository_url,
                    "expected_format": "https://github.com/owner/repo",
                    "github_token": github_token_status,
                },
            }

        # Step 4: Parse URL components
        url_path = repository_url.replace("https://github.com/", "").strip("/")
        path_parts = url_path.split("/")
        logger.info(f"URL parts: {path_parts}")

        if len(path_parts) < 2:
            return {
                "success": False,
                "error": "URL must contain owner and repository name",
                "validation_details": {
                    "received_parts": path_parts,
                    "minimum_required": ["owner", "repo"],
                    "github_token": github_token_status,
                },
            }

        owner = path_parts[0]
        repo = path_parts[1]
        branch = "main"
        path = None

        # Handle branch/path parsing
        if len(path_parts) > 2:
            if path_parts[2] == "tree" and len(path_parts) > 3:
                branch = path_parts[3]
                if len(path_parts) > 4:
                    path = "/".join(path_parts[4:])

        parsed_components = {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "path": path,
            "full_repo": f"{owner}/{repo}",
        }
        logger.info(f"Parsed components: {parsed_components}")

        # Step 5: Test GitHub client initialization
        github_client_status = "❌ Failed"
        github_error = None

        if GITHUB_INTEGRATION_AVAILABLE:
            try:
                github_client = GitHubClient()
                await github_client.init_session()
                github_client_status = "✅ Initialized"

                # Step 6: Test GitHub API access
                try:
                    repo_info = await github_client.get_repository(owner, repo)
                    github_client_status = "✅ API Access Working"
                    await github_client.close()
                except Exception as api_error:
                    github_error = str(api_error)
                    github_client_status = f"❌ API Error: {github_error}"
                    try:
                        await github_client.close()
                    except:
                        pass

            except Exception as client_error:
                github_error = str(client_error)
                github_client_status = f"❌ Client Error: {github_error}"
        else:
            github_client_status = "❌ GitHub integration not available"

        # Step 7: Generate response
        test_results = {
            "success": True,
            "test_results": {
                "1_url_parsing": "✅ Success",
                "2_component_extraction": "✅ Success",
                "3_github_token": github_token_status,
                "4_github_client": github_client_status,
                "5_integration_available": (
                    "✅ Available"
                    if GITHUB_INTEGRATION_AVAILABLE
                    else "❌ Not Available"
                ),
            },
            "parsed_data": parsed_components,
            "received_url": repository_url,
            "error_details": github_error,
            "recommendations": [],
        }

        # Add recommendations based on results
        if not settings.GITHUB_TOKEN:
            test_results["recommendations"].append(
                "Configure GITHUB_TOKEN in .env file"
            )

        if github_error:
            if "404" in str(github_error):
                test_results["recommendations"].append(
                    "Repository not found or private - check repository URL and token permissions"
                )
            elif "403" in str(github_error):
                test_results["recommendations"].append(
                    "Access forbidden - check token permissions"
                )
            else:
                test_results["recommendations"].append(
                    f"GitHub API error: {github_error}"
                )

        if not GITHUB_INTEGRATION_AVAILABLE:
            test_results["recommendations"].append(
                "GitHub client modules not properly imported"
            )

        logger.info(f"Test results: {test_results}")

        return test_results

    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return {
            "success": False,
            "error": f"Integration test failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
        }


@graph_router.post("/debug-request")
async def debug_frontend_request(request_data: dict = None, **kwargs):
    """Debug endpoint to see exactly what the frontend is sending"""
    try:
        logger.info(f"=== DEBUG REQUEST RECEIVED ===")
        logger.info(f"Request data: {request_data}")
        logger.info(f"Kwargs: {kwargs}")

        return {
            "success": True,
            "message": "Request received successfully",
            "received_data": request_data,
            "received_kwargs": kwargs,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@graph_router.post("/test-endpoint")
async def test_frontend_request(request_data: dict):
    """Test endpoint to see what the frontend is sending"""
    try:
        logger.info(f"Frontend sent: {request_data}")
        return {
            "message": "Request received successfully",
            "received_data": request_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.post("/parse-url")
async def parse_repository_url(request: GraphGenerationRequest):
    """Parse and validate a GitHub repository URL to show extracted components"""
    try:
        repository_url = request.repository_url.strip()
        owner = None
        repo = None
        branch = None
        path = None

        if repository_url.startswith("https://github.com/"):
            # Remove the base URL
            url_path = repository_url.replace("https://github.com/", "").strip("/")
            path_parts = url_path.split("/")

            if len(path_parts) >= 2:
                owner = path_parts[0]
                repo = path_parts[1]

                # Check if URL contains branch or tree information
                if len(path_parts) > 2:
                    if path_parts[2] == "tree" and len(path_parts) > 3:
                        # Format: owner/repo/tree/branch_name
                        branch = path_parts[3]
                        if len(path_parts) > 4:
                            # Format: owner/repo/tree/branch_name/path/to/folder
                            path = "/".join(path_parts[4:])
                    elif path_parts[2] == "blob" and len(path_parts) > 4:
                        # Format: owner/repo/blob/branch_name/path/to/file
                        branch = path_parts[3]
                        path = "/".join(path_parts[4:])
                    else:
                        # Other GitHub URL formats
                        branch = "main"  # Default branch
                else:
                    branch = "main"  # Default branch

                repository = f"{owner}/{repo}"
            else:
                raise HTTPException(status_code=400, detail="Invalid GitHub URL format")
        else:
            raise HTTPException(
                status_code=400, detail="Only GitHub repositories are supported"
            )

        return {
            "original_url": repository_url,
            "parsed_components": {
                "owner": owner,
                "repository": repo,
                "full_repository": repository,
                "branch": branch,
                "path": path,
            },
            "github_api_calls": {
                "repository_info": f"GET /repos/{owner}/{repo}",
                "branch_tree": f"GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
                "file_content": f"GET /repos/{owner}/{repo}/contents/{{file_path}}?ref={branch}",
            },
            "status": "valid",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing repository URL: {e}")
        raise HTTPException(status_code=500, detail=f"URL parsing failed: {str(e)}")


@graph_router.get("/types")
async def get_graph_types():
    """Get available graph types"""
    try:
        return {
            "graph_types": [
                {
                    "id": "dependency",
                    "name": "Dependency Graph",
                    "description": "Shows dependencies between files and modules",
                },
                {
                    "id": "call_graph",
                    "name": "Call Graph",
                    "description": "Shows function call relationships",
                },
                {
                    "id": "class_hierarchy",
                    "name": "Class Hierarchy",
                    "description": "Shows inheritance relationships",
                },
                {
                    "id": "module_structure",
                    "name": "Module Structure",
                    "description": "Shows project structure and organization",
                },
                {
                    "id": "data_flow",
                    "name": "Data Flow",
                    "description": "Shows data flow through the application",
                },
            ]
        }
    except Exception as e:
        logger.error(f"Error getting graph types: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.get("/metrics/{repository:path}")
async def get_graph_metrics(repository: str):
    """Get graph-based metrics for a repository"""
    try:
        return {
            "repository": repository,
            "metrics": {
                "modularity": 0.75,
                "coupling": 0.35,
                "cohesion": 0.82,
                "complexity": 15.2,
                "fan_in": {"max": 8, "avg": 3.2},
                "fan_out": {"max": 12, "avg": 4.1},
                "circular_dependencies": 2,
                "dead_code_files": 3,
            },
            "hotspots": [
                {"file": "main.py", "connections": 15, "type": "high_coupling"},
                {"file": "utils.py", "connections": 12, "type": "utility_hub"},
                {"file": "deprecated.py", "connections": 0, "type": "dead_code"},
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting graph metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.get("/visualization/{repository:path}")
async def get_graph_visualization(
    repository: str, graph_type: str = "dependency", format: str = "json"
):
    """Get graph visualization data"""
    try:
        if format == "d3":
            # D3.js compatible format
            return {
                "nodes": [
                    {"id": "main.py", "group": 1, "size": 150},
                    {"id": "utils.py", "group": 2, "size": 80},
                    {"id": "config.py", "group": 3, "size": 45},
                ],
                "links": [
                    {"source": "main.py", "target": "utils.py", "value": 1},
                    {"source": "main.py", "target": "config.py", "value": 1},
                ],
            }
        elif format == "cytoscape":
            # Cytoscape.js compatible format
            return {
                "elements": [
                    {"data": {"id": "main.py", "label": "main.py"}},
                    {"data": {"id": "utils.py", "label": "utils.py"}},
                    {"data": {"id": "config.py", "label": "config.py"}},
                    {"data": {"source": "main.py", "target": "utils.py"}},
                    {"data": {"source": "main.py", "target": "config.py"}},
                ]
            }
        else:
            # Default JSON format
            return {
                "repository": repository,
                "graph_type": graph_type,
                "format": format,
                "visualization_data": "Generated visualization data would be here",
                "generated_at": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error getting graph visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@graph_router.get("/enhanced-traceability")
async def get_enhanced_traceability_graph():
    """Get the enhanced traceability graph from e2etrace analysis"""
    try:
        import json
        import os

        # Path to the enhanced traceability graph data
        graph_data_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "analysis",
            "ENHANCED_TRACEABILITY_GRAPH",
            "hierarchical-graph-data.json",
        )

        if os.path.exists(graph_data_path):
            with open(graph_data_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)

            return {
                "success": True,
                "graph_data": graph_data,
                "source": "enhanced_traceability_analysis",
                "description": "GraphTrace Enhanced Hierarchical Traceability with Impact Analysis",
                "generated_at": datetime.utcnow().isoformat(),
            }
        else:
            return {
                "success": False,
                "error": "Enhanced traceability graph data not found",
                "expected_path": graph_data_path,
                "generated_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Error loading enhanced traceability graph: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load enhanced traceability graph: {str(e)}",
        )


@graph_router.post("/analyze/complexity")
async def analyze_complexity():
    """Analyze code complexity using graph metrics"""
    try:
        return {
            "complexity_analysis": {
                "overall_complexity": "medium",
                "complex_modules": [
                    {"module": "main.py", "complexity": 8.5, "reason": "high_coupling"},
                    {
                        "module": "processor.py",
                        "complexity": 9.2,
                        "reason": "cyclomatic_complexity",
                    },
                ],
                "recommendations": [
                    "Consider breaking down large functions in main.py",
                    "Reduce coupling between core modules",
                    "Extract utility functions to separate modules",
                ],
            }
        }
    except Exception as e:
        logger.error(f"Error analyzing complexity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_repository_file_contents_with_branch(
    github_client,
    owner: str,
    repo: str,
    branch: str = "main",
    path: str = None,
    limit: int = 50,
):
    """Get file contents from repository with branch and path support"""
    try:
        # Get repository tree for the specific branch
        tree = await github_client.get_repository_tree(
            owner, repo, recursive=True, sha=branch
        )
        files = tree.get("tree", [])

        # Filter for code files and apply path filter if specified
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
            ".json",
            ".yaml",
            ".yml",
        }

        for file_info in files:
            if file_info["type"] == "blob":  # Regular file
                file_path = file_info["path"]

                # Apply path filter if specified
                if path and not file_path.startswith(path):
                    continue

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
                    owner, repo, file_path, ref=branch
                )
                file_contents[file_path] = content
            except Exception as e:
                logger.warning(
                    f"Error reading file {file_path} from branch {branch}: {e}"
                )
                continue

        return file_contents

    except Exception as e:
        logger.error(f"Error getting repository file contents: {e}")
        return {}
