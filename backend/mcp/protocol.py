"""
Model Context Protocol (MCP) - Protocol Definitions
Defines the standard MCP request/response models and types
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union, Literal
from enum import Enum
from datetime import datetime

class ContextType(str, Enum):
    """Types of context that can be provided"""
    CODE = "code"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    REPOSITORY = "repository"
    DOCUMENTATION = "documentation"
    DEPENDENCIES = "dependencies"
    QUALITY_METRICS = "quality_metrics"
    GRAPH = "graph"
    SECURITY = "security"

class ResourceType(str, Enum):
    """Types of resources available through MCP"""
    FILE = "file"
    DIRECTORY = "directory"
    SYMBOL = "symbol"
    DEPENDENCY = "dependency"
    METRIC = "metric"

class MCPCapability(str, Enum):
    """MCP server capabilities"""
    RESOURCES = "resources"
    TOOLS = "tools"
    PROMPTS = "prompts"
    LOGGING = "logging"

# Base MCP Protocol Models
class MCPMessage(BaseModel):
    """Base MCP message"""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[Union[str, int]] = Field(default=None, description="Request ID")

class MCPRequest(MCPMessage):
    """MCP request message"""
    method: str = Field(description="Method name")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Method parameters")

class MCPResponse(MCPMessage):
    """MCP response message"""
    result: Optional[Any] = Field(default=None, description="Success result")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error details")

class MCPError(BaseModel):
    """MCP error object"""
    code: int = Field(description="Error code")
    message: str = Field(description="Error message")
    data: Optional[Any] = Field(default=None, description="Additional error data")

# Server Information
class MCPServerInfo(BaseModel):
    """MCP server information"""
    name: str = Field(description="Server name")
    version: str = Field(description="Server version")
    description: Optional[str] = Field(default=None, description="Server description")
    capabilities: List[MCPCapability] = Field(description="Server capabilities")

class MCPClientInfo(BaseModel):
    """MCP client information"""
    name: str = Field(description="Client name")
    version: str = Field(description="Client version")

# Resource Models
class MCPResource(BaseModel):
    """MCP resource definition"""
    uri: str = Field(description="Resource URI")
    name: str = Field(description="Resource name")
    description: Optional[str] = Field(default=None, description="Resource description")
    mime_type: Optional[str] = Field(default=None, description="MIME type")
    annotations: Optional[Dict[str, Any]] = Field(default=None, description="Resource annotations")

class MCPResourceTemplate(BaseModel):
    """MCP resource template"""
    uri_template: str = Field(description="URI template")
    name: str = Field(description="Template name")
    description: Optional[str] = Field(default=None, description="Template description")
    mime_type: Optional[str] = Field(default=None, description="MIME type")

class MCPResourceContent(BaseModel):
    """MCP resource content"""
    uri: str = Field(description="Resource URI")
    mime_type: str = Field(description="Content MIME type")
    text: Optional[str] = Field(default=None, description="Text content")
    blob: Optional[str] = Field(default=None, description="Binary content (base64)")

# Tool Models
class MCPTool(BaseModel):
    """MCP tool definition"""
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    input_schema: Dict[str, Any] = Field(description="JSON schema for tool input")

class MCPToolCall(BaseModel):
    """MCP tool call request"""
    name: str = Field(description="Tool name")
    arguments: Dict[str, Any] = Field(description="Tool arguments")

class MCPToolResult(BaseModel):
    """MCP tool result"""
    content: List[Dict[str, Any]] = Field(description="Tool result content")
    is_error: bool = Field(default=False, description="Whether result is an error")

# Prompt Models
class MCPPrompt(BaseModel):
    """MCP prompt definition"""
    name: str = Field(description="Prompt name")
    description: str = Field(description="Prompt description")
    arguments: Optional[List[Dict[str, Any]]] = Field(default=None, description="Prompt arguments")

class MCPPromptMessage(BaseModel):
    """MCP prompt message"""
    role: Literal["user", "assistant", "system"] = Field(description="Message role")
    content: Dict[str, Any] = Field(description="Message content")

class MCPPromptResult(BaseModel):
    """MCP prompt result"""
    description: Optional[str] = Field(default=None, description="Prompt description")
    messages: List[MCPPromptMessage] = Field(description="Prompt messages")

# Logging Models
class MCPLogLevel(str, Enum):
    """Log levels"""
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"
    EMERGENCY = "emergency"

class MCPLogEntry(BaseModel):
    """MCP log entry"""
    level: MCPLogLevel = Field(description="Log level")
    data: Any = Field(description="Log data")
    logger: Optional[str] = Field(default=None, description="Logger name")

# CodeTrace-specific Models
class CodeContextRequest(BaseModel):
    """Request for code context"""
    repository_url: str = Field(description="GitHub repository URL")
    file_path: Optional[str] = Field(default=None, description="Specific file path")
    function_name: Optional[str] = Field(default=None, description="Specific function name")
    class_name: Optional[str] = Field(default=None, description="Specific class name")
    context_type: ContextType = Field(default=ContextType.CODE, description="Type of context")
    include_dependencies: bool = Field(default=True, description="Include dependency information")
    include_quality: bool = Field(default=True, description="Include quality metrics")
    max_lines: int = Field(default=100, description="Maximum lines of code to return")

class CodeSpan(BaseModel):
    """Code span with context"""
    file_path: str = Field(description="File path")
    start_line: int = Field(description="Start line number")
    end_line: int = Field(description="End line number")
    content: str = Field(description="Code content")
    language: str = Field(description="Programming language")
    context: Optional[str] = Field(default=None, description="Additional context")

class CodeSymbol(BaseModel):
    """Code symbol information"""
    name: str = Field(description="Symbol name")
    type: str = Field(description="Symbol type (function, class, variable)")
    file_path: str = Field(description="File path")
    line_number: int = Field(description="Line number")
    signature: Optional[str] = Field(default=None, description="Function/method signature")
    docstring: Optional[str] = Field(default=None, description="Documentation string")
    dependencies: List[str] = Field(default=[], description="Dependencies")

class RepositoryContext(BaseModel):
    """Repository context information"""
    url: str = Field(description="Repository URL")
    name: str = Field(description="Repository name")
    description: Optional[str] = Field(default=None, description="Repository description")
    language: str = Field(description="Primary language")
    structure: Dict[str, Any] = Field(description="Directory structure")
    key_files: List[str] = Field(description="Important files")
    dependencies: List[str] = Field(description="Dependencies")
    quality_score: Optional[float] = Field(default=None, description="Quality score")
    last_analyzed: Optional[datetime] = Field(default=None, description="Last analysis time")

class QualityContext(BaseModel):
    """Code quality context"""
    overall_score: float = Field(description="Overall quality score")
    metrics: Dict[str, float] = Field(description="Quality metrics")
    issues: List[Dict[str, Any]] = Field(description="Quality issues")
    recommendations: List[str] = Field(description="Improvement recommendations")
    complexity_metrics: Dict[str, Any] = Field(description="Complexity analysis")

class GraphContext(BaseModel):
    """Code graph context"""
    nodes: List[Dict[str, Any]] = Field(description="Graph nodes")
    edges: List[Dict[str, Any]] = Field(description="Graph edges")
    metrics: Dict[str, Any] = Field(description="Graph metrics")
    clusters: List[Dict[str, Any]] = Field(description="Code clusters")
    dependencies: Dict[str, List[str]] = Field(description="Dependency mapping")

# Response Models
class CodeContextResponse(BaseModel):
    """Response containing code context"""
    repository: RepositoryContext = Field(description="Repository information")
    code_spans: List[CodeSpan] = Field(description="Relevant code spans")
    symbols: List[CodeSymbol] = Field(description="Code symbols")
    quality: Optional[QualityContext] = Field(default=None, description="Quality information")
    graph: Optional[GraphContext] = Field(default=None, description="Graph information")
    metadata: Dict[str, Any] = Field(description="Additional metadata")

# Standard MCP Method Names
class MCPMethods:
    """Standard MCP method names"""
    # Server lifecycle
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    SHUTDOWN = "shutdown"
    
    # Resources
    LIST_RESOURCES = "resources/list"
    LIST_RESOURCE_TEMPLATES = "resources/templates/list"
    READ_RESOURCE = "resources/read"
    SUBSCRIBE_RESOURCE = "resources/subscribe"
    UNSUBSCRIBE_RESOURCE = "resources/unsubscribe"
    
    # Tools
    LIST_TOOLS = "tools/list"
    CALL_TOOL = "tools/call"
    
    # Prompts
    LIST_PROMPTS = "prompts/list"
    GET_PROMPT = "prompts/get"
    
    # Logging
    SET_LOG_LEVEL = "logging/setLevel"
    
    # CodeTrace-specific methods
    GET_CODE_CONTEXT = "codetrace/context"
    ANALYZE_REPOSITORY = "codetrace/analyze"
    GET_QUALITY_METRICS = "codetrace/quality"
    GET_DEPENDENCY_GRAPH = "codetrace/graph"
    SEARCH_CODE = "codetrace/search"
