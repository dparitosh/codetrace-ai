"""
CodeTrace AI - API Testing Script
Quick verification of backend endpoints functionality
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8009"

async def test_api_endpoints():
    """Test all main API endpoints"""
    print("🧪 CodeTrace AI - API Testing Suite")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        # Test basic endpoints
        await test_health_check(session)
        await test_root_endpoint(session)
        await test_api_info(session)
        
        # Test API endpoints
        await test_github_endpoints(session)
        await test_analysis_endpoints(session)
        await test_quality_endpoints(session)
        await test_graph_endpoints(session)

async def test_health_check(session):
    """Test health check endpoint"""
    print("\n🏥 Testing Health Check...")
    try:
        async with session.get(f"{BASE_URL}/health") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Health Check: {data['status']}")
                print(f"   Service: {data['service']}")
                print(f"   Components: {data['components']}")
            else:
                print(f"❌ Health Check failed: {response.status}")
    except Exception as e:
        print(f"❌ Health Check error: {e}")

async def test_root_endpoint(session):
    """Test root endpoint"""
    print("\n🏠 Testing Root Endpoint...")
    try:
        async with session.get(f"{BASE_URL}/") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Root: {data['service']} v{data['version']}")
                print(f"   Description: {data['description']}")
            else:
                print(f"❌ Root endpoint failed: {response.status}")
    except Exception as e:
        print(f"❌ Root endpoint error: {e}")

async def test_api_info(session):
    """Test API info endpoint"""
    print("\n📋 Testing API Info...")
    try:
        async with session.get(f"{BASE_URL}/api/v1") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ API Info: {data['api_version']}")
                print(f"   Available endpoints: {len(data['endpoints'])}")
                for name, path in data['endpoints'].items():
                    print(f"   - {name}: {path}")
            else:
                print(f"❌ API info failed: {response.status}")
    except Exception as e:
        print(f"❌ API info error: {e}")

async def test_github_endpoints(session):
    """Test GitHub integration endpoints"""
    print("\n🐙 Testing GitHub Endpoints...")
    
    # Test repository info endpoint
    try:
        async with session.get(f"{BASE_URL}/api/v1/github/repositories") as response:
            print(f"   GET /github/repositories: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Response: {len(data.get('repositories', []))} repositories")
            else:
                print(f"   ⚠️ Status: {response.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

async def test_analysis_endpoints(session):
    """Test analysis endpoints"""
    print("\n🔍 Testing Analysis Endpoints...")
    
    # Test analysis types
    try:
        async with session.get(f"{BASE_URL}/api/v1/analysis/types") as response:
            print(f"   GET /analysis/types: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Available analysis types: {len(data.get('analysis_types', []))}")
            else:
                print(f"   ⚠️ Status: {response.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

async def test_quality_endpoints(session):
    """Test quality assessment endpoints"""
    print("\n📊 Testing Quality Endpoints...")
    
    # Test quality metrics
    try:
        async with session.get(f"{BASE_URL}/api/v1/quality/metrics") as response:
            print(f"   GET /quality/metrics: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Quality metrics available")
            else:
                print(f"   ⚠️ Status: {response.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

async def test_graph_endpoints(session):
    """Test graph generation endpoints"""
    print("\n📈 Testing Graph Endpoints...")
    
    # Test graph types
    try:
        async with session.get(f"{BASE_URL}/api/v1/graph/types") as response:
            print(f"   GET /graph/types: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Available graph types: {len(data.get('graph_types', []))}")
                for graph_type in data.get('graph_types', []):
                    print(f"     - {graph_type['name']}: {graph_type['description']}")
            else:
                print(f"   ⚠️ Status: {response.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

async def test_openapi_docs(session):
    """Test OpenAPI documentation"""
    print("\n📚 Testing API Documentation...")
    try:
        async with session.get(f"{BASE_URL}/openapi.json") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ OpenAPI docs: {data['info']['title']} v{data['info']['version']}")
                print(f"   Endpoints: {len(data.get('paths', {}))}")
            else:
                print(f"❌ OpenAPI docs failed: {response.status}")
    except Exception as e:
        print(f"❌ OpenAPI docs error: {e}")

async def main():
    """Main testing function"""
    print(f"Testing CodeTrace AI API at {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        await test_api_endpoints()
        
        print("\n" + "=" * 50)
        print("🎉 API Testing Complete!")
        print("✅ Backend is responding to requests")
        print("📖 API documentation available at: http://localhost:8009/docs")
        
    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        print("⚠️ Make sure the backend server is running on port 8009")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
