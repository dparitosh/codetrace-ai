"""
Database migration script to add enhanced graph data and security compliance capabilities
This includes CVSS, SBOM, SPDX support
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text, create_engine
from core.config import settings
from database.connection import Base, engine
from database.enhanced_models import *

def create_enhanced_tables():
    """Create all enhanced database tables"""
    try:
        # Import enhanced models to register them with Base
        from database.enhanced_models import (
            GraphAnalysis, EnhancedGraphNode, EnhancedGraphEdge,
            CVSSVulnerability, SBOMDocument, SBOMComponent,
            SPDXDocument, SPDXPackage, SPDXRelationship,
            SecurityAssessment, LicenseCompliance
        )
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Enhanced database tables created successfully")
        
        # Create additional indexes for performance
        with engine.connect() as conn:
            # Graph performance indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enhanced_graph_nodes_type_depth 
                ON enhanced_graph_nodes(node_type, depth_level);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_enhanced_graph_edges_relationship 
                ON enhanced_graph_edges(edge_type, relationship_strength);
            """))
            
            # CVSS indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cvss_severity_score 
                ON cvss_vulnerabilities(cvss_severity, cvss_base_score);
            """))
            
            # SBOM indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sbom_component_type_name 
                ON sbom_components(component_type, name);
            """))
            
            # SPDX indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_spdx_package_license 
                ON spdx_packages(package_license_concluded);
            """))
            
            # Security assessment indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_security_assessment_risk 
                ON security_assessments(risk_level, security_score);
            """))
            
            conn.commit()
            print("✅ Performance indexes created successfully")
            
    except Exception as e:
        print(f"❌ Error creating enhanced tables: {e}")
        raise

def create_sample_data():
    """Create sample data for testing"""
    try:
        with engine.connect() as conn:
            # Sample CVSS vulnerability
            conn.execute(text("""
                INSERT INTO cvss_vulnerabilities (
                    repository_id, cve_id, vulnerability_type, description,
                    cvss_version, cvss_vector, cvss_base_score, cvss_severity,
                    attack_vector, attack_complexity, privileges_required,
                    user_interaction, scope, confidentiality_impact,
                    integrity_impact, availability_impact, status
                ) VALUES (
                    1, 'CVE-2023-12345', 'Cross-Site Scripting (XSS)',
                    'Stored XSS vulnerability in user input validation',
                    '3.1', 'CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N',
                    5.4, 'Medium', 'Network', 'Low', 'Low', 'Required',
                    'Changed', 'Low', 'Low', 'None', 'open'
                ) ON CONFLICT DO NOTHING;
            """))
            
            # Sample SBOM document
            conn.execute(text("""
                INSERT INTO sbom_documents (
                    repository_id, sbom_format, sbom_version, document_id,
                    document_name, document_namespace, generated_by,
                    specification_version
                ) VALUES (
                    1, 'CycloneDX', '1.4', 'urn:uuid:3e671687-395b-41f5-a30f-a58921a69b79',
                    'CodeTrace AI SBOM', 'https://codetrace.ai/sbom/v1',
                    'CodeTrace AI Scanner v1.0', '1.4'
                ) ON CONFLICT DO NOTHING;
            """))
            
            # Sample SPDX document
            conn.execute(text("""
                INSERT INTO spdx_documents (
                    repository_id, spdx_version, spdx_id, document_name,
                    document_namespace, creators, license_list_version
                ) VALUES (
                    1, 'SPDX-2.3', 'SPDXRef-DOCUMENT', 'CodeTrace AI SPDX Document',
                    'https://codetrace.ai/spdx/v1', 
                    '["Tool: CodeTrace AI Scanner", "Organization: CodeTrace AI"]',
                    '3.18'
                ) ON CONFLICT DO NOTHING;
            """))
            
            conn.commit()
            print("✅ Sample data created successfully")
            
    except Exception as e:
        print(f"⚠️ Warning: Could not create sample data: {e}")

async def migrate_enhanced_schema():
    """Main migration function"""
    print("🚀 Starting enhanced schema migration...")
    print("📊 Adding support for:")
    print("   - Enhanced Graph Data Management")
    print("   - CVSS Vulnerability Tracking")  
    print("   - SBOM (Software Bill of Materials)")
    print("   - SPDX Compliance")
    print("   - Security Assessment Framework")
    print("   - License Compliance Tracking")
    
    try:
        # Create enhanced tables
        create_enhanced_tables()
        
        # Create sample data
        create_sample_data()
        
        print("\n✅ Enhanced schema migration completed successfully!")
        print("\n📋 New Capabilities Available:")
        print("   ✅ Hierarchical graph structures")
        print("   ✅ CVSS v3.1 vulnerability scoring")
        print("   ✅ CycloneDX/SPDX SBOM generation")
        print("   ✅ SPDX 2.3 compliance tracking")
        print("   ✅ Comprehensive security assessments")
        print("   ✅ License compliance management")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate_enhanced_schema())
