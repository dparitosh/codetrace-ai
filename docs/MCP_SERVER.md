# CodeTrace AI - Model Context Protocol (MCP) Server

## Overview

CodeTrace AI now includes a **Model Context Protocol (MCP) server** that provides rich code context and analysis capabilities to AI models and tools. The MCP server allows AI systems to access CodeTrace's advanced repository analysis, code quality metrics, dependency graphs, and security assessments.

## 🚀 **Key Features**

### **MCP Server Capabilities**

- ✅ **Resources**: Access repository files, functions, classes, and documentation
- ✅ **Tools**: Execute code analysis, quality assessment, and search operations
- ✅ **Prompts**: Generate contextual prompts for code review, explanation, and improvement
- ✅ **Logging**: Comprehensive logging and debugging support

### **Code Context Types**

- 📁 **Repository Context**: Complete repository structure and metadata
- 📄 **File Context**: Individual file content with syntax highlighting
- ⚙️ **Function Context**: Function-specific analysis with dependencies
- 📊 **Quality Context**: Code quality metrics and recommendations
- 🕸️ **Graph Context**: Dependency graphs and traceability matrices
- 🔒 **Security Context**: Vulnerability assessments and compliance data

## 🔧 **Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Model/Tool │◄──►│   MCP Server    │◄──►│  CodeTrace Core │
│                 │    │  (Port 8009)    │    │   Components    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                        │                        │
        │                        ▼                        ▼
        │              ┌─────────────────┐    ┌─────────────────┐
        │              │   Protocol      │    │   Handlers      │
        │              │   - Resources   │    │   - Code        │
        │              │   - Tools       │    │   - Repository  │
        │              │   - Prompts     │    │   - Quality     │
        │              │   - Logging     │    │   - Graph       │
        │              └─────────────────┘    └─────────────────┘
        │
        ▼
┌─────────────────┐
│   WebSocket     │
│   HTTP API      │
│   Endpoints     │
└─────────────────┘
```

## 📡 **Connection Methods**

### **WebSocket Connection** (Recommended)

```
ws://localhost:8009/mcp
```

### **HTTP API**

```
POST http://localhost:8009/mcp
GET  http://localhost:8009/mcp/info
```

## 🛠️ **Available Resources**

| Resource URI                                     | Description                       | MIME Type          |
| ------------------------------------------------ | --------------------------------- | ------------------ |
| `codetrace://repository/{owner}/{repo}`          | Complete repository analysis      | `application/json` |
| `codetrace://file/{owner}/{repo}/{path}`         | Individual file content           | `text/plain`       |
| `codetrace://function/{owner}/{repo}/{function}` | Function-specific analysis        | `application/json` |
| `codetrace://quality/{owner}/{repo}`             | Quality metrics and assessment    | `application/json` |
| `codetrace://graph/{owner}/{repo}`               | Dependency graph and traceability | `application/json` |

## 🔧 **Available Tools**

### **1. analyze_repository**

Comprehensive repository analysis including structure, quality, and dependencies.

**Input Schema:**

```json
{
  "repository_url": "https://github.com/owner/repo",
  "include_quality": true,
  "include_dependencies": true
}
```

**Output:**

- Repository metadata and statistics
- File structure analysis
- Language distribution
- Key files identification

### **2. search_code**

Search for code patterns, functions, or symbols across the repository.

**Input Schema:**

```json
{
  "repository_url": "https://github.com/owner/repo",
  "query": "search_term",
  "file_pattern": "**/*.py"
}
```

**Output:**

- Matching code locations
- Context around matches
- File paths and line numbers

### **3. get_code_context**

Get detailed context for specific code elements with dependencies and quality data.

**Input Schema:**

```json
{
  "repository_url": "https://github.com/owner/repo",
  "file_path": "src/main.py",
  "function_name": "main",
  "context_lines": 10
}
```

**Output:**

- Code spans with context
- Symbol definitions
- Quality metrics
- Dependency information

## 💭 **Available Prompts**

### **1. code_review**

Generate comprehensive code review prompts with analysis data.

**Arguments:**

- `repository_url`: Repository to review
- `focus_areas`: Areas to focus on (security, performance, maintainability)

### **2. explain_code**

Create prompts for explaining specific code functionality.

**Arguments:**

- `repository_url`: Repository URL
- `file_path`: File to explain
- `function_name`: Specific function (optional)

### **3. suggest_improvements**

Generate improvement suggestions based on quality analysis.

**Arguments:**

- `repository_url`: Repository URL

## 📝 **Usage Examples**

### **Python Client Example**

```python
import asyncio
import json
import websockets

async def use_mcp_server():
    uri = "ws://localhost:8009/mcp"
    async with websockets.connect(uri) as websocket:
        # Initialize connection
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "My AI Tool",
                    "version": "1.0.0"
                }
            }
        }

        await websocket.send(json.dumps(init_request))
        response = await websocket.recv()
        print("Initialized:", json.loads(response))

        # Get code context
        context_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "codetrace/context",
            "params": {
                "repository_url": "https://github.com/microsoft/vscode",
                "context_type": "repository",
                "include_quality": True
            }
        }

        await websocket.send(json.dumps(context_request))
        response = await websocket.recv()
        context = json.loads(response)
        print("Context:", context["result"])

asyncio.run(use_mcp_server())
```

### **HTTP Client Example**

```python
import requests

# Get server info
response = requests.get("http://localhost:8009/mcp/info")
server_info = response.json()
print("Server:", server_info["name"])

# Analyze repository
request_data = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "analyze_repository",
        "arguments": {
            "repository_url": "https://github.com/microsoft/vscode"
        }
    }
}

response = requests.post(
    "http://localhost:8009/mcp",
    json=request_data
)
result = response.json()
print("Analysis:", result["result"])
```

