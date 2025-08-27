"""
CodeTrace AI - Enhanced Code Graph Integration
Integrates codegraph_core for advanced GitHub repository analysis
"""
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add codegraph_core to path
CODETRACE_ROOT = Path(__file__).resolve().parent.parent.parent
CODEGRAPH_PATH = CODETRACE_ROOT / "codegraph_core"
if str(CODEGRAPH_PATH) not in sys.path:
    sys.path.insert(0, str(CODEGRAPH_PATH))

try:
    from codegraph_core import CodeGraph
    from codegraph_core.graph.nx_adapter import to_networkx, compute_basic_metrics
    CODEGRAPH_AVAILABLE = True
except ImportError as e:
    CodeGraph = None
    to_networkx = None
    compute_basic_metrics = None
    CODEGRAPH_AVAILABLE = False


class CodeTraceGraphAnalyzer:
    """Enhanced code graph analyzer for CodeTrace AI"""
    
    def __init__(self):
        if not CODEGRAPH_AVAILABLE:
            raise RuntimeError("codegraph_core not available")
        self.graph = CodeGraph()
        self.last_scan_result = None
    
    async def analyze_repository(self, repo_path: str, languages: List[str] = None) -> Dict[str, Any]:
        """
        Analyze a GitHub repository for code structure and dependencies
        
        Args:
            repo_path: Path to cloned repository
            languages: List of languages to analyze (default: ['python'])
        
        Returns:
            Comprehensive analysis results
        """
        languages = languages or ['python']
        
        # Scan the repository
        scan_result = self.graph.scan(paths=[repo_path])
        self.last_scan_result = scan_result
        
        # Generate NetworkX graph for advanced metrics
        nx_graph = to_networkx(self.graph.g) if to_networkx else None
        
        # Extract key insights
        analysis = {
            "scan_summary": scan_result,
            "node_count": len(self.graph.g.nodes),
            "edge_count": sum(len(edges) for edges in self.graph.g.edges.values()),
            "languages_detected": languages,
            "complexity_metrics": {},
            "architectural_insights": {},
            "quality_indicators": {}
        }
        
        if nx_graph:
            # Advanced graph metrics
            analysis["complexity_metrics"] = self._compute_complexity_metrics(nx_graph)
            analysis["architectural_insights"] = self._analyze_architecture(nx_graph)
        
        return analysis
    
    async def find_code_context(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Find relevant code context for a natural language query
        
        Args:
            query: Natural language description of what to find
            top_k: Number of top results to return
        
        Returns:
            Relevant code snippets and context
        """
        if not self.last_scan_result:
            raise ValueError("Repository not analyzed yet. Call analyze_repository first.")
        
        context = self.graph.prompt_context(query, top_k=top_k)
        
        # Enhance with additional metadata
        enhanced_context = {
            **context,
            "analysis_metadata": {
                "query_complexity": len(query.split()),
                "total_nodes_searched": len(self.graph.g.nodes),
                "relevance_threshold": 0.1
            }
        }
        
        return enhanced_context
    
    def _compute_complexity_metrics(self, nx_graph) -> Dict[str, Any]:
        """Compute code complexity metrics"""
        try:
            import networkx as nx
            
            metrics = {
                "density": nx.density(nx_graph),
                "is_connected": nx.is_weakly_connected(nx_graph),
                "number_of_components": nx.number_weakly_connected_components(nx_graph),
                "average_clustering": nx.average_clustering(nx_graph.to_undirected()),
            }
            
            # Centrality measures for top nodes
            centrality = nx.degree_centrality(nx_graph)
            top_central = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
            metrics["top_central_nodes"] = top_central
            
            return metrics
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_architecture(self, nx_graph) -> Dict[str, Any]:
        """Analyze architectural patterns"""
        try:
            import networkx as nx
            
            # Find modules with high in-degree (heavily used)
            in_degrees = dict(nx_graph.in_degree())
            heavily_used = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # Find modules with high out-degree (high coupling)
            out_degrees = dict(nx_graph.out_degree())
            high_coupling = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "heavily_used_modules": heavily_used,
                "highly_coupled_modules": high_coupling,
                "modularity_score": self._compute_modularity(nx_graph),
                "architectural_debt_indicators": self._detect_architectural_debt(nx_graph)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _compute_modularity(self, nx_graph) -> float:
        """Compute modularity score indicating good architectural separation"""
        try:
            import networkx as nx
            from networkx.algorithms import community
            
            undirected = nx_graph.to_undirected()
            communities = community.greedy_modularity_communities(undirected)
            return community.modularity(undirected, communities)
        except Exception:
            return 0.0
    
    def _detect_architectural_debt(self, nx_graph) -> List[Dict[str, Any]]:
        """Detect potential architectural debt indicators"""
        debt_indicators = []
        
        try:
            import networkx as nx
            
            # Detect circular dependencies
            if not nx.is_directed_acyclic_graph(nx_graph):
                cycles = list(nx.simple_cycles(nx_graph))
                debt_indicators.append({
                    "type": "circular_dependency",
                    "severity": "high",
                    "count": len(cycles),
                    "examples": cycles[:3]  # Show first 3 examples
                })
            
            # Detect god modules (high degree)
            degrees = dict(nx_graph.degree())
            avg_degree = sum(degrees.values()) / len(degrees) if degrees else 0
            god_modules = [node for node, degree in degrees.items() if degree > avg_degree * 3]
            
            if god_modules:
                debt_indicators.append({
                    "type": "god_modules",
                    "severity": "medium",
                    "modules": god_modules[:5],
                    "recommendation": "Consider breaking down these modules"
                })
            
            return debt_indicators
        except Exception:
            return []


class GitHubRepositoryAnalyzer:
    """High-level analyzer for GitHub repositories using CodeTrace AI"""
    
    def __init__(self):
        self.code_analyzer = CodeTraceGraphAnalyzer()
    
    async def comprehensive_analysis(self, repo_path: str) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of a GitHub repository
        
        Returns:
            Complete analysis including code structure, quality, and recommendations
        """
        try:
            # Core code analysis
            code_analysis = await self.code_analyzer.analyze_repository(repo_path)
            
            # Generate quality score
            quality_score = self._calculate_quality_score(code_analysis)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(code_analysis)
            
            return {
                "repository_path": repo_path,
                "analysis_timestamp": self._get_timestamp(),
                "code_analysis": code_analysis,
                "quality_score": quality_score,
                "recommendations": recommendations,
                "codetrace_ai_version": "1.0.0"
            }
        except Exception as e:
            return {"error": str(e), "repository_path": repo_path}
    
    def _calculate_quality_score(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall code quality score"""
        base_score = 70  # Starting score
        
        # Adjust based on complexity metrics
        complexity = analysis.get("complexity_metrics", {})
        if complexity.get("density", 0) < 0.1:
            base_score += 10  # Good modularity
        elif complexity.get("density", 0) > 0.5:
            base_score -= 15  # Too dense, poor modularity
        
        # Adjust based on architectural insights
        architecture = analysis.get("architectural_insights", {})
        debt_indicators = architecture.get("architectural_debt_indicators", [])
        base_score -= len(debt_indicators) * 5  # Reduce score for debt
        
        return {
            "overall_score": max(0, min(100, base_score)),
            "category": "excellent" if base_score >= 90 else "good" if base_score >= 70 else "needs_improvement",
            "factors": {
                "modularity": complexity.get("density", 0),
                "architectural_debt": len(debt_indicators)
            }
        }
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Check architectural debt
        debt_indicators = analysis.get("architectural_insights", {}).get("architectural_debt_indicators", [])
        for debt in debt_indicators:
            if debt["type"] == "circular_dependency":
                recommendations.append({
                    "priority": "high",
                    "category": "architecture",
                    "title": "Resolve Circular Dependencies",
                    "description": f"Found {debt['count']} circular dependencies that should be refactored",
                    "action": "Review and refactor circular imports"
                })
        
        # Check complexity
        complexity = analysis.get("complexity_metrics", {})
        if complexity.get("density", 0) > 0.4:
            recommendations.append({
                "priority": "medium",
                "category": "complexity",
                "title": "Reduce Module Coupling",
                "description": "High coupling detected between modules",
                "action": "Consider implementing dependency injection or facade patterns"
            })
        
        return recommendations
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()


# Export for CodeTrace AI backend
__all__ = ["CodeTraceGraphAnalyzer", "GitHubRepositoryAnalyzer", "CODEGRAPH_AVAILABLE"]
