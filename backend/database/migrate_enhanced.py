"""Bootstrap missing enhanced tables/indexes, without sample records.

Existing columns/constraints are not upgraded. Use versioned migrations for that.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

INDEXES = (
    ('idx_enhanced_graph_nodes_type_depth', 'enhanced_graph_nodes', 'node_type, depth_level'),
    ('idx_enhanced_graph_edges_relationship', 'enhanced_graph_edges', 'edge_type, relationship_strength'),
    ('idx_cvss_severity_score', 'cvss_vulnerabilities', 'cvss_severity, cvss_base_score'),
    ('idx_sbom_component_type_name', 'sbom_components', 'component_type, name'),
    ('idx_spdx_package_license', 'spdx_packages', 'package_license_concluded'),
    ('idx_security_assessment_risk', 'security_assessments', 'risk_level, security_score'),
)


def create_enhanced_tables():
    from sqlalchemy import text
    from database.connection import Base, engine
    from database import models, enhanced_models
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
        for name, table, columns in INDEXES:
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})'))


def main():
    try:
        create_enhanced_tables()
    except Exception as exc:
        print(f'Enhanced schema bootstrap failed ({type(exc).__name__}). Check schema and configuration.', file=sys.stderr)
        return 1
    print('Missing enhanced tables/indexes created. No SBOM generation or sample data performed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
