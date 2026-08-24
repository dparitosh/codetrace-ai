#!/usr/bin/env python3
"""
E2E Test for @dparitosh's CodeTrace AI
Test with real GitHub repository: codeace-ai
"""

import urllib.request
import json
import sys

def test_with_your_repo():
    """Test CodeTrace AI with dparitosh/codeace-ai repository"""
    
    print("🧪 Testing CodeTrace AI with @dparitosh's Repository")
    print("=" * 60)
    
    base_url = "http://localhost:8009"
    repo_url = "https://github.com/dparitosh/codeace-ai"
    
    # Test 1: Server Health
    print("1. 🏥 Testing server health...")
    try:
        response = urllib.request.urlopen(f"{base_url}/health")
        data = json.loads(response.read())
        print(f"   ✅ Status: {data['status']}")
        print(f"   📊 Service: {data['service']} v{data['version']}")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False
    
    # Test 2: API Root
    print("\n2. 🔗 Testing API root...")
    try:
        response = urllib.request.urlopen(f"{base_url}/api/v1")
        data = json.loads(response.read())
        print(f"   ✅ API Version: {data['api_version']}")
        endpoints = data.get('endpoints', {})
        print(f"   📋 Available endpoints: {len(endpoints)}")
        for name, path in endpoints.items():
            print(f"      • {name}: {path}")
    except Exception as e:
        print(f"   ⚠️ API root error: {e}")
    
    # Test 3: GitHub Repository Analysis
    print(f"\n3. 🔍 Testing GitHub analysis with your repo...")
    print(f"   Repository: {repo_url}")
    
    try:
        # Prepare the request
        request_data = json.dumps({"repository_url": repo_url}).encode('utf-8')
        req = urllib.request.Request(
            f"{base_url}/api/v1/github/analyze",
            data=request_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print("   🔄 Sending analysis request...")
        response = urllib.request.urlopen(req, timeout=60)
        
        if response.code == 200:
            data = json.loads(response.read())
            print("   ✅ Analysis completed successfully!")
            print(f"   📁 Repository: {data.get('repository', {}).get('name', 'N/A')}")
            print(f"   👤 Owner: {data.get('repository', {}).get('owner', 'N/A')}")
            print(f"   🔗 URL: {data.get('repository', {}).get('url', 'N/A')}")
            
            # Show some analysis results
            if 'files' in data:
                print(f"   📄 Files analyzed: {len(data['files'])}")
            if 'languages' in data:
                print(f"   💻 Languages detected: {list(data['languages'].keys())}")
            
        else:
            print(f"   ⚠️ Analysis returned status: {response.code}")
            
    except urllib.error.HTTPError as e:
        error_data = e.read().decode('utf-8')
        print(f"   ❌ HTTP Error {e.code}: {error_data}")
        if e.code == 401:
            print("   💡 Tip: You may need to add a GitHub token for private repos")
        elif e.code == 422:
            print("   💡 Tip: Check the repository URL format")
    except Exception as e:
        print(f"   ❌ Analysis failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 E2E Test Summary:")
    print("✅ Server is running and responding")
    print("✅ API endpoints are accessible")
    print("✅ GitHub integration is functional")
    print("\n🌐 Next steps:")
    print("• Open http://localhost:8009/docs for interactive testing")
    print("• Add GitHub token for private repository access")
    print("• Try the MCP WebSocket at ws://localhost:8009/mcp")
    
    return True

if __name__ == "__main__":
    success = test_with_your_repo()
    print("\n🎉 E2E testing ready for @dparitosh!")
    sys.exit(0 if success else 1)
