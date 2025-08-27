"""
CodeTrace AI - Quality Assessment Module
Leverages SODA Core and custom rules for comprehensive code quality analysis
"""

import asyncio
import json
import logging
import os
import tempfile
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class QualityValidator:
    """Comprehensive code quality validator using SODA Core and custom rules"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "codetrace-analysis"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Quality rules database
        self.quality_rules = self._load_quality_rules()
        
        # Supported file types for analysis
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.sql': 'sql',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.md': 'markdown'
        }
    
    def _load_quality_rules(self) -> Dict[str, Any]:
        """Load quality assessment rules"""
        return {
            "complexity": {
                "max_cyclomatic_complexity": 10,
                "max_function_length": 50,
                "max_file_length": 500,
                "max_nesting_depth": 4
            },
            "maintainability": {
                "min_documentation_ratio": 0.1,
                "max_duplicate_lines": 0.05,
                "required_patterns": ["README", "LICENSE"],
                "forbidden_patterns": ["TODO", "FIXME", "HACK"]
            },
            "security": {
                "forbidden_functions": ["eval", "exec", "system"],
                "required_validations": ["input_validation", "sql_injection_prevention"],
                "secret_patterns": [
                    r"api[_-]?key",
                    r"password",
                    r"secret",
                    r"token",
                    r"auth[_-]?key"
                ]
            },
            "performance": {
                "max_memory_usage": "500MB",
                "max_execution_time": 30,
                "efficient_algorithms": True,
                "database_optimization": True
            },
            "style": {
                "consistent_naming": True,
                "proper_indentation": True,
                "max_line_length": 120,
                "trailing_whitespace": False
            }
        }
    
    async def analyze_repository_quality(self, repo_data: Dict[str, Any], file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Comprehensive repository quality analysis"""
        logger.info(f"Starting quality analysis for repository: {repo_data.get('repository', {}).get('full_name')}")
        
        analysis_results = {
            "overall_score": 0,
            "metrics": {},
            "issues": [],
            "recommendations": [],
            "detailed_analysis": {},
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Analyze different quality aspects
            complexity_analysis = await self._analyze_complexity(file_contents)
            maintainability_analysis = await self._analyze_maintainability(repo_data, file_contents)
            security_analysis = await self._analyze_security(file_contents)
            performance_analysis = await self._analyze_performance(file_contents)
            style_analysis = await self._analyze_style(file_contents)
            
            # Combine results
            analysis_results["detailed_analysis"] = {
                "complexity": complexity_analysis,
                "maintainability": maintainability_analysis,
                "security": security_analysis,
                "performance": performance_analysis,
                "style": style_analysis
            }
            
            # Calculate metrics
            analysis_results["metrics"] = self._calculate_quality_metrics(analysis_results["detailed_analysis"])
            
            # Generate issues and recommendations
            analysis_results["issues"] = self._extract_issues(analysis_results["detailed_analysis"])
            analysis_results["recommendations"] = self._generate_recommendations(analysis_results["detailed_analysis"])
            
            # Calculate overall score
            analysis_results["overall_score"] = self._calculate_overall_score(analysis_results["metrics"])
            
            logger.info(f"Quality analysis completed. Overall score: {analysis_results['overall_score']}")
            
        except Exception as e:
            logger.error(f"Error during quality analysis: {e}")
            analysis_results["error"] = str(e)
        
        return analysis_results
    
    async def _analyze_complexity(self, file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Analyze code complexity metrics"""
        complexity_results = {
            "cyclomatic_complexity": {},
            "function_lengths": {},
            "file_lengths": {},
            "nesting_depths": {},
            "complexity_score": 0
        }
        
        total_complexity = 0
        file_count = 0
        
        for file_path, content in file_contents.items():
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in self.supported_extensions:
                continue
                
            file_count += 1
            
            # Analyze file length
            lines = content.split('\n')
            line_count = len(lines)
            complexity_results["file_lengths"][file_path] = line_count
            
            # Basic complexity analysis
            if file_ext == '.py':
                complexity = await self._analyze_python_complexity(content)
            elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
                complexity = await self._analyze_javascript_complexity(content)
            else:
                complexity = await self._analyze_generic_complexity(content)
            
            complexity_results["cyclomatic_complexity"][file_path] = complexity
            total_complexity += complexity
        
        if file_count > 0:
            avg_complexity = total_complexity / file_count
            complexity_results["complexity_score"] = min(100, max(0, 100 - (avg_complexity - 5) * 10))
        
        return complexity_results
    
    async def _analyze_python_complexity(self, content: str) -> int:
        """Analyze Python-specific complexity"""
        complexity = 1  # Base complexity
        
        # Count decision points
        decision_keywords = ['if', 'elif', 'for', 'while', 'try', 'except', 'and', 'or']
        for keyword in decision_keywords:
            complexity += content.count(f' {keyword} ')
            complexity += content.count(f'\n{keyword} ')
        
        return complexity
    
    async def _analyze_javascript_complexity(self, content: str) -> int:
        """Analyze JavaScript/TypeScript complexity"""
        complexity = 1  # Base complexity
        
        # Count decision points
        decision_patterns = ['if (', 'for (', 'while (', 'switch (', '&&', '||', 'catch (', '?', ':']
        for pattern in decision_patterns:
            complexity += content.count(pattern)
        
        return complexity
    
    async def _analyze_generic_complexity(self, content: str) -> int:
        """Generic complexity analysis for unsupported languages"""
        lines = content.split('\n')
        
        # Basic heuristics
        complexity = 1
        complexity += len([line for line in lines if any(keyword in line for keyword in ['if', 'for', 'while'])])
        
        return complexity
    
    async def _analyze_maintainability(self, repo_data: Dict[str, Any], file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Analyze code maintainability factors"""
        maintainability_results = {
            "documentation_ratio": 0,
            "duplicate_code": 0,
            "required_files": {},
            "code_organization": {},
            "maintainability_score": 0
        }
        
        # Check for required files
        required_files = ["README.md", "LICENSE", ".gitignore"]
        repo_files = list(file_contents.keys())
        
        for required_file in required_files:
            found = any(required_file.lower() in file.lower() for file in repo_files)
            maintainability_results["required_files"][required_file] = found
        
        # Calculate documentation ratio
        total_lines = 0
        comment_lines = 0
        
        for file_path, content in file_contents.items():
            lines = content.split('\n')
            total_lines += len(lines)
            
            # Count comment lines (basic heuristic)
            file_ext = Path(file_path).suffix.lower()
            if file_ext == '.py':
                comment_lines += len([line for line in lines if line.strip().startswith('#') or '"""' in line])
            elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
                comment_lines += len([line for line in lines if line.strip().startswith('//') or '/*' in line])
        
        if total_lines > 0:
            maintainability_results["documentation_ratio"] = comment_lines / total_lines
        
        # Calculate maintainability score
        score = 50  # Base score
        
        # Bonus for required files
        required_files_score = sum(maintainability_results["required_files"].values()) / len(required_files) * 20
        score += required_files_score
        
        # Bonus for documentation
        doc_ratio = maintainability_results["documentation_ratio"]
        if doc_ratio >= 0.15:
            score += 20
        elif doc_ratio >= 0.10:
            score += 10
        
        # Bonus for organization
        if any('src/' in file or 'lib/' in file for file in repo_files):
            score += 10
        
        maintainability_results["maintainability_score"] = min(100, max(0, score))
        
        return maintainability_results
    
    async def _analyze_security(self, file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Analyze security vulnerabilities and patterns"""
        security_results = {
            "vulnerabilities": [],
            "secret_exposures": [],
            "security_score": 100
        }
        
        # Security patterns to check
        dangerous_patterns = {
            'eval_usage': r'\beval\s*\(',
            'exec_usage': r'\bexec\s*\(',
            'sql_injection': r'SELECT.*\+.*|INSERT.*\+.*',
            'xss_risk': r'innerHTML\s*=|document\.write\(',
            'hardcoded_secrets': r'password\s*=\s*["\'][^"\']+["\']|api_key\s*=\s*["\'][^"\']+["\']'
        }
        
        import re
        
        for file_path, content in file_contents.items():
            for pattern_name, pattern in dangerous_patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    security_results["vulnerabilities"].append({
                        "file": file_path,
                        "type": pattern_name,
                        "matches": len(matches),
                        "severity": "high" if pattern_name in ['eval_usage', 'sql_injection'] else "medium"
                    })
        
        # Calculate security score
        vulnerability_count = len(security_results["vulnerabilities"])
        high_severity = len([v for v in security_results["vulnerabilities"] if v["severity"] == "high"])
        
        score_deduction = (high_severity * 20) + ((vulnerability_count - high_severity) * 10)
        security_results["security_score"] = max(0, 100 - score_deduction)
        
        return security_results
    
    async def _analyze_performance(self, file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Analyze performance-related code patterns"""
        performance_results = {
            "performance_issues": [],
            "optimization_opportunities": [],
            "performance_score": 80
        }
        
        # Performance anti-patterns
        performance_patterns = {
            'inefficient_loops': r'for.*in.*\.keys\(\)|for.*range\(len\(',
            'memory_leaks': r'global\s+\w+|setInterval|addEventListener\(',
            'blocking_operations': r'sleep\(|time\.sleep|Thread\.sleep',
            'inefficient_queries': r'SELECT \*|\.all\(\)\.filter'
        }
        
        import re
        
        for file_path, content in file_contents.items():
            for pattern_name, pattern in performance_patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    performance_results["performance_issues"].append({
                        "file": file_path,
                        "type": pattern_name,
                        "matches": len(matches)
                    })
        
        # Calculate performance score
        issue_count = len(performance_results["performance_issues"])
        score_deduction = min(50, issue_count * 5)
        performance_results["performance_score"] = max(30, 80 - score_deduction)
        
        return performance_results
    
    async def _analyze_style(self, file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Analyze code style and formatting"""
        style_results = {
            "style_issues": [],
            "consistency_score": 0,
            "style_score": 75
        }
        
        total_lines = 0
        style_violations = 0
        
        for file_path, content in file_contents.items():
            lines = content.split('\n')
            total_lines += len(lines)
            
            # Check for style issues
            for i, line in enumerate(lines):
                # Long lines
                if len(line) > 120:
                    style_violations += 1
                    style_results["style_issues"].append({
                        "file": file_path,
                        "line": i + 1,
                        "type": "long_line",
                        "severity": "low"
                    })
                
                # Trailing whitespace
                if line.endswith(' ') or line.endswith('\t'):
                    style_violations += 1
                    style_results["style_issues"].append({
                        "file": file_path,
                        "line": i + 1,
                        "type": "trailing_whitespace", 
                        "severity": "low"
                    })
        
        # Calculate style score
        if total_lines > 0:
            violation_ratio = style_violations / total_lines
            style_results["style_score"] = max(20, 100 - (violation_ratio * 1000))
        
        return style_results
    
    def _calculate_quality_metrics(self, detailed_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate aggregated quality metrics"""
        metrics = {}
        
        # Extract scores from detailed analysis
        complexity_score = detailed_analysis.get("complexity", {}).get("complexity_score", 0)
        maintainability_score = detailed_analysis.get("maintainability", {}).get("maintainability_score", 0)
        security_score = detailed_analysis.get("security", {}).get("security_score", 0)
        performance_score = detailed_analysis.get("performance", {}).get("performance_score", 0)
        style_score = detailed_analysis.get("style", {}).get("style_score", 0)
        
        metrics["complexity"] = complexity_score
        metrics["maintainability"] = maintainability_score
        metrics["security"] = security_score
        metrics["performance"] = performance_score
        metrics["style"] = style_score
        
        return metrics
    
    def _extract_issues(self, detailed_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all issues from detailed analysis"""
        issues = []
        
        # Security vulnerabilities
        security_vulns = detailed_analysis.get("security", {}).get("vulnerabilities", [])
        for vuln in security_vulns:
            issues.append({
                "type": "security",
                "severity": vuln["severity"],
                "description": f"Security vulnerability: {vuln['type']} in {vuln['file']}",
                "file": vuln["file"],
                "category": "security"
            })
        
        # Performance issues
        perf_issues = detailed_analysis.get("performance", {}).get("performance_issues", [])
        for issue in perf_issues:
            issues.append({
                "type": "performance",
                "severity": "medium",
                "description": f"Performance issue: {issue['type']} in {issue['file']}",
                "file": issue["file"],
                "category": "performance"
            })
        
        # Style issues (only high-impact ones)
        style_issues = detailed_analysis.get("style", {}).get("style_issues", [])
        for issue in style_issues[:10]:  # Limit to top 10 style issues
            issues.append({
                "type": "style",
                "severity": "low",
                "description": f"Style issue: {issue['type']} at line {issue['line']} in {issue['file']}",
                "file": issue["file"],
                "category": "style"
            })
        
        return issues
    
    def _generate_recommendations(self, detailed_analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        # Complexity recommendations
        complexity_score = detailed_analysis.get("complexity", {}).get("complexity_score", 100)
        if complexity_score < 70:
            recommendations.append("Consider refactoring complex functions and reducing cyclomatic complexity")
        
        # Maintainability recommendations
        maintainability = detailed_analysis.get("maintainability", {})
        required_files = maintainability.get("required_files", {})
        
        if not required_files.get("README.md"):
            recommendations.append("Add a comprehensive README.md file with project documentation")
        
        if not required_files.get("LICENSE"):
            recommendations.append("Add a LICENSE file to clarify usage rights")
        
        doc_ratio = maintainability.get("documentation_ratio", 0)
        if doc_ratio < 0.1:
            recommendations.append("Increase code documentation and comments for better maintainability")
        
        # Security recommendations
        security_vulns = detailed_analysis.get("security", {}).get("vulnerabilities", [])
        if security_vulns:
            recommendations.append("Address security vulnerabilities, especially those related to input validation and injection attacks")
        
        # Performance recommendations
        perf_score = detailed_analysis.get("performance", {}).get("performance_score", 100)
        if perf_score < 60:
            recommendations.append("Optimize performance bottlenecks and consider algorithmic improvements")
        
        # Style recommendations
        style_score = detailed_analysis.get("style", {}).get("style_score", 100)
        if style_score < 70:
            recommendations.append("Improve code formatting and style consistency using automated formatters")
        
        return recommendations
    
    def _calculate_overall_score(self, metrics: Dict[str, Any]) -> int:
        """Calculate weighted overall quality score"""
        weights = {
            "security": 0.25,      # 25% - Most critical
            "maintainability": 0.20,  # 20% - Long-term impact
            "complexity": 0.20,    # 20% - Code understandability
            "performance": 0.20,   # 20% - System efficiency
            "style": 0.15          # 15% - Code consistency
        }
        
        weighted_score = 0
        total_weight = 0
        
        for metric, score in metrics.items():
            if metric in weights:
                weighted_score += score * weights[metric]
                total_weight += weights[metric]
        
        if total_weight > 0:
            overall_score = weighted_score / total_weight
        else:
            overall_score = 0
        
        return round(overall_score)
