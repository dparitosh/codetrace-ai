# 🧪 E2E Testing Guide - Real GitHub Integration

## 🚀 Quick Start

### 1. Setup GitHub Token

```bash
python setup_github_testing.py
```

This will:

- Guide you through creating a GitHub token
- Configure your environment
- Set up testing repositories

### 2. Start the Application

```bash
cd backend
python main.py
```

### 3. Test Real Repositories

#### Option A: Use the Web Interface

1. Open http://localhost:8009/docs
2. Try the `/api/v1/github/analyze` endpoint
3. Use your GitHub repository URL

#### Option B: Use MCP WebSocket

```python
import asyncio
import websockets
import json

async def test_mcp():
    uri = "ws://localhost:8009/mcp"
    async with websockets.connect(uri) as websocket:
        # Initialize MCP
        await websocket.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "Test", "version": "1.0"}
            }
        }))
        response = await websocket.recv()
        print("Init:", json.loads(response))

asyncio.run(test_mcp())
```

## 🎯 Test Scenarios

### Scenario 1: Analyze Your Own Repository

```bash
curl -X POST "http://localhost:8009/api/v1/github/analyze" \
  -H "Content-Type: application/json" \
  -d '{"repository_url": "https://github.com/YOUR_USERNAME/YOUR_REPO"}'
```

### Scenario 2: Search Code in Repository

```bash
curl -X POST "http://localhost:8009/api/v1/analysis/search" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_url": "https://github.com/YOUR_USERNAME/YOUR_REPO",
    "query": "function",
    "file_pattern": "*.py"
  }'
```

### Scenario 3: Get Quality Metrics

```bash
curl -X POST "http://localhost:8009/api/v1/quality/assess" \
  -H "Content-Type: application/json" \
  -d '{"repository_url": "https://github.com/YOUR_USERNAME/YOUR_REPO"}'
```

## 📊 Expected Results

### ✅ Success Indicators:

- **200 OK responses** from all API endpoints
- **Repository data** returned with file listings
- **Quality metrics** with scores and recommendations
- **MCP WebSocket** connections established successfully

### ⚠️ Common Issues:

- **401 Unauthorized**: Check your GitHub token
- **404 Not Found**: Verify repository URL is correct
- **Rate Limited**: Wait and try again
- **Timeout**: Large repositories may take time

## 🔧 Troubleshooting

### GitHub Token Issues

```bash
# Check if token is set
echo $GITHUB_TOKEN

# Test token manually
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
```

### Server Issues

```bash
# Check if server is running
curl http://localhost:8009/health

# View server logs
cd backend && python main.py
```

### MCP Connection Issues

```bash
# Test WebSocket endpoint
wscat -c ws://localhost:8009/mcp
```

## 🎉 Success Criteria

Your E2E setup is working correctly if you can:

1. ✅ **Authenticate** with GitHub using your token
2. ✅ **Analyze** your own repositories
3. ✅ **Search** for code patterns
4. ✅ **Get quality metrics** for your code
5. ✅ **Connect** via MCP WebSocket
6. ✅ **Receive** structured data responses

## 🔗 Useful Links

- **API Documentation**: http://localhost:8009/docs
- **Health Check**: http://localhost:8009/health
- **GitHub Token Setup**: https://github.com/settings/tokens
- **Your Repositories**: https://github.com/YOUR_USERNAME?tab=repositories

---

**Ready to test with real GitHub repositories!** 🚀
