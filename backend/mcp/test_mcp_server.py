#!/usr/bin/env python3
"""
CodeTrace AI MCP Server Test Suite
Tests the MCP server functionality and endpoints
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch

# Test the MCP protocol models
def test_mcp_protocol_models():
    """Test MCP protocol model creation"""
    from backend.mcp.protocol import (
        MCPRequest, MCPResponse, MCPServerInfo, 
        CodeContextRequest, ContextType
    )
    
    # Test MCP Request
    request = MCPRequest(
        method="initialize",
        params={"test": "value"}
    )
    assert request.method == "initialize"
    assert request.jsonrpc == "2.0"
    
    # Test Code Context Request
    context_req = CodeContextRequest(
        repository_url="https://github.com/test/repo",
        context_type=ContextType.CODE
    )
    assert context_req.repository_url == "https://github.com/test/repo"
    assert context_req.context_type == ContextType.CODE
    
    print("✅ MCP Protocol models work correctly")

def test_mcp_server_initialization():
    """Test MCP server initialization"""
    from backend.mcp.server import MCPServer
    
    # Create server instance
    server = MCPServer()
    
    # Check basic properties
    assert server.server_info.name == "CodeTrace AI MCP Server"
    assert server.server_info.version == "1.0.0"
    assert len(server.capabilities) == 4
    assert not server.is_initialized
    
    print("✅ MCP Server initializes correctly")

@pytest.mark.asyncio
async def test_mcp_server_lifecycle():
    """Test MCP server lifecycle methods"""
    from backend.mcp.server import MCPServer
    
    server = MCPServer()
    
    # Test initialize
    init_params = {
        "protocolVersion": "2024-11-05",
        "clientInfo": {
            "name": "Test Client",
            "version": "1.0.0"
        }
    }
    
    init_result = await server._handle_initialize(init_params)
    assert "serverInfo" in init_result
    assert server.client_info.name == "Test Client"
    
    # Test initialized
    await server._handle_initialized({})
    assert server.is_initialized
    
    # Test shutdown
    await server._handle_shutdown({})
    assert not server.is_initialized
    
    print("✅ MCP Server lifecycle works correctly")

@pytest.mark.asyncio
async def test_mcp_request_processing():
    """Test MCP request processing"""
    from backend.mcp.server import MCPServer
    
    server = MCPServer()
    
    # Initialize server first
    await server._handle_initialize({
        "clientInfo": {"name": "Test", "version": "1.0.0"}
    })
    await server._handle_initialized({})
    
    # Test valid request
    request_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resources/list",
        "params": {}
    }
    
    response = await server.process_request(request_data)
    assert response["id"] == 1
    assert "result" in response
    
    # Test invalid method
    invalid_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "invalid/method",
        "params": {}
    }
    
    error_response = await server.process_request(invalid_request)
    assert "error" in error_response
    assert error_response["error"]["code"] == -32601
    
    print("✅ MCP Request processing works correctly")

def test_mcp_handlers_initialization():
    """Test MCP handlers initialize properly"""
    from backend.mcp.handlers import (
        CodeContextHandler, 
        RepositoryHandler, 
        QualityHandler
    )
    
    # Test handler creation
    code_handler = CodeContextHandler()
    repo_handler = RepositoryHandler()
    quality_handler = QualityHandler()
    
    # Check handlers have required methods
    assert hasattr(code_handler, 'get_code_context')
    assert hasattr(repo_handler, 'analyze_repository')
    assert hasattr(quality_handler, 'get_quality_metrics')
    
    print("✅ MCP Handlers initialize correctly")

@pytest.mark.asyncio
async def test_mcp_tools_list():
    """Test MCP tools listing"""
    from backend.mcp.server import MCPServer
    
    server = MCPServer()
    
    # Initialize server
    await server._handle_initialize({
        "clientInfo": {"name": "Test", "version": "1.0.0"}
    })
    await server._handle_initialized({})
    
    # Get tools list
    tools_result = await server._handle_list_tools({})
    
    assert "tools" in tools_result
    tools = tools_result["tools"]
    assert len(tools) >= 3
    
    # Check for expected tools
    tool_names = [tool["name"] for tool in tools]
    assert "analyze_repository" in tool_names
    assert "search_code" in tool_names
    assert "get_code_context" in tool_names
    
    print("✅ MCP Tools listing works correctly")

@pytest.mark.asyncio 
async def test_mcp_resources_list():
    """Test MCP resources listing"""
    from backend.mcp.server import MCPServer
    
    server = MCPServer()
    
    # Initialize server
    await server._handle_initialize({
        "clientInfo": {"name": "Test", "version": "1.0.0"}
    })
    await server._handle_initialized({})
    
    # Get resources list
    resources_result = await server._handle_list_resources({})
    
    assert "resources" in resources_result
    resources = resources_result["resources"]
    assert len(resources) >= 5
    
    # Check for expected resource patterns
    resource_uris = [res["uri"] for res in resources]
    assert any("repository" in uri for uri in resource_uris)
    assert any("file" in uri for uri in resource_uris)
    assert any("quality" in uri for uri in resource_uris)
    
    print("✅ MCP Resources listing works correctly")

@pytest.mark.asyncio
async def test_mcp_prompts_list():
    """Test MCP prompts listing"""
    from backend.mcp.server import MCPServer
    
    server = MCPServer()
    
    # Initialize server
    await server._handle_initialize({
        "clientInfo": {"name": "Test", "version": "1.0.0"}
    })
    await server._handle_initialized({})
    
    # Get prompts list
    prompts_result = await server._handle_list_prompts({})
    
    assert "prompts" in prompts_result
    prompts = prompts_result["prompts"]
    assert len(prompts) >= 3
    
    # Check for expected prompts
    prompt_names = [prompt["name"] for prompt in prompts]
    assert "code_review" in prompt_names
    assert "explain_code" in prompt_names
    assert "suggest_improvements" in prompt_names
    
    print("✅ MCP Prompts listing works correctly")

def test_mcp_error_handling():
    """Test MCP error handling"""
    from backend.mcp.server import MCPServer
    
    server = MCPServer()
    
    # Test error response creation
    error_response = server._create_error_response(123, -32601, "Method not found")
    
    assert error_response["id"] == 123
    assert error_response["error"]["code"] == -32601
    assert error_response["error"]["message"] == "Method not found"
    
    print("✅ MCP Error handling works correctly")

def run_all_tests():
    """Run all MCP server tests"""
    print("🧪 Running CodeTrace AI MCP Server Tests")
    print("=" * 50)
    
    try:
        # Basic functionality tests
        test_mcp_protocol_models()
        test_mcp_server_initialization()
        test_mcp_handlers_initialization()
        test_mcp_error_handling()
        
        # Async tests
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(test_mcp_server_lifecycle())
            loop.run_until_complete(test_mcp_request_processing())
            loop.run_until_complete(test_mcp_tools_list())
            loop.run_until_complete(test_mcp_resources_list())
            loop.run_until_complete(test_mcp_prompts_list())
        finally:
            loop.close()
        
        print("\n" + "=" * 50)
        print("✅ All MCP Server tests passed!")
        print("\n🚀 MCP Server is ready for production use")
        print("\nTo start the MCP server:")
        print("  python backend/main.py")
        print("\nMCP Endpoints:")
        print("  WebSocket: ws://localhost:8009/mcp")
        print("  HTTP:      http://localhost:8009/mcp")
        print("  Info:      http://localhost:8009/mcp/info")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    import sys
    import os
    
    # Add backend to path
    backend_path = os.path.join(os.path.dirname(__file__), "..")
    sys.path.insert(0, backend_path)
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
