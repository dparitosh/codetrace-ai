"""
Database models for CodeAce AI
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON
from sqlalchemy.sql import func
from database.connection import Base

class Repository(Base):
    """Repository analysis records"""
    __tablename__ = "repositories"
    
    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(511), nullable=False, unique=True)
    url = Column(String(511), nullable=False)
    default_branch = Column(String(255), default="main")
    language = Column(String(100))
    size = Column(Integer, default=0)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    analysis_status = Column(String(50), default="pending")
    analysis_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Analysis(Base):
    """Code analysis results"""
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, nullable=False)
    analysis_type = Column(String(100), nullable=False)  # 'quality', 'security', 'dependencies', etc.
    status = Column(String(50), default="running")  # 'running', 'completed', 'failed'
    results = Column(JSON)
    metrics = Column(JSON)
    errors = Column(Text)
    duration = Column(Integer)  # seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class File(Base):
    """File analysis records"""
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, nullable=False)
    path = Column(String(1000), nullable=False)
    filename = Column(String(255), nullable=False)
    extension = Column(String(50))
    language = Column(String(100))
    size = Column(Integer, default=0)
    lines_of_code = Column(Integer, default=0)
    complexity = Column(Integer, default=0)
    quality_score = Column(Integer, default=0)
    analysis_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Dependency(Base):
    """Dependency tracking"""
    __tablename__ = "dependencies"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(String(100))
    package_manager = Column(String(50))  # 'npm', 'pip', 'maven', etc.
    dependency_type = Column(String(50))  # 'production', 'development', 'peer'
    vulnerabilities = Column(JSON)
    license = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class QualityMetric(Base):
    """Quality metrics tracking"""
    __tablename__ = "quality_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, nullable=False)
    metric_name = Column(String(255), nullable=False)
    metric_value = Column(String(255))
    metric_type = Column(String(100))  # 'coverage', 'complexity', 'maintainability'
    threshold = Column(String(100))
    status = Column(String(50))  # 'pass', 'fail', 'warning'
    details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
