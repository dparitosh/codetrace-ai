"""
Model Context Protocol (MCP) Server Implementation
Main server class for handling MCP requests and responses
"""

import json
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, Set
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from .protocol import (
    MCPRequest, MCPServerInfo, MCPClientInfo,
    MCPMethods, MCPCapability, MCPResource, MCPTool, MCPPrompt,
    CodeContextRequest
)
from .handlers import CodeContextHandler, RepositoryHandler, QualityHandler

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Thread-safe WebSocket connection manager"""
    
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    @property
    def lock(self):
        """Access to the async lock for external coordination"""
        return self._lock
    
    async def add_connection(self, websocket: WebSocket) -> str:
        """Add a WebSocket connection"""
        connection_id = str(uuid.uuid4())
        async with self._lock:
            self.connections.add(websocket)
        logger.info("🔌 WebSocket connection added: %s", connection_id)
        return connection_id
    
    async def remove_connection(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            self.connections.discard(websocket)  # Safe removal
        logger.info("🔌 WebSocket connection removed")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connections"""
        if not self.connections:
            return
        
        # Get a copy of connections to avoid modification during iteration
        async with self._lock:
            connections_copy = self.connections.copy()
        
        dead_connections = []
        for websocket in connections_copy:
            try:
                await websocket.send_json(message)
            except ConnectionResetError as e:
                logger.warning("Connection reset while sending message: %s", str(e))
                dead_connections.append(websocket)
            except Exception as e:
                logger.warning("Failed to send to connection: %s", str(e))
                dead_connections.append(websocket)
        
        # Remove dead connections
        if dead_connections:
            async with self._lock:
                for websocket in dead_connections:
                    self.connections.discard(websocket)

