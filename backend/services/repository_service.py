"""
Repository Service - Handles persistence of repository analysis data
Provides database operations for repositories, analyses, and results
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, delete
import json
import logging

from database.connection import engine
from database.models import Repository, Analysis, File, Dependency, QualityMetric
from database.enhanced_models import (
    GraphAnalysis, EnhancedGraphNode, EnhancedGraphEdge,
    CVSSVulnerability, SBOMDocument, SBOMComponent,
    SPDXDocument, SPDXPackage, SecurityAssessment
)

logger = logging.getLogger(__name__)

class RepositoryService:
    """Service for repository data persistence and retrieval"""
    
    def __init__(self):
        self.Session = sessionmaker(bind=engine)
        
    def get_session(self):
        """Get database session"""
        return self.Session()
    
    # ==========================================
    # REPOSITORY MANAGEMENT
    # ==========================================
    
    async def save_repository(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update repository information"""
        try:
            with self.get_session() as session:
                # Check if repository exists
                existing_repo = session.query(Repository).filter(
                    Repository.full_name == repo_data.get('full_name')
                ).first()
                
                if existing_repo:
                    # Update existing repository
                    for key, value in repo_data.items():
                        if hasattr(existing_repo, key) and value is not None:
                            setattr(existing_repo, key, value)
                    existing_repo.updated_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Updated repository: {repo_data.get('full_name')}")
                    return self._repository_to_dict(existing_repo)
                else:
                    # Create new repository
                    repo = Repository(
                        owner=repo_data.get('owner'),
                        name=repo_data.get('name'),
                        full_name=repo_data.get('full_name'),
                        url=repo_data.get('url', ''),
                        default_branch=repo_data.get('default_branch', 'main'),
                        language=repo_data.get('language'),
                        size=repo_data.get('size', 0),
                        stars=repo_data.get('stars', 0),
                        forks=repo_data.get('forks', 0),
                        analysis_status='pending',
                        analysis_data=repo_data.get('metadata', {})
                    )
                    session.add(repo)
                    session.commit()
                    session.refresh(repo)
                    logger.info(f"Created new repository: {repo_data.get('full_name')}")
                    return self._repository_to_dict(repo)
                    
        except Exception as e:
            logger.error(f"Error saving repository {repo_data.get('full_name')}: {e}")
            raise
    
    async def get_repository(self, owner: str, name: str) -> Optional[Dict[str, Any]]:
        """Get repository by owner and name"""
        try:
            with self.get_session() as session:
                repo = session.query(Repository).filter(
                    Repository.owner == owner,
                    Repository.name == name
                ).first()
                
                if repo:
                    return self._repository_to_dict(repo)
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving repository {owner}/{name}: {e}")
            raise
    
    async def get_repositories(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get list of repositories with pagination"""
        try:
            with self.get_session() as session:
                repos = session.query(Repository).offset(offset).limit(limit).all()
                return [self._repository_to_dict(repo) for repo in repos]
                
        except Exception as e:
            logger.error(f"Error retrieving repositories: {e}")
            raise
    
    async def update_repository_status(self, repo_id: int, status: str, analysis_data: Dict = None):
        """Update repository analysis status"""
        try:
            with self.get_session() as session:
                repo = session.query(Repository).filter(Repository.id == repo_id).first()
                if repo:
                    repo.analysis_status = status
                    if analysis_data:
                        repo.analysis_data = analysis_data
                    repo.updated_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Updated repository status: {repo.full_name} -> {status}")
                    
        except Exception as e:
            logger.error(f"Error updating repository status: {e}")
            raise
    
    # ==========================================
    # ANALYSIS MANAGEMENT
    # ==========================================
    
    async def save_analysis_result(self, repo_id: int, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save comprehensive analysis results"""
        try:
            with self.get_session() as session:
                analysis = Analysis(
                    repository_id=repo_id,
                    analysis_type=analysis_data.get('type', 'comprehensive'),
                    status='completed',
                    results=analysis_data.get('results', {}),
                    metrics=analysis_data.get('metrics', {}),
                    duration=analysis_data.get('duration', 0)
                )
                session.add(analysis)
                session.commit()
                session.refresh(analysis)
                
                # Save individual components
                await self._save_analysis_components(session, repo_id, analysis.id, analysis_data)
                
                logger.info(f"Saved analysis result for repository ID: {repo_id}")
                return self._analysis_to_dict(analysis)
                
        except Exception as e:
            logger.error(f"Error saving analysis result: {e}")
            raise
    
    async def _save_analysis_components(self, session, repo_id: int, analysis_id: int, data: Dict):
        """Save detailed analysis components"""
        try:
            # Save quality assessment
            if 'quality' in data:
                await self._save_quality_metrics(session, repo_id, data['quality'])
            
            # Save file analysis
            if 'files' in data:
                await self._save_file_analysis(session, repo_id, data['files'])
            
            # Save dependencies
            if 'dependencies' in data:
                await self._save_dependencies(session, repo_id, data['dependencies'])
            
            # Save graph data
            if 'graph' in data:
                await self._save_graph_analysis(session, repo_id, data['graph'])
            
            # Save security assessment
            if 'security' in data:
                await self._save_security_assessment(session, repo_id, data['security'])
                
        except Exception as e:
            logger.error(f"Error saving analysis components: {e}")
            raise
    
    async def _save_quality_metrics(self, session, repo_id: int, quality_data: Dict):
        """Save quality metrics"""
        try:
            metrics = quality_data.get('metrics', {})
            for metric_name, metric_info in metrics.items():
                quality_metric = QualityMetric(
                    repository_id=repo_id,
                    metric_name=metric_name,
                    metric_value=str(metric_info.get('value', '')),
                    metric_type=metric_info.get('type', 'unknown'),
                    threshold=str(metric_info.get('threshold', '')),
                    status=metric_info.get('status', 'unknown'),
                    details=metric_info
                )
                session.add(quality_metric)
            session.commit()
            
        except Exception as e:
            logger.error(f"Error saving quality metrics: {e}")
            raise
    
    async def _save_file_analysis(self, session, repo_id: int, files_data: List[Dict]):
        """Save file analysis data"""
        try:
            for file_info in files_data:
                file_record = File(
                    repository_id=repo_id,
                    path=file_info.get('path', ''),
                    filename=file_info.get('filename', ''),
                    extension=file_info.get('extension', ''),
                    language=file_info.get('language', ''),
                    size=file_info.get('size', 0),
                    lines_of_code=file_info.get('lines_of_code', 0),
                    complexity=file_info.get('complexity', 0),
                    quality_score=file_info.get('quality_score', 0),
                    analysis_data=file_info
                )
                session.add(file_record)
            session.commit()
            
        except Exception as e:
            logger.error(f"Error saving file analysis: {e}")
            raise
    
    async def _save_dependencies(self, session, repo_id: int, deps_data: List[Dict]):
        """Save dependency information"""
        try:
            for dep_info in deps_data:
                dependency = Dependency(
                    repository_id=repo_id,
                    name=dep_info.get('name', ''),
                    version=dep_info.get('version', ''),
                    package_manager=dep_info.get('package_manager', ''),
                    dependency_type=dep_info.get('type', 'production'),
                    vulnerabilities=dep_info.get('vulnerabilities', []),
                    license=dep_info.get('license', '')
                )
                session.add(dependency)
            session.commit()
            
        except Exception as e:
            logger.error(f"Error saving dependencies: {e}")
            raise
    
    async def _save_graph_analysis(self, session, repo_id: int, graph_data: Dict):
        """Save enhanced graph analysis data"""
        try:
            # Create graph analysis record
            graph_analysis = GraphAnalysis(
                repository_id=repo_id,
                graph_type=graph_data.get('type', 'traceability'),
                layout_algorithm=graph_data.get('layout', 'force-directed'),
                complexity_score=graph_data.get('complexity_score', 0.0),
                total_nodes=len(graph_data.get('nodes', [])),
                total_edges=len(graph_data.get('edges', [])),
                max_depth=graph_data.get('max_depth', 0),
                graph_metadata=graph_data.get('metadata', {})
            )
            session.add(graph_analysis)
            session.commit()
            session.refresh(graph_analysis)
            
            # Save nodes
            for node_data in graph_data.get('nodes', []):
                node = EnhancedGraphNode(
                    graph_analysis_id=graph_analysis.id,
                    node_id=node_data.get('id', ''),
                    label=node_data.get('label', ''),
                    node_type=node_data.get('type', 'unknown'),
                    file_path=node_data.get('file_path', ''),
                    x_position=node_data.get('x', 0.0),
                    y_position=node_data.get('y', 0.0),
                    size_metric=node_data.get('size', 1.0),
                    color=node_data.get('color', '#000000'),
                    properties=node_data
                )
                session.add(node)
            
            # Save edges
            for edge_data in graph_data.get('edges', []):
                edge = EnhancedGraphEdge(
                    graph_analysis_id=graph_analysis.id,
                    source_node_id=edge_data.get('source', ''),
                    target_node_id=edge_data.get('target', ''),
                    edge_type=edge_data.get('type', 'unknown'),
                    relationship_strength=edge_data.get('strength', 1.0),
                    color=edge_data.get('color', '#666666'),
                    properties=edge_data
                )
                session.add(edge)
            
            session.commit()
            
        except Exception as e:
            logger.error(f"Error saving graph analysis: {e}")
            raise
    
    async def _save_security_assessment(self, session, repo_id: int, security_data: Dict):
        """Save security assessment data"""
        try:
            assessment = SecurityAssessment(
                repository_id=repo_id,
                assessment_type=security_data.get('type', 'comprehensive'),
                scan_engine=security_data.get('scan_engine', 'codetrace-ai'),
                scan_status='completed',
                total_issues=security_data.get('total_issues', 0),
                critical_issues=security_data.get('critical_issues', 0),
                high_issues=security_data.get('high_issues', 0),
                medium_issues=security_data.get('medium_issues', 0),
                low_issues=security_data.get('low_issues', 0),
                security_score=security_data.get('security_score', 0.0),
                risk_level=security_data.get('risk_level', 'Unknown'),
                scan_results=security_data
            )
            session.add(assessment)
            session.commit()
            
        except Exception as e:
            logger.error(f"Error saving security assessment: {e}")
            raise
    
    # ==========================================
    # DATA RETRIEVAL
    # ==========================================
    
    async def get_analysis_history(self, repo_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get analysis history for a repository"""
        try:
            with self.get_session() as session:
                analyses = session.query(Analysis).filter(
                    Analysis.repository_id == repo_id
                ).order_by(Analysis.created_at.desc()).limit(limit).all()
                
                return [self._analysis_to_dict(analysis) for analysis in analyses]
                
        except Exception as e:
            logger.error(f"Error retrieving analysis history: {e}")
            raise
    
    async def get_latest_analysis(self, repo_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest analysis for a repository"""
        try:
            with self.get_session() as session:
                analysis = session.query(Analysis).filter(
                    Analysis.repository_id == repo_id
                ).order_by(Analysis.created_at.desc()).first()
                
                if analysis:
                    return self._analysis_to_dict(analysis)
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving latest analysis: {e}")
            raise
    
    async def get_repository_metrics(self, repo_id: int) -> Dict[str, Any]:
        """Get comprehensive repository metrics"""
        try:
            with self.get_session() as session:
                # Get quality metrics
                quality_metrics = session.query(QualityMetric).filter(
                    QualityMetric.repository_id == repo_id
                ).all()
                
                # Get latest security assessment
                security_assessment = session.query(SecurityAssessment).filter(
                    SecurityAssessment.repository_id == repo_id
                ).order_by(SecurityAssessment.created_at.desc()).first()
                
                # Get dependency count
                dependency_count = session.query(Dependency).filter(
                    Dependency.repository_id == repo_id
                ).count()
                
                # Get file analysis count
                file_count = session.query(File).filter(
                    File.repository_id == repo_id
                ).count()
                
                return {
                    'quality_metrics': [self._quality_metric_to_dict(qm) for qm in quality_metrics],
                    'security_assessment': self._security_assessment_to_dict(security_assessment) if security_assessment else None,
                    'dependency_count': dependency_count,
                    'file_count': file_count,
                    'last_updated': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error retrieving repository metrics: {e}")
            raise
    
    # ==========================================
    # UTILITY METHODS
    # ==========================================
    
    def _repository_to_dict(self, repo: Repository) -> Dict[str, Any]:
        """Convert repository model to dictionary"""
        return {
            'id': repo.id,
            'owner': repo.owner,
            'name': repo.name,
            'full_name': repo.full_name,
            'url': repo.url,
            'default_branch': repo.default_branch,
            'language': repo.language,
            'size': repo.size,
            'stars': repo.stars,
            'forks': repo.forks,
            'analysis_status': repo.analysis_status,
            'analysis_data': repo.analysis_data,
            'created_at': repo.created_at.isoformat() if repo.created_at else None,
            'updated_at': repo.updated_at.isoformat() if repo.updated_at else None
        }
    
    def _analysis_to_dict(self, analysis: Analysis) -> Dict[str, Any]:
        """Convert analysis model to dictionary"""
        return {
            'id': analysis.id,
            'repository_id': analysis.repository_id,
            'analysis_type': analysis.analysis_type,
            'status': analysis.status,
            'results': analysis.results,
            'metrics': analysis.metrics,
            'errors': analysis.errors,
            'duration': analysis.duration,
            'created_at': analysis.created_at.isoformat() if analysis.created_at else None,
            'updated_at': analysis.updated_at.isoformat() if analysis.updated_at else None
        }
    
    def _quality_metric_to_dict(self, metric: QualityMetric) -> Dict[str, Any]:
        """Convert quality metric model to dictionary"""
        return {
            'id': metric.id,
            'metric_name': metric.metric_name,
            'metric_value': metric.metric_value,
            'metric_type': metric.metric_type,
            'threshold': metric.threshold,
            'status': metric.status,
            'details': metric.details,
            'created_at': metric.created_at.isoformat() if metric.created_at else None
        }
    
    def _security_assessment_to_dict(self, assessment: SecurityAssessment) -> Dict[str, Any]:
        """Convert security assessment model to dictionary"""
        return {
            'id': assessment.id,
            'assessment_type': assessment.assessment_type,
            'scan_engine': assessment.scan_engine,
            'scan_status': assessment.scan_status,
            'total_issues': assessment.total_issues,
            'critical_issues': assessment.critical_issues,
            'high_issues': assessment.high_issues,
            'medium_issues': assessment.medium_issues,
            'low_issues': assessment.low_issues,
            'security_score': assessment.security_score,
            'risk_level': assessment.risk_level,
            'created_at': assessment.created_at.isoformat() if assessment.created_at else None
        }

# Global service instance
repository_service = RepositoryService()
