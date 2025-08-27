"""
Enhanced Database Models for Graph Data + Security Compliance (CVSS, SBOM, SPDX)
This file extends the existing models.py with enhanced capabilities
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base

# ========================================
# ENHANCED GRAPH DATA MODELS
# ========================================

class GraphAnalysis(Base):
    """Enhanced graph analysis with versioning and metadata"""
    __tablename__ = "graph_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    analysis_version = Column(String(50), default="1.0")
    graph_type = Column(String(100), nullable=False)  # 'dependency', 'traceability', 'impact'
    layout_algorithm = Column(String(100))  # 'force-directed', 'hierarchical', 'circular'
    complexity_score = Column(Float)
    total_nodes = Column(Integer, default=0)
    total_edges = Column(Integer, default=0)
    max_depth = Column(Integer, default=0)
    graph_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    nodes = relationship("EnhancedGraphNode", back_populates="graph_analysis")
    edges = relationship("EnhancedGraphEdge", back_populates="graph_analysis")

class EnhancedGraphNode(Base):
    """Enhanced graph nodes with hierarchical support"""
    __tablename__ = "enhanced_graph_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    graph_analysis_id = Column(Integer, ForeignKey("graph_analyses.id"), nullable=False)
    node_id = Column(String(255), nullable=False)
    label = Column(String(255), nullable=False)
    node_type = Column(String(100), nullable=False)  # 'file', 'function', 'class', 'module'
    
    # Hierarchical structure
    parent_node_id = Column(String(255))  # For tree structures
    depth_level = Column(Integer, default=0)
    children_count = Column(Integer, default=0)
    
    # Positioning and visualization
    x_position = Column(Float)
    y_position = Column(Float)
    z_position = Column(Float)  # For 3D graphs
    size_metric = Column(Float, default=1.0)
    color = Column(String(50))
    shape = Column(String(50), default="circle")
    
    # Code analysis data
    file_path = Column(String(1000))
    line_number = Column(Integer)
    lines_of_code = Column(Integer)
    complexity_score = Column(Float)
    maintainability_index = Column(Float)
    
    # Security and quality metrics
    security_issues = Column(JSON)  # Array of security findings
    quality_score = Column(Float)
    technical_debt_ratio = Column(Float)
    
    # Metadata and extensions
    properties = Column(JSON)  # Flexible properties
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    graph_analysis = relationship("GraphAnalysis", back_populates="nodes")

class EnhancedGraphEdge(Base):
    """Enhanced graph edges with detailed relationship types"""
    __tablename__ = "enhanced_graph_edges"
    
    id = Column(Integer, primary_key=True, index=True)
    graph_analysis_id = Column(Integer, ForeignKey("graph_analyses.id"), nullable=False)
    source_node_id = Column(String(255), nullable=False)
    target_node_id = Column(String(255), nullable=False)
    
    # Relationship details
    edge_type = Column(String(100), nullable=False)  # 'imports', 'calls', 'inherits', 'uses'
    relationship_strength = Column(Float, default=1.0)
    bidirectional = Column(Boolean, default=False)
    
    # Traceability information
    trace_type = Column(String(100))  # 'requirement', 'design', 'implementation', 'test'
    impact_level = Column(String(50))  # 'high', 'medium', 'low'
    change_frequency = Column(Integer, default=0)
    
    # Visual properties
    color = Column(String(50))
    thickness = Column(Float, default=1.0)
    style = Column(String(50), default="solid")  # 'solid', 'dashed', 'dotted'
    
    # Metadata
    properties = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    graph_analysis = relationship("GraphAnalysis", back_populates="edges")

# ========================================
# CVSS VULNERABILITY MODELS
# ========================================

class CVSSVulnerability(Base):
    """CVSS-compliant vulnerability tracking"""
    __tablename__ = "cvss_vulnerabilities"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    
    # CVE Information
    cve_id = Column(String(50), unique=True)  # CVE-2023-12345
    vulnerability_type = Column(String(100))
    description = Column(Text)
    
    # CVSS v3.1 Base Metrics
    cvss_version = Column(String(10), default="3.1")
    cvss_vector = Column(String(200))  # CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
    cvss_base_score = Column(Float)  # 0.0 - 10.0
    cvss_severity = Column(String(20))  # 'Critical', 'High', 'Medium', 'Low'
    
    # Base Metrics Components
    attack_vector = Column(String(20))  # 'Network', 'Adjacent', 'Local', 'Physical'
    attack_complexity = Column(String(20))  # 'Low', 'High'
    privileges_required = Column(String(20))  # 'None', 'Low', 'High'
    user_interaction = Column(String(20))  # 'None', 'Required'
    scope = Column(String(20))  # 'Unchanged', 'Changed'
    confidentiality_impact = Column(String(20))  # 'None', 'Low', 'High'
    integrity_impact = Column(String(20))  # 'None', 'Low', 'High'
    availability_impact = Column(String(20))  # 'None', 'Low', 'High'
    
    # Temporal Metrics (Optional)
    exploit_code_maturity = Column(String(20))
    remediation_level = Column(String(20))
    report_confidence = Column(String(20))
    temporal_score = Column(Float)
    
    # Environmental Metrics (Optional)
    environmental_score = Column(Float)
    
    # Discovery and remediation
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    patched_at = Column(DateTime(timezone=True))
    status = Column(String(50), default="open")  # 'open', 'patched', 'mitigated', 'false_positive'
    
    # Affected components
    affected_components = Column(JSON)  # List of affected files/dependencies
    remediation_guidance = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# ========================================
# SBOM (Software Bill of Materials) MODELS
# ========================================

class SBOMDocument(Base):
    """SBOM document metadata"""
    __tablename__ = "sbom_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    
    # SBOM Metadata
    sbom_format = Column(String(50), default="CycloneDX")  # 'CycloneDX', 'SPDX'
    sbom_version = Column(String(20), default="1.4")
    document_id = Column(String(255), unique=True)  # UUID or custom ID
    document_name = Column(String(255))
    document_namespace = Column(String(500))
    
    # Generation metadata
    generated_by = Column(String(255))  # Tool/person that generated SBOM
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    specification_version = Column(String(20))
    
    # Document properties
    suppliers = Column(JSON)  # List of suppliers
    authors = Column(JSON)  # List of authors
    manufacture_info = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    components = relationship("SBOMComponent", back_populates="sbom_document")

class SBOMComponent(Base):
    """SBOM component/package information"""
    __tablename__ = "sbom_components"
    
    id = Column(Integer, primary_key=True, index=True)
    sbom_document_id = Column(Integer, ForeignKey("sbom_documents.id"), nullable=False)
    
    # Component identification
    component_type = Column(String(50))  # 'library', 'framework', 'application', 'container'
    bom_ref = Column(String(255))  # Unique reference within SBOM
    supplier = Column(String(255))
    author = Column(String(255))
    publisher = Column(String(255))
    group = Column(String(255))  # Group/namespace
    name = Column(String(255), nullable=False)
    version = Column(String(100))
    description = Column(Text)
    scope = Column(String(50))  # 'required', 'optional', 'excluded'
    
    # Licensing
    license_id = Column(String(100))  # SPDX license identifier
    license_name = Column(String(255))
    license_text = Column(Text)
    license_url = Column(String(500))
    copyright_text = Column(Text)
    
    # Security and integrity
    hashes = Column(JSON)  # Hash algorithms and values
    external_references = Column(JSON)  # URLs, repositories, etc.
    properties = Column(JSON)  # Additional properties
    
    # Vulnerability association
    vulnerabilities = Column(JSON)  # Associated CVE/vulnerability IDs
    
    # Package manager specific
    package_manager = Column(String(50))  # 'npm', 'pip', 'maven', 'nuget'
    package_url = Column(String(500))  # PURL (Package URL)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    sbom_document = relationship("SBOMDocument", back_populates="components")

# ========================================
# SPDX COMPLIANCE MODELS
# ========================================

class SPDXDocument(Base):
    """SPDX document information"""
    __tablename__ = "spdx_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    
    # SPDX Document fields
    spdx_version = Column(String(20), default="SPDX-2.3")
    spdx_id = Column(String(255), unique=True)  # SPDXRef-DOCUMENT
    document_name = Column(String(255), nullable=False)
    document_namespace = Column(String(500), nullable=False, unique=True)
    creators = Column(JSON)  # List of creators (Tool, Person, Organization)
    created_at_spdx = Column(DateTime(timezone=True), server_default=func.now())
    
    # Document metadata
    license_list_version = Column(String(20))
    document_comment = Column(Text)
    external_document_refs = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    packages = relationship("SPDXPackage", back_populates="spdx_document")
    relationships = relationship("SPDXRelationship", back_populates="spdx_document")

class SPDXPackage(Base):
    """SPDX package information"""
    __tablename__ = "spdx_packages"
    
    id = Column(Integer, primary_key=True, index=True)
    spdx_document_id = Column(Integer, ForeignKey("spdx_documents.id"), nullable=False)
    
    # Package identification
    spdx_id = Column(String(255), nullable=False)  # SPDXRef-Package
    package_name = Column(String(255), nullable=False)
    package_version = Column(String(100))
    package_supplier = Column(String(255))  # NOASSERTION, Organization, Person
    package_originator = Column(String(255))
    download_location = Column(String(500))  # URL or NOASSERTION
    package_homepage = Column(String(500))
    
    # File information
    files_analyzed = Column(Boolean, default=True)
    package_verification_code = Column(String(255))
    package_checksum = Column(JSON)  # Algorithm and value pairs
    
    # Licensing
    package_license_concluded = Column(String(255))  # SPDX license expression
    package_license_info_from_files = Column(JSON)  # Array of license identifiers
    package_license_declared = Column(String(255))
    package_license_comments = Column(Text)
    package_copyright_text = Column(Text)
    
    # Additional information
    package_summary = Column(Text)
    package_description = Column(Text)
    package_comment = Column(Text)
    external_refs = Column(JSON)  # External references
    attribution_texts = Column(JSON)  # Attribution text array
    
    # Security
    security_info = Column(JSON)  # Security-related metadata
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    spdx_document = relationship("SPDXDocument", back_populates="packages")

class SPDXRelationship(Base):
    """SPDX relationships between elements"""
    __tablename__ = "spdx_relationships"
    
    id = Column(Integer, primary_key=True, index=True)
    spdx_document_id = Column(Integer, ForeignKey("spdx_documents.id"), nullable=False)
    
    # Relationship components
    element_a = Column(String(255), nullable=False)  # SPDX ID of first element
    relationship_type = Column(String(100), nullable=False)  # CONTAINS, DEPENDS_ON, etc.
    element_b = Column(String(255), nullable=False)  # SPDX ID of second element
    relationship_comment = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    spdx_document = relationship("SPDXDocument", back_populates="relationships")

# ========================================
# SECURITY ASSESSMENT MODELS
# ========================================

class SecurityAssessment(Base):
    """Comprehensive security assessment results"""
    __tablename__ = "security_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    assessment_type = Column(String(100))  # 'SAST', 'DAST', 'SCA', 'Container', 'IaC'
    
    # Assessment metadata
    scan_engine = Column(String(100))  # Tool used for scanning
    scan_version = Column(String(50))
    scan_started_at = Column(DateTime(timezone=True))
    scan_completed_at = Column(DateTime(timezone=True))
    scan_status = Column(String(50))  # 'completed', 'failed', 'partial'
    
    # Security metrics
    total_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    high_issues = Column(Integer, default=0)
    medium_issues = Column(Integer, default=0)
    low_issues = Column(Integer, default=0)
    info_issues = Column(Integer, default=0)
    
    # Risk scoring
    security_score = Column(Float)  # 0-100 security score
    risk_level = Column(String(20))  # 'Critical', 'High', 'Medium', 'Low'
    
    # Compliance status
    compliance_frameworks = Column(JSON)  # OWASP, NIST, etc.
    compliance_score = Column(Float)
    
    # Raw results
    scan_results = Column(JSON)  # Full scan results
    false_positives = Column(JSON)  # Marked false positives
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# ========================================
# LICENSE COMPLIANCE MODELS
# ========================================

class LicenseCompliance(Base):
    """License compliance tracking"""
    __tablename__ = "license_compliance"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    
    # License information
    license_spdx_id = Column(String(100))  # SPDX license identifier
    license_name = Column(String(255))
    license_category = Column(String(100))  # 'Permissive', 'Copyleft', 'Proprietary'
    license_text = Column(Text)
    license_url = Column(String(500))
    
    # Compliance status
    compliance_status = Column(String(50))  # 'compliant', 'review_required', 'non_compliant'
    risk_level = Column(String(20))  # 'High', 'Medium', 'Low'
    
    # Usage context
    usage_type = Column(String(100))  # 'direct_dependency', 'transitive', 'dev_dependency'
    commercial_use_allowed = Column(Boolean)
    modification_allowed = Column(Boolean)
    distribution_allowed = Column(Boolean)
    
    # Obligations and restrictions
    obligations = Column(JSON)  # List of license obligations
    restrictions = Column(JSON)  # List of restrictions
    
    # Review information
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