class MCPServer:
    """Model Context Protocol Server for CodeTrace AI"""
    
    def __init__(self):
        self.capabilities = [
            MCPCapability.RESOURCES,
            MCPCapability.TOOLS,
            MCPCapability.PROMPTS,
            MCPCapability.LOGGING
        ]
        
        self.server_info = MCPServerInfo(
            name="CodeTrace AI MCP Server",
            version="1.0.0",
            description="Provides code context and analysis capabilities",
            capabilities=self.capabilities
        )
        
        self.client_info: Optional[MCPClientInfo] = None
        self.is_initialized = False
        
        # Request handlers
        self.handlers: Dict[str, Callable] = {}
        self._register_handlers()
        
        # Component handlers
        self.code_handler = CodeContextHandler()
        self.repo_handler = RepositoryHandler()
        self.quality_handler = QualityHandler()
        
        # Connection manager for WebSocket connections
        self.connection_manager = ConnectionManager()
        
        logger.info("🚀 MCP Server initialized")
    
    def _register_handlers(self):
        """Register MCP method handlers"""
        self.handlers.update({
            # Server lifecycle
            MCPMethods.INITIALIZE: self._handle_initialize,
            MCPMethods.INITIALIZED: self._handle_initialized,
            MCPMethods.SHUTDOWN: self._handle_shutdown,
            
            # Resources
            MCPMethods.LIST_RESOURCES: self._handle_list_resources,
            MCPMethods.LIST_RESOURCE_TEMPLATES: self._handle_list_resource_templates,
            MCPMethods.READ_RESOURCE: self._handle_read_resource,
            MCPMethods.SUBSCRIBE_RESOURCE: self._handle_subscribe_resource,
            MCPMethods.UNSUBSCRIBE_RESOURCE: self._handle_unsubscribe_resource,
            
            # Tools
            MCPMethods.LIST_TOOLS: self._handle_list_tools,
            MCPMethods.CALL_TOOL: self._handle_call_tool,
            
            # Prompts
            MCPMethods.LIST_PROMPTS: self._handle_list_prompts,
            MCPMethods.GET_PROMPT: self._handle_get_prompt,
            
            # Logging
            MCPMethods.SET_LOG_LEVEL: self._handle_set_log_level,
            
            # CodeTrace-specific methods
            MCPMethods.GET_CODE_CONTEXT: self._handle_get_code_context,
            MCPMethods.ANALYZE_REPOSITORY: self._handle_analyze_repository,
            MCPMethods.GET_QUALITY_METRICS: self._handle_get_quality_metrics,
            MCPMethods.GET_DEPENDENCY_GRAPH: self._handle_get_dependency_graph,
            MCPMethods.SEARCH_CODE: self._handle_search_code,
        })
    
    def _create_error_response(self, request_id: Optional[str], error_code: int, error_message: str) -> Dict[str, Any]:
        """Create standardized MCP error response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": error_code,
                "message": error_message,
                "data": None
            }
        }
    
    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming MCP request"""
        try:
            # Parse request
            request = MCPRequest(**request_data)
            
            # Check if server is initialized for non-lifecycle methods
            if (request.method not in [MCPMethods.INITIALIZE, MCPMethods.INITIALIZED] 
                and not self.is_initialized):
                return self._create_error_response(
                    str(request.id) if request.id is not None else None,
                    -32002,
                    "Server not initialized"
                )
            
            # Find handler
            handler = self.handlers.get(request.method)
            if not handler:
                return self._create_error_response(
                    str(request.id) if request.id is not None else None,
                    -32601,
                    f"Method not found: {request.method}"
                )
            
            # Execute handler
            result = await handler(request.params or {})
            
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": result
            }
            
        except ValueError as e:
            logger.error("Request validation error: %s", str(e))
            return self._create_error_response(
                str(request_data.get("id")) if request_data.get("id") is not None else None,
                -32602,
                f"Invalid params: {str(e)}"
            )
        except Exception as e:
            logger.error("Error processing MCP request: %s", str(e))
            return self._create_error_response(
                str(request_data.get("id")) if request_data.get("id") is not None else None,
                -32603,
                f"Internal error: {str(e)}"
            )
    
    # Lifecycle handlers
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        try:
            client_info = MCPClientInfo(**params.get("clientInfo", {}))
            self.client_info = client_info
            
            logger.info("🤝 Client connected: %s v%s", client_info.name, client_info.version)
            
            return {
                "protocolVersion": "2025-06-18",
                "serverInfo": self.server_info.dict(),
                "capabilities": {
                    "resources": {
                        "subscribe": False,  # Not yet implemented
                        "listChanged": False  # Not yet implemented
                    },
                    "tools": {},
                    "prompts": {},
                    "logging": {
                        "setLevel": False  # Not yet implemented
                    }
                }
            }
        except Exception as e:
            logger.error("Initialize error: %s", str(e))
            raise
    
    async def _handle_initialized(self, _params: Dict[str, Any]) -> None:
        """Handle initialized notification"""
        self.is_initialized = True
        logger.info("✅ MCP Server fully initialized and ready")
        return None
    
    async def _handle_shutdown(self, _params: Dict[str, Any]) -> None:
        """Handle shutdown request with proper cleanup"""
        logger.info("� MCP Server shutting down...")
        self.is_initialized = False
        
        # Close all WebSocket connections safely
        if hasattr(self, 'connection_manager'):
            async with self.connection_manager.lock:
                connections_copy = self.connection_manager.connections.copy()
            
            for connection in connections_copy:
                try:
                    await connection.close()
                except ConnectionResetError as e:
                    logger.warning("Connection already closed during shutdown: %s", str(e))
                except Exception as e:
                    logger.warning("Error closing connection during shutdown: %s", str(e))
            
            # Clear all connections
            async with self.connection_manager.lock:
                self.connection_manager.connections.clear()
        
        logger.info("✅ MCP Server shutdown completed")
        return None
    
    # Resource handlers
    async def _handle_list_resources(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list resources request"""
        resources = [
            MCPResource(
                uri="codetrace://repository/{owner}/{repo}",
                name="Repository Analysis",
                description="Complete repository analysis and context",
                mime_type="application/json"
            ).dict(),
            MCPResource(
                uri="codetrace://file/{owner}/{repo}/{path}",
                name="File Content",
                description="Individual file content with context",
                mime_type="text/plain"
            ).dict(),
            MCPResource(
                uri="codetrace://function/{owner}/{repo}/{function}",
                name="Function Analysis",
                description="Function-specific analysis and context",
                mime_type="application/json"
            ).dict(),
            MCPResource(
                uri="codetrace://quality/{owner}/{repo}",
                name="Quality Metrics",
                description="Code quality assessment and metrics",
                mime_type="application/json"
            ).dict(),
            MCPResource(
                uri="codetrace://graph/{owner}/{repo}",
                name="Dependency Graph",
                description="Code dependency and traceability graph",
                mime_type="application/json"
            ).dict()
        ]
        
        return {"resources": resources}
    
    async def _handle_list_resource_templates(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list resource templates request"""
        # Resource templates are not yet implemented
        # TODO: Add support for parameterized resource URIs
        templates: list[dict] = []
        return {"resourceTemplates": templates}
    
    async def _handle_subscribe_resource(self, params: Dict[str, Any]) -> None:
        """Handle resource subscription request"""
        # Resource subscriptions are not yet implemented
        # TODO: Add WebSocket-based resource change notifications
        uri = params.get("uri", "")
        logger.info("Resource subscription requested for: %s", uri)
        return None
    
    async def _handle_unsubscribe_resource(self, params: Dict[str, Any]) -> None:
        """Handle resource unsubscription request"""
        # Resource subscriptions are not yet implemented
        # TODO: Remove WebSocket-based resource change notifications
        uri = params.get("uri", "")
        logger.info("Resource unsubscription requested for: %s", uri)
        return None
    
    async def _handle_read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle read resource request"""
        uri = params.get("uri", "")
        
        if uri.startswith("codetrace://repository/"):
            return await self.repo_handler.get_repository_context(uri)
        elif uri.startswith("codetrace://file/"):
            return await self.code_handler.get_file_context(uri)
        elif uri.startswith("codetrace://function/"):
            return await self.code_handler.get_function_context(uri)
        elif uri.startswith("codetrace://quality/"):
            return await self.quality_handler.get_quality_context(uri)
        elif uri.startswith("codetrace://graph/"):
            return await self.repo_handler.get_graph_context(uri)
        else:
            raise ValueError(f"Unknown resource URI: {uri}")
    
    # Tool handlers
    async def _handle_list_tools(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list tools request"""
        tools = [
            MCPTool(
                name="analyze_repository",
                description="Analyze a GitHub repository for code quality and structure",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repository_url": {
                            "type": "string",
                            "description": "GitHub repository URL"
                        },
                        "include_quality": {
                            "type": "boolean",
                            "description": "Include quality metrics",
                            "default": True
                        },
                        "include_dependencies": {
                            "type": "boolean", 
                            "description": "Include dependency analysis",
                            "default": True
                        }
                    },
                    "required": ["repository_url"]
                }
            ).dict(),
            MCPTool(
                name="search_code",
                description="Search for code patterns or symbols in a repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repository_url": {
                            "type": "string",
                            "description": "GitHub repository URL"
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "File pattern to search in"
                        }
                    },
                    "required": ["repository_url", "query"]
                }
            ).dict(),
            MCPTool(
                name="get_code_context",
                description="Get detailed context for specific code elements",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repository_url": {
                            "type": "string",
                            "description": "GitHub repository URL"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Specific file path"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Function name to analyze"
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": "Number of context lines",
                            "default": 10
                        }
                    },
                    "required": ["repository_url"]
                }
            ).dict()
        ]
        
        return {"tools": tools}
    
    async def _handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name == "analyze_repository":
            return await self._tool_analyze_repository(arguments)
        elif tool_name == "search_code":
            return await self._tool_search_code(arguments)
        elif tool_name == "get_code_context":
            return await self._tool_get_code_context(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    # Prompt handlers
    async def _handle_list_prompts(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list prompts request"""
        prompts = [
            MCPPrompt(
                name="code_review",
                description="Generate a comprehensive code review for a repository",
                arguments=[
                    {
                        "name": "repository_url",
                        "description": "GitHub repository URL",
                        "required": True
                    },
                    {
                        "name": "focus_areas", 
                        "description": "Areas to focus on (security, performance, maintainability)",
                        "required": False
                    }
                ]
            ).dict(),
            MCPPrompt(
                name="explain_code",
                description="Explain how a specific piece of code works",
                arguments=[
                    {
                        "name": "repository_url",
                        "description": "GitHub repository URL",
                        "required": True
                    },
                    {
                        "name": "file_path",
                        "description": "File path to explain",
                        "required": True
                    },
                    {
                        "name": "function_name",
                        "description": "Specific function to explain",
                        "required": False
                    }
                ]
            ).dict(),
            MCPPrompt(
                name="suggest_improvements",
                description="Suggest improvements for code quality and performance",
                arguments=[
                    {
                        "name": "repository_url",
                        "description": "GitHub repository URL", 
                        "required": True
                    }
                ]
            ).dict()
        ]
        
        return {"prompts": prompts}
    
    async def _handle_get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get prompt request"""
        prompt_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if prompt_name == "code_review":
            return await self._prompt_code_review(arguments)
        elif prompt_name == "explain_code":
            return await self._prompt_explain_code(arguments)
        elif prompt_name == "suggest_improvements":
            return await self._prompt_suggest_improvements(arguments)
        else:
            raise ValueError(f"Unknown prompt: {prompt_name}")
    
    # Logging handlers
    async def _handle_set_log_level(self, params: Dict[str, Any]) -> None:
        """Handle set log level request"""
        # Dynamic log level setting is not yet implemented  
        # TODO: Add runtime log level adjustment capability
        level = params.get("level", "info")
        logger.info("Log level change requested: %s", level)
        return None
    
    # CodeTrace-specific handlers
    async def _handle_get_code_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get code context request"""
        request = CodeContextRequest(**params)
        return await self.code_handler.get_code_context(request)
    
    async def _handle_analyze_repository(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analyze repository request"""
        return await self.repo_handler.analyze_repository(params)
    
    async def _handle_get_quality_metrics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get quality metrics request"""
        return await self.quality_handler.get_quality_metrics(params)
    
    async def _handle_get_dependency_graph(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get dependency graph request"""
        return await self.repo_handler.get_dependency_graph(params)
    
    async def _handle_search_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search code request"""
        return await self.code_handler.search_code(params)
    
    # Tool implementations
    async def _tool_analyze_repository(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze repository tool"""
        result = await self.repo_handler.analyze_repository(arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Repository analysis completed for {arguments.get('repository_url')}"
                },
                {
                    "type": "resource",
                    "resource": {
                        "uri": f"codetrace://repository/{arguments.get('repository_url')}",
                        "text": json.dumps(result, indent=2)
                    }
                }
            ]
        }
    
    async def _tool_search_code(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search code tool"""
        result = await self.code_handler.search_code(arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(result.get('matches', []))} matches for '{arguments.get('query')}'"
                },
                {
                    "type": "resource",
                    "resource": {
                        "uri": f"codetrace://search/{arguments.get('repository_url')}",
                        "text": json.dumps(result, indent=2)
                    }
                }
            ]
        }
    
    async def _tool_get_code_context(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get code context tool"""
        request = CodeContextRequest(**arguments)
        result = await self.code_handler.get_code_context(request)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Code context retrieved for {arguments.get('repository_url')}"
                },
                {
                    "type": "resource",
                    "resource": {
                        "uri": f"codetrace://context/{arguments.get('repository_url')}",
                        "text": json.dumps(result.dict(), indent=2)
                    }
                }
            ]
        }
    
    # Prompt implementations
    async def _prompt_code_review(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Code review prompt"""
        repo_url = arguments.get("repository_url")
        focus_areas = arguments.get("focus_areas", ["security", "performance", "maintainability"])
        
        # Get repository analysis
        analysis = await self.repo_handler.analyze_repository({"repository_url": repo_url})
        quality = await self.quality_handler.get_quality_metrics({"repository_url": repo_url})
        
        prompt_text = f"""Please conduct a comprehensive code review for the repository: {repo_url}

Focus Areas: {', '.join(focus_areas)}

Repository Analysis:
{json.dumps(analysis, indent=2)}

Quality Metrics:
{json.dumps(quality, indent=2)}

Please provide:
1. Overall assessment of code quality
2. Specific issues found in each focus area
3. Recommendations for improvement
4. Priority ranking of suggested changes
"""
        
        return {
            "description": f"Code review prompt for {repo_url}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt_text
                    }
                }
            ]
        }
    
    async def _prompt_explain_code(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Explain code prompt"""
        repo_url = arguments.get("repository_url", "")
        if not repo_url:
            raise ValueError("repository_url is required")
            
        file_path = arguments.get("file_path")
        function_name = arguments.get("function_name")
        
        # Get code context
        context_request = CodeContextRequest(
            repository_url=repo_url,
            file_path=file_path,
            function_name=function_name
        )
        context = await self.code_handler.get_code_context(context_request)
        
        prompt_text = f"""Please explain how this code works:

Repository: {repo_url}
File: {file_path}
{"Function: " + function_name if function_name else ""}

Code Context:
{json.dumps(context.dict(), indent=2)}

Please provide:
1. High-level overview of what the code does
2. Step-by-step explanation of the logic
3. Key algorithms or patterns used
4. Dependencies and interactions with other components
5. Potential edge cases or considerations
"""
        
        return {
            "description": f"Code explanation for {file_path}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt_text
                    }
                }
            ]
        }
    
    async def _prompt_suggest_improvements(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest improvements prompt"""
        repo_url = arguments.get("repository_url")
        
        # Get comprehensive analysis
        analysis = await self.repo_handler.analyze_repository({"repository_url": repo_url})
        quality = await self.quality_handler.get_quality_metrics({"repository_url": repo_url})
        
        prompt_text = f"""Please suggest improvements for this codebase: {repo_url}

Current Analysis:
{json.dumps(analysis, indent=2)}

Quality Assessment:
{json.dumps(quality, indent=2)}

Please provide specific, actionable suggestions for:
1. Code quality improvements
2. Performance optimizations  
3. Security enhancements
4. Maintainability improvements
5. Architecture refinements
6. Testing strategies

For each suggestion, include:
- Specific files/areas to modify
- Expected impact and benefits
- Implementation complexity (low/medium/high)
- Priority level (critical/high/medium/low)
"""
        
        return {
            "description": f"Improvement suggestions for {repo_url}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt_text
                    }
                }
            ]
        }

@asynccontextmanager
async def create_mcp_app():
    """Create MCP FastAPI application"""
    mcp_server = MCPServer()
    
    app = FastAPI(
        title="CodeTrace AI MCP Server",
        description="Model Context Protocol server for code analysis",
        version="1.0.0"
    )
    
    @app.websocket("/mcp")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for MCP communication with proper connection management"""
        await websocket.accept()
        connection_id = await mcp_server.connection_manager.add_connection(websocket)
        
        try:
            while True:
                # Receive request with timeout
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=300.0)
                except asyncio.TimeoutError:
                    logger.warning("WebSocket connection %s timed out", connection_id)
                    break
                
                # Validate JSON
                try:
                    request_data = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON received: %s", str(e))
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "Parse error"}
                    }
                    await websocket.send_text(json.dumps(error_response))
                    continue
                
                # Process request
                response = await mcp_server.process_request(request_data)
                
                # Send response
                await websocket.send_text(json.dumps(response))
                
        except ConnectionResetError:
            logger.info("WebSocket connection %s reset by client", connection_id)
        except Exception as e:
            logger.error("WebSocket error for %s: %s", connection_id, str(e))
        finally:
            await mcp_server.connection_manager.remove_connection(websocket)
    
    @app.post("/mcp")
    async def http_endpoint(request_data: Dict[str, Any]):
        """HTTP endpoint for MCP communication"""
        response = await mcp_server.process_request(request_data)
        return JSONResponse(content=response)
    
    @app.get("/mcp/info")
    async def server_info():
        """Get MCP server information"""
        return mcp_server.server_info.dict()
    
    yield app