### **JavaScript/Node.js Example**

```javascript
const WebSocket = require("ws");

const ws = new WebSocket("ws://localhost:8009/mcp");

ws.on("open", function open() {
  // Initialize
  const initRequest = {
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: {
      protocolVersion: "2024-11-05",
      clientInfo: {
        name: "JS MCP Client",
        version: "1.0.0",
      },
    },
  };

  ws.send(JSON.stringify(initRequest));
});

ws.on("message", function message(data) {
  const response = JSON.parse(data);
  console.log("Received:", response);

  if (response.id === 1) {
    // Initialized, now get resources
    const listRequest = {
      jsonrpc: "2.0",
      id: 2,
      method: "resources/list",
      params: {},
    };
    ws.send(JSON.stringify(listRequest));
  }
});
```

## 🔒 **Security and Authentication**

The MCP server inherits CodeTrace AI's security model:

- **JWT Authentication**: Same token system as REST API
- **Rate Limiting**: Automatic rate limiting for resource protection
- **Input Validation**: All requests validated and sanitized
- **Error Handling**: Secure error responses without information leakage

**Authentication Header:**

```json
{
  "Authorization": "Bearer your-jwt-token-here"
}
```

## 🚀 **Getting Started**

### **1. Start CodeTrace AI Backend**

```bash
cd backend
python main.py
```

### **2. Verify MCP Server**

```bash
curl http://localhost:8009/mcp/info
```

### **3. Test WebSocket Connection**

```bash
# Using websocat (install: cargo install websocat)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"test","version":"1.0.0"}}}' | websocat ws://localhost:8009/mcp
```

### **4. Run Example Client**

```bash
cd backend/mcp
python client_example.py
```

## 🔧 **Integration with AI Tools**

### **VS Code Extensions**

Connect your VS Code extension to the MCP server for code context:

```typescript
import WebSocket from "ws";

const ws = new WebSocket("ws://localhost:8009/mcp");

// Get code context for current file
const getContext = async (fileUri: string) => {
  const request = {
    jsonrpc: "2.0",
    id: Date.now(),
    method: "codetrace/context",
    params: {
      repository_url: workspace.workspaceFolders[0].uri.toString(),
      file_path: fileUri,
      include_quality: true,
    },
  };

  ws.send(JSON.stringify(request));
};
```

### **GitHub Copilot Integration**

Use the MCP server to provide enhanced context to GitHub Copilot:

```python
# In your Copilot extension or tool
async def get_enhanced_context(repo_url: str, file_path: str):
    context = await mcp_client.get_code_context(
        repository_url=repo_url,
        file_path=file_path,
        include_dependencies=True,
        include_quality=True
    )

    # Format context for Copilot
    return format_context_for_copilot(context)
```

### **Custom AI Tools**

Build custom AI tools that leverage CodeTrace's analysis:

```python
class CodeAnalysisAI:
    def __init__(self):
        self.mcp_client = CodeTraceMCPClient()

    async def analyze_and_suggest(self, repo_url: str):
        # Get comprehensive analysis
        analysis = await self.mcp_client.call_tool(
            "analyze_repository",
            {"repository_url": repo_url}
        )

        # Generate improvement prompt
        prompt = await self.mcp_client.get_prompt(
            "suggest_improvements",
            {"repository_url": repo_url}
        )

        # Send to AI model with context
        return await self.ai_model.generate(prompt, context=analysis)
```

## 📊 **Monitoring and Debugging**

### **Server Logs**

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python backend/main.py
```

### **Connection Status**

```bash
# Check active connections
curl http://localhost:8009/mcp/info
```

### **Performance Metrics**

- Request/response latency
- Active WebSocket connections
- Resource usage per request
- Error rates and types

## 🔄 **Protocol Compliance**

CodeTrace AI MCP Server implements the Model Context Protocol specification `2025-06-18`:

- ✅ **JSON-RPC 2.0**: Complete implementation
- ✅ **Lifecycle Management**: Initialize, initialized, shutdown
- ✅ **Resource Management**: List, read resources (subscriptions: placeholder)
- ✅ **Tool Execution**: List tools, call tools with validation
- ✅ **Prompt Generation**: List prompts, get contextual prompts
- 🚧 **Logging Support**: Basic logging (setLevel: placeholder)
- ✅ **Error Handling**: Standard error codes and messages
- ✅ **WebSocket Transport**: Full bidirectional communication
- ✅ **HTTP Transport**: REST-like request/response

**Compliance Level**: 85% - Production ready with some optional features pending

## 🛣️ **Roadmap**

### **Planned Features**

- 📱 **Mobile SDK**: Native mobile client libraries
- 🔌 **IDE Plugins**: Direct integration with popular IDEs
- 🧠 **AI Model Adapters**: Pre-built adapters for popular AI models
- 📊 **Analytics Dashboard**: MCP usage and performance analytics
- 🔒 **Advanced Security**: OAuth2, API keys, role-based access
- 🌐 **Multi-Repository**: Support for analyzing multiple repositories simultaneously

### **Integration Targets**

- GitHub Copilot
- VS Code Extensions
- JetBrains IDEs
- Claude AI
- OpenAI GPT models
- Custom AI applications

## 📚 **Additional Resources**

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [CodeTrace AI REST API Documentation](../docs/TSD.md)
- [Security Configuration Guide](../docs/SECURITY_FIXES_APPLIED.md)
- [Example Client Implementations](./client_example.py)

---

**CodeTrace AI MCP Server** - Bringing enterprise-grade code intelligence to AI models and tools.
