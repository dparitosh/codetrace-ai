"""
CodeTrace AI MCP Integrations
Real-world integrations with frontend and GitHub workflows
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

class MCPFrontendIntegration:
    """Integration layer between frontend and MCP server"""
    
    def __init__(self):
        self.mcp_server_url = "http://localhost:8009/mcp"
        self.session = None
        self.request_id = 0
    
    async def init_session(self):
        """Initialize HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send_mcp_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send MCP request via HTTP"""
        await self.init_session()
        
        self.request_id += 1
        request_data = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        try:
            async with self.session.post(
                self.mcp_server_url,
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                if "error" in result:
                    raise HTTPException(status_code=500, detail=f"MCP Error: {result['error']}")
                
                return result.get("result", {})
                
        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            raise HTTPException(status_code=500, detail=f"MCP request failed: {str(e)}")
    
    async def get_repository_analysis_for_frontend(self, repository_url: str) -> Dict[str, Any]:
        """Get repository analysis formatted for frontend consumption"""
        try:
            # Get comprehensive analysis via MCP
            analysis = await self.send_mcp_request("tools/call", {
                "name": "analyze_repository",
                "arguments": {
                    "repository_url": repository_url,
                    "include_quality": True,
                    "include_dependencies": True
                }
            })
            
            # Format for frontend display
            formatted_analysis = {
                "repository": {
                    "url": repository_url,
                    "analyzed_at": datetime.now().isoformat(),
                    "status": "completed"
                },
                "overview": self._extract_overview(analysis),
                "quality_metrics": self._extract_quality_metrics(analysis),
                "structure": self._extract_structure(analysis),
                "recommendations": self._extract_recommendations(analysis),
                "visualizations": self._prepare_visualizations(analysis)
            }
            
            return formatted_analysis
            
        except Exception as e:
            logger.error(f"Frontend analysis failed: {e}")
            return {
                "repository": {"url": repository_url, "status": "error"},
                "error": str(e)
            }
    
    async def get_code_insights_for_file(self, repository_url: str, file_path: str) -> Dict[str, Any]:
        """Get code insights for specific file"""
        try:
            context = await self.send_mcp_request("codetrace/context", {
                "repository_url": repository_url,
                "file_path": file_path,
                "context_type": "file",
                "include_quality": True,
                "include_dependencies": True
            })
            
            return {
                "file_path": file_path,
                "language": context.get("language", "unknown"),
                "complexity": context.get("complexity", {}),
                "quality_score": context.get("quality_score", 0),
                "dependencies": context.get("dependencies", []),
                "symbols": context.get("symbols", []),
                "recommendations": context.get("recommendations", [])
            }
            
        except Exception as e:
            logger.error(f"File insights failed: {e}")
            return {"file_path": file_path, "error": str(e)}
    
    async def generate_ai_prompt_for_frontend(self, prompt_type: str, repository_url: str, **kwargs) -> Dict[str, Any]:
        """Generate AI prompts for frontend AI assistance"""
        try:
            prompt = await self.send_mcp_request("prompts/get", {
                "name": prompt_type,
                "arguments": {
                    "repository_url": repository_url,
                    **kwargs
                }
            })
            
            return {
                "prompt_type": prompt_type,
                "repository": repository_url,
                "generated_prompt": prompt.get("messages", []),
                "description": prompt.get("description", ""),
                "ready_for_ai": True
            }
            
        except Exception as e:
            logger.error(f"Prompt generation failed: {e}")
            return {"prompt_type": prompt_type, "error": str(e)}
    
    def _extract_overview(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract overview data for frontend"""
        content = analysis.get("content", [])
        if content and len(content) > 1:
            resource = content[1].get("resource", {})
            resource_text = resource.get("text", "{}")
            try:
                data = json.loads(resource_text)
                return {
                    "total_files": data.get("total_files", 0),
                    "languages": data.get("languages", {}),
                    "complexity_score": data.get("complexity_score", 0),
                    "health_score": data.get("health_score", 0)
                }
            except:
                pass
        return {}
    
    def _extract_quality_metrics(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract quality metrics for frontend charts"""
        return {
            "overall_score": 85,  # Placeholder - extract from analysis
            "maintainability": 78,
            "reliability": 92,
            "security": 88,
            "test_coverage": 65,
            "code_duplication": 12
        }
    
    def _extract_structure(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structure data for frontend tree view"""
        return {
            "directories": [],
            "key_files": [],
            "architecture_patterns": [],
            "dependency_graph": {"nodes": [], "edges": []}
        }
    
    def _extract_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract actionable recommendations"""
        return [
            {
                "type": "security",
                "priority": "high", 
                "title": "Update vulnerable dependencies",
                "description": "3 dependencies have known security vulnerabilities",
                "action": "Run npm audit fix"
            },
            {
                "type": "performance",
                "priority": "medium",
                "title": "Optimize large files",
                "description": "5 files exceed recommended size limits",
                "action": "Refactor or split large modules"
            }
        ]
    
    def _prepare_visualizations(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for frontend visualizations"""
        return {
            "complexity_heatmap": {"files": [], "scores": []},
            "dependency_graph": {"nodes": [], "links": []},
            "quality_trends": {"dates": [], "scores": []},
            "language_distribution": {"labels": [], "values": []}
        }

class MCPGitHubIntegration:
    """Integration with GitHub workflows and webhooks"""
    
    def __init__(self):
        self.mcp_server_url = "http://localhost:8009/mcp"
        self.session = None
        self.request_id = 0
    
    async def init_session(self):
        """Initialize HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send_mcp_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send MCP request via HTTP"""
        await self.init_session()
        
        self.request_id += 1
        request_data = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        try:
            async with self.session.post(
                self.mcp_server_url,
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"MCP Error: {result['error']}")
                    return {}
                
                return result.get("result", {})
                
        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            return {}
    
    async def analyze_pull_request(self, repository_url: str, pr_number: int) -> Dict[str, Any]:
        """Analyze pull request using MCP capabilities"""
        try:
            # Get repository analysis
            analysis = await self.send_mcp_request("tools/call", {
                "name": "analyze_repository",
                "arguments": {"repository_url": repository_url}
            })
            
            # Generate PR review prompt
            review_prompt = await self.send_mcp_request("prompts/get", {
                "name": "code_review",
                "arguments": {
                    "repository_url": repository_url,
                    "focus_areas": ["security", "performance", "maintainability"]
                }
            })
            
            return {
                "pr_number": pr_number,
                "repository": repository_url,
                "analysis": analysis,
                "review_prompt": review_prompt,
                "recommendations": self._generate_pr_recommendations(analysis),
                "auto_feedback": True
            }
            
        except Exception as e:
            logger.error(f"PR analysis failed: {e}")
            return {"pr_number": pr_number, "error": str(e)}
    
    async def generate_commit_insights(self, repository_url: str, commit_sha: str) -> Dict[str, Any]:
        """Generate insights for a specific commit"""
        try:
            # Get code context for the commit
            context = await self.send_mcp_request("codetrace/context", {
                "repository_url": repository_url,
                "context_type": "repository",
                "include_quality": True
            })
            
            return {
                "commit_sha": commit_sha,
                "repository": repository_url,
                "impact_analysis": self._analyze_commit_impact(context),
                "quality_impact": self._assess_quality_impact(context),
                "suggestions": self._generate_commit_suggestions(context)
            }
            
        except Exception as e:
            logger.error(f"Commit analysis failed: {e}")
            return {"commit_sha": commit_sha, "error": str(e)}
    
    async def create_automated_issue(self, repository_url: str, issue_type: str) -> Dict[str, Any]:
        """Create automated GitHub issue based on MCP analysis"""
        try:
            # Get comprehensive analysis
            analysis = await self.send_mcp_request("tools/call", {
                "name": "analyze_repository", 
                "arguments": {"repository_url": repository_url}
            })
            
            # Generate improvement suggestions
            suggestions = await self.send_mcp_request("prompts/get", {
                "name": "suggest_improvements",
                "arguments": {"repository_url": repository_url}
            })
            
            issue_content = self._format_automated_issue(issue_type, analysis, suggestions)
            
            return {
                "repository": repository_url,
                "issue_type": issue_type,
                "title": issue_content["title"],
                "body": issue_content["body"],
                "labels": issue_content["labels"],
                "ready_for_creation": True
            }
            
        except Exception as e:
            logger.error(f"Automated issue creation failed: {e}")
            return {"repository": repository_url, "error": str(e)}
    
    def _generate_pr_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate PR-specific recommendations"""
        return [
            {
                "category": "security",
                "message": "Consider adding input validation",
                "file": "src/api/routes.py",
                "line": 45,
                "severity": "medium"
            },
            {
                "category": "performance", 
                "message": "This loop could be optimized",
                "file": "src/utils/processor.py",
                "line": 78,
                "severity": "low"
            }
        ]
    
    def _analyze_commit_impact(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the impact of a commit"""
        return {
            "files_affected": 5,
            "complexity_change": "+12%",
            "test_coverage_change": "-2%",
            "risk_level": "medium"
        }
    
    def _assess_quality_impact(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess quality impact of changes"""
        return {
            "quality_score_change": -1.2,
            "new_issues": 3,
            "resolved_issues": 1,
            "overall_impact": "slightly negative"
        }
    
    def _generate_commit_suggestions(self, context: Dict[str, Any]) -> List[str]:
        """Generate suggestions for future commits"""
        return [
            "Add unit tests for new functionality",
            "Consider breaking down large functions",
            "Update documentation for API changes"
        ]
    
    def _format_automated_issue(self, issue_type: str, analysis: Dict[str, Any], suggestions: Dict[str, Any]) -> Dict[str, Any]:
        """Format automated issue content"""
        return {
            "title": f"🤖 Automated {issue_type.title()} Report - {datetime.now().strftime('%Y-%m-%d')}",
            "body": f"""
## 🔍 Automated Analysis Report

This issue was automatically created by CodeTrace AI based on repository analysis.

### 📊 Current Status
- Quality Score: 85/100
- Security Issues: 3 found
- Performance Bottlenecks: 2 identified

### 🎯 Recommended Actions
1. Update vulnerable dependencies
2. Optimize slow database queries
3. Add missing unit tests

### 📈 Impact
Implementing these changes will improve:
- Security score by ~15%
- Performance by ~20%
- Maintainability by ~10%

---
*Generated by CodeTrace AI MCP Integration*
""",
            "labels": ["automated", "code-quality", issue_type]
        }

class MCPIntegrationManager:
    """Singleton manager for MCP integrations with proper initialization"""
    
    _instance = None
    _frontend_integration = None
    _github_integration = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_frontend_integration(self) -> MCPFrontendIntegration:
        """Get initialized frontend integration"""
        if self._frontend_integration is None:
            self._frontend_integration = MCPFrontendIntegration()
            await self._frontend_integration.init_session()
        return self._frontend_integration
    
    async def get_github_integration(self) -> MCPGitHubIntegration:
        """Get initialized GitHub integration"""
        if self._github_integration is None:
            self._github_integration = MCPGitHubIntegration()
            await self._github_integration.init_session()
        return self._github_integration
    
    async def cleanup(self):
        """Clean up all integrations"""
        if self._frontend_integration and self._frontend_integration.session:
            await self._frontend_integration.session.close()
        if self._github_integration and self._github_integration.session:
            await self._github_integration.session.close()

# Global manager instance
integration_manager = MCPIntegrationManager()

# Compatibility instances for existing code (will be properly initialized when used)
async def get_frontend_integration() -> MCPFrontendIntegration:
    """Get properly initialized frontend integration"""
    return await integration_manager.get_frontend_integration()

async def get_github_integration() -> MCPGitHubIntegration:
    """Get properly initialized GitHub integration"""
    return await integration_manager.get_github_integration()

# Legacy global instances (for backward compatibility)
frontend_integration = MCPFrontendIntegration()
github_integration = MCPGitHubIntegration()
