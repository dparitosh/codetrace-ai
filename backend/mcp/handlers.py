"""
Model Context Protocol (MCP) Handlers
Specialized handlers for different types of context requests
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from .protocol import (
    CodeContextRequest, CodeContextResponse, RepositoryContext,
    CodeSpan, CodeSymbol, QualityContext, GraphContext
)
from api.github_routes import GitHubService
from quality.validator import QualityValidator
from graph.codegraph_integration import CodeTraceGraphAnalyzer

logger = logging.getLogger(__name__)

class CodeContextHandler:
    """Handler for code-specific context requests"""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.graph_analyzer = None
        self._init_graph_analyzer()
    
    def _init_graph_analyzer(self):
        """Initialize graph analyzer if available"""
        try:
            self.graph_analyzer = CodeTraceGraphAnalyzer()
            logger.info("✅ Graph analyzer initialized")
        except Exception as e:
            logger.warning(f"⚠️ Graph analyzer not available: {e}")
            self.graph_analyzer = None
    
    async def get_code_context(self, request: CodeContextRequest) -> CodeContextResponse:
        """Get comprehensive code context"""
        try:
            # Parse repository URL
            repo_info = self._parse_repository_url(request.repository_url)
            
            # Get repository context
            repo_context = await self._get_repository_context(repo_info)
            
            # Get specific code spans
            code_spans = await self._get_code_spans(repo_info, request)
            
            # Get code symbols
            symbols = await self._get_code_symbols(repo_info, request)
            
            # Get quality context if requested
            quality = None
            if request.include_quality:
                quality = await self._get_quality_context(repo_info)
            
            # Get graph context if available
            graph = None
            if self.graph_analyzer and request.include_dependencies:
                graph = await self._get_graph_context(repo_info)
            
            return CodeContextResponse(
                repository=repo_context,
                code_spans=code_spans,
                symbols=symbols,
                quality=quality,
                graph=graph,
                metadata={
                    "request_type": request.context_type,
                    "timestamp": "2025-08-26T00:00:00Z",
                    "analyzer_available": self.graph_analyzer is not None
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting code context: {e}")
            raise
    
    async def get_file_context(self, uri: str) -> Dict[str, Any]:
        """Get context for a specific file"""
        # Parse URI: codetrace://file/{owner}/{repo}/{path}
        parts = uri.replace("codetrace://file/", "").split("/", 2)
        if len(parts) < 3:
            raise ValueError("Invalid file URI format")
        
        owner, repo, file_path = parts[0], parts[1], parts[2]
        
        try:
            # Get file content
            content = await self.github_service.get_file_content(owner, repo, file_path)
            
            # Detect language
            language = self._detect_language(file_path)
            
            # Get file-specific symbols
            symbols = await self._analyze_file_symbols(content, language, file_path)
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": f"text/{language}",
                        "text": content
                    }
                ],
                "metadata": {
                    "file_path": file_path,
                    "language": language,
                    "symbols": symbols,
                    "lines": len(content.splitlines())
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting file context: {e}")
            raise
    
    async def get_function_context(self, uri: str) -> Dict[str, Any]:
        """Get context for a specific function"""
        # Parse URI: codetrace://function/{owner}/{repo}/{function}
        parts = uri.replace("codetrace://function/", "").split("/", 2)
        if len(parts) < 3:
            raise ValueError("Invalid function URI format")
        
        owner, repo, function_name = parts[0], parts[1], parts[2]
        
        try:
            # Search for function in repository
            function_info = await self._find_function(owner, repo, function_name)
            
            if not function_info:
                raise ValueError(f"Function {function_name} not found")
            
            # Get function code with context
            file_content = await self.github_service.get_file_content(
                owner, repo, function_info["file_path"]
            )
            
            # Extract function code
            function_code = self._extract_function_code(
                file_content, function_info, context_lines=10
            )
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": function_code
                    }
                ],
                "metadata": function_info
            }
            
        except Exception as e:
            logger.error(f"Error getting function context: {e}")
            raise
    
    async def search_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for code patterns"""
        repository_url = params.get("repository_url")
        query = params.get("query")
        file_pattern = params.get("file_pattern", "**/*")
        
        repo_info = self._parse_repository_url(repository_url)
        
        try:
            # Get repository files
            files = await self.github_service.get_repository_files(
                repo_info["owner"], repo_info["repo"]
            )
            
            # Filter files by pattern
            if file_pattern != "**/*":
                files = [f for f in files if self._matches_pattern(f, file_pattern)]
            
            # Search in files
            matches = []
            for file_path in files:
                try:
                    content = await self.github_service.get_file_content(
                        repo_info["owner"], repo_info["repo"], file_path
                    )
                    
                    file_matches = self._search_in_content(content, query, file_path)
                    matches.extend(file_matches)
                    
                except Exception as e:
                    logger.warning(f"Error searching in {file_path}: {e}")
                    continue
            
            return {
                "query": query,
                "repository": repository_url,
                "total_matches": len(matches),
                "matches": matches[:50]  # Limit results
            }
            
        except Exception as e:
            logger.error(f"Error searching code: {e}")
            raise
    
    def _parse_repository_url(self, url: str) -> Dict[str, str]:
        """Parse GitHub repository URL"""
        if url.startswith("https://github.com/"):
            parts = url.replace("https://github.com/", "").split("/")
            if len(parts) >= 2:
                return {"owner": parts[0], "repo": parts[1]}
        
        raise ValueError(f"Invalid GitHub repository URL: {url}")
    
    async def _get_repository_context(self, repo_info: Dict[str, str]) -> RepositoryContext:
        """Get repository context information"""
        try:
            # Get repository metadata
            repo_data = await self.github_service.get_repository_info(
                repo_info["owner"], repo_info["repo"]
            )
            
            # Get file structure
            structure = await self.github_service.get_repository_structure(
                repo_info["owner"], repo_info["repo"]
            )
            
            # Identify key files
            key_files = self._identify_key_files(structure)
            
            return RepositoryContext(
                url=f"https://github.com/{repo_info['owner']}/{repo_info['repo']}",
                name=repo_data.get("name", repo_info["repo"]),
                description=repo_data.get("description"),
                language=repo_data.get("language", "Unknown"),
                structure=structure,
                key_files=key_files,
                dependencies=[],  # TODO: Extract from package files
                last_analyzed=None
            )
            
        except Exception as e:
            logger.error(f"Error getting repository context: {e}")
            # Return minimal context
            return RepositoryContext(
                url=f"https://github.com/{repo_info['owner']}/{repo_info['repo']}",
                name=repo_info["repo"],
                language="Unknown",
                structure={},
                key_files=[],
                dependencies=[]
            )
    
    async def _get_code_spans(self, repo_info: Dict[str, str], request: CodeContextRequest) -> List[CodeSpan]:
        """Get relevant code spans"""
        spans = []
        
        try:
            if request.file_path:
                # Get specific file
                content = await self.github_service.get_file_content(
                    repo_info["owner"], repo_info["repo"], request.file_path
                )
                
                language = self._detect_language(request.file_path)
                
                if request.function_name:
                    # Extract specific function
                    function_span = self._extract_function_span(
                        content, request.function_name, request.file_path, language
                    )
                    if function_span:
                        spans.append(function_span)
                else:
                    # Get file with limited lines
                    lines = content.splitlines()
                    max_lines = min(request.max_lines, len(lines))
                    
                    spans.append(CodeSpan(
                        file_path=request.file_path,
                        start_line=1,
                        end_line=max_lines,
                        content="\n".join(lines[:max_lines]),
                        language=language,
                        context=f"First {max_lines} lines of {request.file_path}"
                    ))
            else:
                # Get key files from repository
                key_files = await self._get_key_files(repo_info)
                
                for file_path in key_files[:5]:  # Limit to 5 files
                    try:
                        content = await self.github_service.get_file_content(
                            repo_info["owner"], repo_info["repo"], file_path
                        )
                        
                        language = self._detect_language(file_path)
                        lines = content.splitlines()
                        max_lines = min(50, len(lines))  # Limit per file
                        
                        spans.append(CodeSpan(
                            file_path=file_path,
                            start_line=1,
                            end_line=max_lines,
                            content="\n".join(lines[:max_lines]),
                            language=language,
                            context=f"Key file: {file_path}"
                        ))
                        
                    except Exception as e:
                        logger.warning(f"Error getting content for {file_path}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error getting code spans: {e}")
        
        return spans
    
    async def _get_code_symbols(self, repo_info: Dict[str, str], request: CodeContextRequest) -> List[CodeSymbol]:
        """Get code symbols (functions, classes, etc.)"""
        symbols = []
        
        try:
            if request.file_path:
                # Analyze specific file
                content = await self.github_service.get_file_content(
                    repo_info["owner"], repo_info["repo"], request.file_path
                )
                
                language = self._detect_language(request.file_path)
                file_symbols = await self._analyze_file_symbols(content, language, request.file_path)
                symbols.extend(file_symbols)
            else:
                # Analyze key files
                key_files = await self._get_key_files(repo_info)
                
                for file_path in key_files[:3]:  # Limit analysis
                    try:
                        content = await self.github_service.get_file_content(
                            repo_info["owner"], repo_info["repo"], file_path
                        )
                        
                        language = self._detect_language(file_path)
                        file_symbols = await self._analyze_file_symbols(content, language, file_path)
                        symbols.extend(file_symbols)
                        
                    except Exception as e:
                        logger.warning(f"Error analyzing symbols in {file_path}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error getting code symbols: {e}")
        
        return symbols
    
    async def _get_quality_context(self, repo_info: Dict[str, str]) -> Optional[QualityContext]:
        """Get quality context if available"""
        try:
            # This would integrate with the quality validator
            # For now, return mock data
            return QualityContext(
                overall_score=75.0,
                metrics={
                    "complexity": 68.0,
                    "maintainability": 82.0,
                    "testability": 70.0,
                    "documentation": 60.0
                },
                issues=[],
                recommendations=[
                    "Add more unit tests",
                    "Improve code documentation",
                    "Reduce cyclomatic complexity"
                ],
                complexity_metrics={
                    "cyclomatic_complexity": 15,
                    "cognitive_complexity": 12,
                    "nesting_depth": 4
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting quality context: {e}")
            return None
    
    async def _get_graph_context(self, repo_info: Dict[str, str]) -> Optional[GraphContext]:
        """Get graph context if analyzer available"""
        if not self.graph_analyzer:
            return None
        
        try:
            # This would use the graph analyzer
            # For now, return mock data
            return GraphContext(
                nodes=[
                    {"id": "main.py", "type": "file", "size": 1200},
                    {"id": "utils.py", "type": "file", "size": 800}
                ],
                edges=[
                    {"source": "main.py", "target": "utils.py", "type": "imports"}
                ],
                metrics={
                    "total_nodes": 2,
                    "total_edges": 1,
                    "density": 0.5,
                    "modularity": 0.8
                },
                clusters=[],
                dependencies={}
            )
            
        except Exception as e:
            logger.error(f"Error getting graph context: {e}")
            return None
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        extension = Path(file_path).suffix.lower()
        
        language_map = {
            ".py": "python",
            ".js": "javascript", 
            ".ts": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".html": "html",
            ".css": "css",
            ".md": "markdown",
            ".json": "json",
            ".xml": "xml",
            ".yaml": "yaml",
            ".yml": "yaml"
        }
        
        return language_map.get(extension, "text")
    
    async def _analyze_file_symbols(self, content: str, language: str, file_path: str) -> List[CodeSymbol]:
        """Analyze symbols in file content"""
        symbols = []
        
        if language == "python":
            symbols = self._analyze_python_symbols(content, file_path)
        elif language in ["javascript", "typescript"]:
            symbols = self._analyze_js_symbols(content, file_path)
        # Add more language analyzers as needed
        
        return symbols
    
    def _analyze_python_symbols(self, content: str, file_path: str) -> List[CodeSymbol]:
        """Analyze Python symbols"""
        symbols = []
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Function definitions
            if line.startswith("def "):
                func_name = line.split("(")[0].replace("def ", "").strip()
                symbols.append(CodeSymbol(
                    name=func_name,
                    type="function",
                    file_path=file_path,
                    line_number=i,
                    signature=line,
                    docstring=None,  # TODO: Extract docstring
                    dependencies=[]
                ))
            
            # Class definitions
            elif line.startswith("class "):
                class_name = line.split("(")[0].replace("class ", "").replace(":", "").strip()
                symbols.append(CodeSymbol(
                    name=class_name,
                    type="class",
                    file_path=file_path,
                    line_number=i,
                    signature=line,
                    docstring=None,
                    dependencies=[]
                ))
        
        return symbols
    
    def _analyze_js_symbols(self, content: str, file_path: str) -> List[CodeSymbol]:
        """Analyze JavaScript/TypeScript symbols"""
        symbols = []
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Function declarations
            if "function " in line and "=" not in line:
                func_name = line.split("function ")[1].split("(")[0].strip()
                symbols.append(CodeSymbol(
                    name=func_name,
                    type="function",
                    file_path=file_path,
                    line_number=i,
                    signature=line,
                    docstring=None,
                    dependencies=[]
                ))
            
            # Arrow functions
            elif "=>" in line and ("const " in line or "let " in line or "var " in line):
                func_name = line.split("=")[0].replace("const ", "").replace("let ", "").replace("var ", "").strip()
                symbols.append(CodeSymbol(
                    name=func_name,
                    type="function",
                    file_path=file_path,
                    line_number=i,
                    signature=line,
                    docstring=None,
                    dependencies=[]
                ))
        
        return symbols
    
    def _identify_key_files(self, structure: Dict[str, Any]) -> List[str]:
        """Identify key files in repository structure"""
        key_files = []
        
        def find_key_files(node, path=""):
            if isinstance(node, dict):
                for name, child in node.items():
                    current_path = f"{path}/{name}" if path else name
                    
                    # Check if it's a key file
                    if self._is_key_file(name):
                        key_files.append(current_path)
                    
                    # Recurse into directories
                    if isinstance(child, dict):
                        find_key_files(child, current_path)
        
        find_key_files(structure)
        return key_files[:20]  # Limit to 20 key files
    
    def _is_key_file(self, filename: str) -> bool:
        """Check if file is considered a key file"""
        key_patterns = [
            "main.py", "app.py", "index.js", "index.ts", "server.js",
            "package.json", "requirements.txt", "Dockerfile", "README.md",
            "setup.py", "config.py", "settings.py", "__init__.py"
        ]
        
        key_extensions = [".py", ".js", ".ts", ".java", ".go", ".rs"]
        
        return (filename in key_patterns or 
                any(filename.endswith(ext) for ext in key_extensions))
    
    async def _get_key_files(self, repo_info: Dict[str, str]) -> List[str]:
        """Get list of key files from repository"""
        try:
            structure = await self.github_service.get_repository_structure(
                repo_info["owner"], repo_info["repo"]
            )
            return self._identify_key_files(structure)
        except Exception as e:
            logger.error(f"Error getting key files: {e}")
            return []
    
    def _extract_function_span(self, content: str, function_name: str, file_path: str, language: str) -> Optional[CodeSpan]:
        """Extract function code span"""
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            if function_name in line and ("def " in line or "function " in line):
                # Found function definition
                start_line = i + 1
                
                # Find end of function (simplified)
                end_line = min(start_line + 50, len(lines))  # Limit to 50 lines
                
                function_content = "\n".join(lines[i:end_line])
                
                return CodeSpan(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    content=function_content,
                    language=language,
                    context=f"Function: {function_name}"
                )
        
        return None
    
    async def _find_function(self, owner: str, repo: str, function_name: str) -> Optional[Dict[str, Any]]:
        """Find function in repository"""
        # This would search through files to find the function
        # For now, return None
        return None
    
    def _extract_function_code(self, content: str, function_info: Dict[str, Any], context_lines: int = 10) -> str:
        """Extract function code with context"""
        # This would extract the actual function code
        # For now, return the content
        return content
    
    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file matches pattern"""
        # Simplified pattern matching
        if pattern == "**/*":
            return True
        if "*" in pattern:
            # Basic wildcard support
            return pattern.replace("*", "") in file_path
        return pattern in file_path
    
    def _search_in_content(self, content: str, query: str, file_path: str) -> List[Dict[str, Any]]:
        """Search for query in content"""
        matches = []
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            if query.lower() in line.lower():
                matches.append({
                    "file_path": file_path,
                    "line_number": i,
                    "line_content": line.strip(),
                    "context": {
                        "before": lines[max(0, i-2):i-1] if i > 1 else [],
                        "after": lines[i:min(len(lines), i+2)] if i < len(lines) else []
                    }
                })
        
        return matches


class RepositoryHandler:
    """Handler for repository-level context requests"""
    
    def __init__(self):
        self.github_service = GitHubService()
    
    async def get_repository_context(self, uri: str) -> Dict[str, Any]:
        """Get repository context from URI"""
        # Parse URI: codetrace://repository/{owner}/{repo}
        parts = uri.replace("codetrace://repository/", "").split("/")
        if len(parts) < 2:
            raise ValueError("Invalid repository URI format")
        
        owner, repo = parts[0], parts[1]
        return await self.analyze_repository({"repository_url": f"https://github.com/{owner}/{repo}"})
    
    async def analyze_repository(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze repository comprehensively"""
        repository_url = params.get("repository_url")
        include_quality = params.get("include_quality", True)
        include_dependencies = params.get("include_dependencies", True)
        
        # Parse repository URL
        if repository_url.startswith("https://github.com/"):
            parts = repository_url.replace("https://github.com/", "").split("/")
            owner, repo = parts[0], parts[1]
        else:
            raise ValueError("Invalid GitHub repository URL")
        
        try:
            # Get basic repository info
            repo_info = await self.github_service.get_repository_info(owner, repo)
            
            # Get file structure
            structure = await self.github_service.get_repository_structure(owner, repo)
            
            # Get file statistics
            file_stats = self._analyze_file_structure(structure)
            
            # Get languages
            languages = await self.github_service.get_repository_languages(owner, repo)
            
            result = {
                "repository": {
                    "url": repository_url,
                    "name": repo_info.get("name", repo),
                    "description": repo_info.get("description"),
                    "language": repo_info.get("language"),
                    "languages": languages,
                    "size": repo_info.get("size", 0),
                    "stars": repo_info.get("stargazers_count", 0),
                    "forks": repo_info.get("forks_count", 0)
                },
                "structure": {
                    "total_files": file_stats["total_files"],
                    "directories": file_stats["directories"],
                    "file_types": file_stats["file_types"],
                    "key_files": file_stats["key_files"]
                },
                "analysis_metadata": {
                    "analyzed_at": "2025-08-26T00:00:00Z",
                    "analyzer_version": "1.0.0"
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            raise
    
    async def get_dependency_graph(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get dependency graph for repository"""
        repository_url = params.get("repository_url")
        
        # This would integrate with the graph analyzer
        # For now, return mock data
        return {
            "repository": repository_url,
            "graph": {
                "nodes": [],
                "edges": [],
                "metrics": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "complexity": 0
                }
            }
        }
    
    async def get_graph_context(self, uri: str) -> Dict[str, Any]:
        """Get graph context from URI"""
        # Parse URI: codetrace://graph/{owner}/{repo}
        parts = uri.replace("codetrace://graph/", "").split("/")
        if len(parts) < 2:
            raise ValueError("Invalid graph URI format")
        
        owner, repo = parts[0], parts[1]
        return await self.get_dependency_graph({
            "repository_url": f"https://github.com/{owner}/{repo}"
        })
    
    def _analyze_file_structure(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze file structure statistics"""
        stats = {
            "total_files": 0,
            "directories": 0,
            "file_types": {},
            "key_files": []
        }
        
        def analyze_node(node, path=""):
            if isinstance(node, dict):
                stats["directories"] += 1
                for name, child in node.items():
                    current_path = f"{path}/{name}" if path else name
                    analyze_node(child, current_path)
            else:
                # It's a file
                stats["total_files"] += 1
                
                # Get file extension
                if "." in path:
                    ext = path.split(".")[-1].lower()
                    stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1
                
                # Check if it's a key file
                filename = path.split("/")[-1]
                if self._is_key_file(filename):
                    stats["key_files"].append(path)
        
        analyze_node(structure)
        return stats
    
    def _is_key_file(self, filename: str) -> bool:
        """Check if file is considered a key file"""
        key_patterns = [
            "main.py", "app.py", "index.js", "index.ts", "server.js",
            "package.json", "requirements.txt", "Dockerfile", "README.md",
            "setup.py", "config.py", "settings.py"
        ]
        return filename in key_patterns


class QualityHandler:
    """Handler for quality-related context requests"""
    
    def __init__(self):
        self.quality_validator = None
        self._init_quality_validator()
    
    def _init_quality_validator(self):
        """Initialize quality validator if available"""
        try:
            self.quality_validator = QualityValidator()
            logger.info("✅ Quality validator initialized")
        except Exception as e:
            logger.warning(f"⚠️ Quality validator not available: {e}")
    
    async def get_quality_context(self, uri: str) -> Dict[str, Any]:
        """Get quality context from URI"""
        # Parse URI: codetrace://quality/{owner}/{repo}
        parts = uri.replace("codetrace://quality/", "").split("/")
        if len(parts) < 2:
            raise ValueError("Invalid quality URI format")
        
        owner, repo = parts[0], parts[1]
        return await self.get_quality_metrics({
            "repository_url": f"https://github.com/{owner}/{repo}"
        })
    
    async def get_quality_metrics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get quality metrics for repository"""
        repository_url = params.get("repository_url")
        
        # For now, return mock quality data
        # This would integrate with the actual quality validator
        return {
            "repository": repository_url,
            "quality": {
                "overall_score": 75.0,
                "metrics": {
                    "complexity": 68.0,
                    "maintainability": 82.0,
                    "testability": 70.0,
                    "documentation": 60.0,
                    "performance": 78.0
                },
                "issues": [
                    {
                        "type": "complexity",
                        "severity": "medium",
                        "message": "High cyclomatic complexity in main.py",
                        "file": "main.py",
                        "line": 45
                    }
                ],
                "recommendations": [
                    "Add more unit tests to improve testability",
                    "Improve inline documentation",
                    "Refactor complex functions to reduce complexity"
                ]
            },
            "analysis_metadata": {
                "analyzed_at": "2025-08-26T00:00:00Z",
                "validator_available": self.quality_validator is not None
            }
        }
