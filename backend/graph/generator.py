"""
CodeTrace AI - Graph Generation Module
Leverages GraphTrace hierarchical graph generator for dependency visualization
"""

import json
import logging
import networkx as nx
from typing import Dict, List, Any, Tuple, Optional, Set
from pathlib import Path
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class GraphGenerator:
    """Generate hierarchical traceability and dependency graphs"""
    
    def __init__(self):
        self.supported_languages = {
            'python': {
                'import_patterns': [
                    r'import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)',
                    r'from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import',
                ],
                'function_pattern': r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                'class_pattern': r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]',
            },
            'javascript': {
                'import_patterns': [
                    r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
                    r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                    r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                ],
                'function_pattern': r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                'class_pattern': r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[{]',
            },
            'typescript': {
                'import_patterns': [
                    r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
                    r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                ],
                'function_pattern': r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                'class_pattern': r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[{]',
            },
            'java': {
                'import_patterns': [
                    r'import\s+([a-zA-Z_][a-zA-Z0-9_.]*);',
                ],
                'function_pattern': r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                'class_pattern': r'(?:public|private|protected)?\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[{]',
            }
        }
    
    async def generate_repository_graph(self, repo_data: Dict[str, Any], file_contents: Dict[str, str], 
                                      quality_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate comprehensive repository dependency and traceability graph"""
        logger.info(f"Generating repository graph for: {repo_data.get('repository', {}).get('full_name')}")
        
        try:
            # Initialize graph
            graph = nx.DiGraph()
            
            # Analyze file dependencies
            file_dependencies = await self._analyze_file_dependencies(file_contents)
            
            # Build component hierarchy
            component_hierarchy = await self._build_component_hierarchy(file_contents, file_dependencies)
            
            # Create nodes and edges
            nodes, edges = await self._create_graph_elements(component_hierarchy, file_dependencies, quality_data)
            
            # Calculate graph metrics
            graph_metrics = await self._calculate_graph_metrics(nodes, edges)
            
            # Generate layout coordinates
            layout = await self._generate_layout(nodes, edges)
            
            # Create final graph structure
            graph_data = {
                "metadata": {
                    "repository": repo_data.get("repository", {}).get("full_name"),
                    "generated_at": datetime.utcnow().isoformat(),
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "graph_type": "hierarchical_dependency"
                },
                "nodes": nodes,
                "edges": edges,
                "hierarchy": component_hierarchy,
                "metrics": graph_metrics,
                "layout": layout,
                "visualization_config": self._get_visualization_config()
            }
            
            logger.info(f"Graph generation completed. Nodes: {len(nodes)}, Edges: {len(edges)}")
            return graph_data
            
        except Exception as e:
            logger.error(f"Error generating repository graph: {e}")
            raise
    
    async def _analyze_file_dependencies(self, file_contents: Dict[str, str]) -> Dict[str, List[str]]:
        """Analyze dependencies between files"""
        dependencies = {}
        
        for file_path, content in file_contents.items():
            file_deps = []
            file_ext = Path(file_path).suffix.lower()
            
            # Determine language
            language = self._detect_language(file_ext)
            if not language:
                continue
            
            # Extract imports/dependencies
            imports = self._extract_imports(content, language)
            
            # Resolve local file dependencies
            for import_path in imports:
                resolved_path = self._resolve_import_path(import_path, file_path, file_contents.keys())
                if resolved_path:
                    file_deps.append(resolved_path)
            
            dependencies[file_path] = file_deps
        
        return dependencies
    
    def _detect_language(self, file_ext: str) -> Optional[str]:
        """Detect programming language from file extension"""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust'
        }
        return ext_to_lang.get(file_ext)
    
    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from source code"""
        imports = []
        
        if language not in self.supported_languages:
            return imports
        
        patterns = self.supported_languages[language]['import_patterns']
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)
        
        return imports
    
    def _resolve_import_path(self, import_path: str, current_file: str, all_files: Set[str]) -> Optional[str]:
        """Resolve import path to actual file path"""
        current_dir = Path(current_file).parent
        
        # Handle relative imports
        if import_path.startswith('.'):
            # Relative import
            parts = import_path.split('.')
            resolved_dir = current_dir
            
            for part in parts:
                if part == '':
                    continue
                elif part == '..':
                    resolved_dir = resolved_dir.parent
                else:
                    resolved_dir = resolved_dir / part
            
            # Try different extensions
            for ext in ['.py', '.js', '.ts', '.jsx', '.tsx']:
                candidate = str(resolved_dir) + ext
                if candidate in all_files:
                    return candidate
        
        else:
            # Absolute import - try to find matching file
            import_parts = import_path.split('.')
            
            for file_path in all_files:
                file_parts = Path(file_path).stem.split('.')
                if any(part in file_parts for part in import_parts):
                    return file_path
        
        return None
    
    async def _build_component_hierarchy(self, file_contents: Dict[str, str], 
                                       dependencies: Dict[str, List[str]]) -> Dict[str, Any]:
        """Build hierarchical component structure"""
        hierarchy = {
            "root": {
                "name": "Repository Root",
                "type": "root",
                "children": {},
                "files": [],
                "metrics": {}
            }
        }
        
        # Organize files by directory structure
        for file_path in file_contents.keys():
            path_parts = Path(file_path).parts
            current_level = hierarchy["root"]["children"]
            
            # Create directory hierarchy
            for i, part in enumerate(path_parts[:-1]):
                if part not in current_level:
                    current_level[part] = {
                        "name": part,
                        "type": "directory",
                        "children": {},
                        "files": [],
                        "metrics": {
                            "file_count": 0,
                            "dependency_count": 0,
                            "complexity_score": 0
                        }
                    }
                current_level = current_level[part]["children"]
            
            # Add file to appropriate directory
            file_name = path_parts[-1]
            parent_path = str(Path(*path_parts[:-1])) if len(path_parts) > 1 else ""
            
            # Find parent directory in hierarchy
            parent_node = hierarchy["root"]
            if parent_path:
                path_parts_parent = Path(parent_path).parts
                current = hierarchy["root"]["children"]
                for part in path_parts_parent:
                    parent_node = current[part]
                    current = parent_node["children"]
            
            # Add file info
            file_info = {
                "name": file_name,
                "path": file_path,
                "type": "file",
                "language": self._detect_language(Path(file_path).suffix.lower()),
                "dependencies": dependencies.get(file_path, []),
                "dependents": [],
                "metrics": self._calculate_file_metrics(file_contents.get(file_path, ""))
            }
            
            parent_node["files"].append(file_info)
            parent_node["metrics"]["file_count"] = len(parent_node["files"])
        
        # Calculate dependents (reverse dependencies)
        for file_path, deps in dependencies.items():
            for dep_path in deps:
                # Find dependent file and add reverse reference
                self._add_dependent(hierarchy, dep_path, file_path)
        
        # Calculate hierarchy metrics
        self._calculate_hierarchy_metrics(hierarchy["root"])
        
        return hierarchy
    
    def _add_dependent(self, hierarchy: Dict[str, Any], file_path: str, dependent_path: str):
        """Add dependent relationship to file in hierarchy"""
        # This is a simplified implementation
        # In a full implementation, you'd traverse the hierarchy to find the file
        pass
    
    def _calculate_file_metrics(self, content: str) -> Dict[str, Any]:
        """Calculate basic metrics for a file"""
        lines = content.split('\n')
        
        return {
            "line_count": len(lines),
            "non_empty_lines": len([line for line in lines if line.strip()]),
            "comment_lines": len([line for line in lines if line.strip().startswith('#') or line.strip().startswith('//')]),
            "complexity_estimate": min(100, len(lines) // 10)  # Simple heuristic
        }
    
    def _calculate_hierarchy_metrics(self, node: Dict[str, Any]):
        """Calculate metrics for hierarchy nodes recursively"""
        if node["type"] == "directory":
            total_files = len(node["files"])
            total_dependencies = sum(len(f["dependencies"]) for f in node["files"])
            
            # Recursively calculate for children
            for child in node["children"].values():
                self._calculate_hierarchy_metrics(child)
                total_files += child["metrics"].get("file_count", 0)
                total_dependencies += child["metrics"].get("dependency_count", 0)
            
            node["metrics"] = {
                "file_count": total_files,
                "dependency_count": total_dependencies,
                "complexity_score": min(100, (total_files + total_dependencies) // 5)
            }
    
    async def _create_graph_elements(self, hierarchy: Dict[str, Any], 
                                   dependencies: Dict[str, List[str]], 
                                   quality_data: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Create nodes and edges for graph visualization"""
        nodes = []
        edges = []
        node_id_counter = 0
        file_to_node_id = {}
        
        # Create nodes for files
        for file_path in dependencies.keys():
            node_id = f"file_{node_id_counter}"
            node_id_counter += 1
            file_to_node_id[file_path] = node_id
            
            # Get quality score if available
            quality_score = 100
            if quality_data and "detailed_analysis" in quality_data:
                # Extract quality score for this file (simplified)
                quality_score = quality_data.get("overall_score", 100)
            
            node = {
                "id": node_id,
                "label": Path(file_path).name,
                "type": "file",
                "file_path": file_path,
                "language": self._detect_language(Path(file_path).suffix.lower()),
                "metrics": {
                    "quality_score": quality_score,
                    "dependency_count": len(dependencies.get(file_path, [])),
                    "size": "medium"  # This would be calculated based on file size
                },
                "visualization": {
                    "color": self._get_node_color(quality_score),
                    "size": self._get_node_size(len(dependencies.get(file_path, []))),
                    "shape": "circle"
                }
            }
            nodes.append(node)
        
        # Create edges for dependencies
        edge_id_counter = 0
        for source_file, deps in dependencies.items():
            source_node_id = file_to_node_id.get(source_file)
            if not source_node_id:
                continue
                
            for dep_file in deps:
                target_node_id = file_to_node_id.get(dep_file)
                if not target_node_id:
                    continue
                
                edge = {
                    "id": f"edge_{edge_id_counter}",
                    "source": source_node_id,
                    "target": target_node_id,
                    "type": "dependency",
                    "weight": 1,
                    "visualization": {
                        "color": "#888888",
                        "width": 2,
                        "style": "solid"
                    }
                }
                edges.append(edge)
                edge_id_counter += 1
        
        return nodes, edges
    
    def _get_node_color(self, quality_score: int) -> str:
        """Get node color based on quality score"""
        if quality_score >= 80:
            return "#4CAF50"  # Green
        elif quality_score >= 60:
            return "#FFC107"  # Yellow
        elif quality_score >= 40:
            return "#FF9800"  # Orange
        else:
            return "#F44336"  # Red
    
    def _get_node_size(self, dependency_count: int) -> int:
        """Get node size based on dependency count"""
        if dependency_count <= 2:
            return 20
        elif dependency_count <= 5:
            return 30
        elif dependency_count <= 10:
            return 40
        else:
            return 50
    
    async def _calculate_graph_metrics(self, nodes: List[Dict[str, Any]], 
                                     edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate graph-level metrics"""
        
        # Basic graph metrics
        node_count = len(nodes)
        edge_count = len(edges)
        
        # Calculate degree metrics
        in_degrees = {}
        out_degrees = {}
        
        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            
            out_degrees[source] = out_degrees.get(source, 0) + 1
            in_degrees[target] = in_degrees.get(target, 0) + 1
        
        # Find highly connected nodes
        avg_in_degree = sum(in_degrees.values()) / max(len(in_degrees), 1)
        avg_out_degree = sum(out_degrees.values()) / max(len(out_degrees), 1)
        
        max_in_degree = max(in_degrees.values()) if in_degrees else 0
        max_out_degree = max(out_degrees.values()) if out_degrees else 0
        
        # Calculate complexity metrics
        cyclomatic_complexity = max(0, edge_count - node_count + 1)  # Basic estimation
        
        # Graph density
        max_possible_edges = node_count * (node_count - 1)
        density = edge_count / max_possible_edges if max_possible_edges > 0 else 0
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": round(density, 3),
            "average_in_degree": round(avg_in_degree, 2),
            "average_out_degree": round(avg_out_degree, 2),
            "max_in_degree": max_in_degree,
            "max_out_degree": max_out_degree,
            "cyclomatic_complexity": cyclomatic_complexity,
            "clustering_coefficient": 0.0,  # Would require more complex calculation
            "strongly_connected_components": 1,  # Simplified
            "graph_diameter": 0  # Would require shortest path calculation
        }
    
    async def _generate_layout(self, nodes: List[Dict[str, Any]], 
                             edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate layout coordinates for visualization"""
        
        # Use NetworkX for layout calculation
        G = nx.DiGraph()
        
        # Add nodes
        for node in nodes:
            G.add_node(node["id"])
        
        # Add edges
        for edge in edges:
            G.add_edge(edge["source"], edge["target"])
        
        # Calculate different layouts
        try:
            spring_layout = nx.spring_layout(G, k=1, iterations=50)
            circular_layout = nx.circular_layout(G)
            
            # Convert to our format
            layout_data = {
                "spring": {
                    node_id: {"x": float(pos[0]) * 1000, "y": float(pos[1]) * 1000}
                    for node_id, pos in spring_layout.items()
                },
                "circular": {
                    node_id: {"x": float(pos[0]) * 1000, "y": float(pos[1]) * 1000}
                    for node_id, pos in circular_layout.items()
                },
                "default": "spring"
            }
            
        except Exception as e:
            logger.warning(f"Error calculating layout: {e}")
            # Fallback to simple grid layout
            layout_data = self._generate_grid_layout(nodes)
        
        return layout_data
    
    def _generate_grid_layout(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate simple grid layout as fallback"""
        import math
        
        node_count = len(nodes)
        grid_size = math.ceil(math.sqrt(node_count))
        
        spring_layout = {}
        for i, node in enumerate(nodes):
            x = (i % grid_size) * 100
            y = (i // grid_size) * 100
            spring_layout[node["id"]] = {"x": x, "y": y}
        
        return {
            "spring": spring_layout,
            "circular": spring_layout,  # Same as spring for fallback
            "default": "spring"
        }
    
    def _get_visualization_config(self) -> Dict[str, Any]:
        """Get configuration for graph visualization"""
        return {
            "node_options": {
                "default_size": 30,
                "size_range": [20, 50],
                "color_scheme": "quality_based",
                "label_position": "center"
            },
            "edge_options": {
                "default_width": 2,
                "color": "#888888",
                "arrow_size": 10,
                "curve_style": "straight"
            },
            "layout_options": {
                "default_layout": "spring",
                "available_layouts": ["spring", "circular", "hierarchical"],
                "animation_duration": 1000
            },
            "interaction": {
                "zoom_enabled": True,
                "pan_enabled": True,
                "node_drag_enabled": True,
                "selection_enabled": True
            },
            "filters": {
                "quality_threshold": 0,
                "dependency_threshold": 0,
                "file_types": [],
                "show_dependencies": True
            }
        }
