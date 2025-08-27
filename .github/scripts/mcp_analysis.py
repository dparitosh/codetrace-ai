#!/usr/bin/env python3
"""
MCP-Powered Repository Analysis Script for GitHub Actions
Uses CodeTrace AI MCP server to analyze repository and generate reports
"""

import os
import json
import requests
import sys
from datetime import datetime

def send_mcp_request(method: str, params: dict = None) -> dict:
    """Send MCP request to CodeTrace AI server"""
    request_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }
    
    try:
        response = requests.post(
            "http://localhost:8009/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        if "error" in result:
            print(f"MCP Error: {result['error']}")
            return {}
        
        return result.get("result", {})
    except Exception as e:
        print(f"MCP request failed: {e}")
        return {}

def main():
    """Main analysis function"""
    repository_url = os.environ.get('REPOSITORY_URL')
    if not repository_url:
        print("Error: REPOSITORY_URL environment variable not set")
        sys.exit(1)
    
    print(f"🔍 Starting MCP analysis for: {repository_url}")
    
    # 1. Comprehensive Repository Analysis
    print("📊 Running comprehensive analysis...")
    analysis = send_mcp_request("tools/call", {
        "name": "analyze_repository",
        "arguments": {
            "repository_url": repository_url,
            "include_quality": True,
            "include_dependencies": True
        }
    })
    
    if analysis:
        print("✅ Repository analysis completed")
        
        # Save analysis results
        with open("analysis-report.json", "w") as f:
            json.dump(analysis, f, indent=2)
    else:
        print("❌ Repository analysis failed")
        sys.exit(1)
    
    # 2. Quality Metrics Analysis
    print("📈 Analyzing quality metrics...")
    quality = send_mcp_request("codetrace/quality", {
        "repository_url": repository_url
    })
    
    if quality:
        print("✅ Quality analysis completed")
        
        # Save quality metrics
        with open("quality-metrics.json", "w") as f:
            json.dump(quality, f, indent=2)
    
    # 3. Generate AI-Powered Recommendations
    print("🤖 Generating AI recommendations...")
    recommendations = send_mcp_request("prompts/get", {
        "name": "suggest_improvements",
        "arguments": {"repository_url": repository_url}
    })
    
    if recommendations:
        print("✅ Recommendations generated")
        
        # Create recommendations markdown
        with open("recommendations.md", "w") as f:
            f.write("# 🎯 CodeTrace AI Recommendations\n\n")
            f.write(f"**Repository:** {repository_url}\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
            
            if "messages" in recommendations:
                for message in recommendations["messages"]:
                    if "content" in message and "text" in message["content"]:
                        f.write(message["content"]["text"])
                        f.write("\n\n")
    
    # 4. Generate Summary Report
    print("📝 Creating summary report...")
    
    summary = {
        "repository": repository_url,
        "analysis_timestamp": datetime.now().isoformat(),
        "status": "completed",
        "components": {
            "repository_analysis": bool(analysis),
            "quality_metrics": bool(quality),
            "ai_recommendations": bool(recommendations)
        }
    }
    
    # Extract key metrics for easy access
    if analysis:
        try:
            # Parse analysis content
            content = analysis.get("content", [])
            if len(content) > 1:
                resource_text = content[1].get("resource", {}).get("text", "{}")
                analysis_data = json.loads(resource_text)
                
                summary["metrics"] = {
                    "total_files": analysis_data.get("total_files", 0),
                    "complexity_score": analysis_data.get("complexity_score", 0),
                    "health_score": analysis_data.get("health_score", 0)
                }
        except Exception as e:
            print(f"Warning: Could not extract metrics: {e}")
    
    with open("summary-report.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print("🎉 MCP analysis completed successfully!")
    print(f"📁 Generated files:")
    print("  - analysis-report.json")
    print("  - quality-metrics.json") 
    print("  - recommendations.md")
    print("  - summary-report.json")

if __name__ == "__main__":
    main()
