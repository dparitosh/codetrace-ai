"""Explicit, transactional PostgreSQL migrations. Never run on application boot.

Run `python backend/database/migrations.py` to inspect pending versions; back up
the database and pass --apply to apply them. PostgreSQL DDL rolls back on failure.
"""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, text

VERSION = '20261015_graph_identity'


def upgrade_graph_identity(conn):
    for table in ('enhanced_graph_nodes', 'enhanced_graph_edges'):
        if not inspect(conn).has_table(table):
            raise RuntimeError('Bootstrap missing tables before migrating existing graph data')
    conn.execute(text('ALTER TABLE enhanced_graph_nodes ALTER COLUMN node_id TYPE TEXT, ALTER COLUMN parent_node_id TYPE TEXT, ALTER COLUMN label TYPE TEXT'))
    conn.execute(text('ALTER TABLE enhanced_graph_edges ALTER COLUMN source_node_id TYPE TEXT, ALTER COLUMN target_node_id TYPE TEXT, ALTER COLUMN edge_type TYPE TEXT'))
    for table, fields in (('enhanced_graph_nodes', [('node_key', 'node_id')]),
                          ('enhanced_graph_edges', [('source_key', 'source_node_id'), ('target_key', 'target_node_id')])):
        columns = {column['name'] for column in inspect(conn).get_columns(table)}
        for key, original in fields:
            if key not in columns:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {key} VARCHAR(64)'))
            for row in conn.execute(text(f'SELECT id,{original} FROM {table}')):
                conn.execute(text(f'UPDATE {table} SET {key}=:key WHERE id=:id'),
                             {'key': hashlib.sha256(row[1].encode()).hexdigest(), 'id': row[0]})
            conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN {key} SET NOT NULL'))
    constraints = {item['name'] for item in inspect(conn).get_unique_constraints('enhanced_graph_nodes')}
    if 'uq_graph_node_identity' not in constraints:
        conn.execute(text('ALTER TABLE enhanced_graph_nodes ADD CONSTRAINT uq_graph_node_identity UNIQUE(graph_analysis_id,node_key)'))
    constraints = {item['name'] for item in inspect(conn).get_foreign_keys('enhanced_graph_edges')}
    for name, key in [('fk_graph_edge_source', 'source_key'), ('fk_graph_edge_target', 'target_key')]:
        if name not in constraints:
            conn.execute(text(f'ALTER TABLE enhanced_graph_edges ADD CONSTRAINT {name} FOREIGN KEY(graph_analysis_id,{key}) REFERENCES enhanced_graph_nodes(graph_analysis_id,node_key)'))


def migrate(engine, apply=False):
    if engine.dialect.name != 'postgresql':
        raise ValueError('This migration runner requires PostgreSQL')
    with engine.begin() as conn:
        conn.execute(text('SELECT pg_advisory_xact_lock(734029611)'))
        existing = inspect(conn).has_table('codetrace_schema_versions')
        applied = existing and conn.execute(text('SELECT 1 FROM codetrace_schema_versions WHERE version=:v'), {'v': VERSION}).scalar()
        if applied:
            return []
        if not apply:
            return [VERSION]
        conn.execute(text('CREATE TABLE IF NOT EXISTS codetrace_schema_versions(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)'))
        upgrade_graph_identity(conn)
        conn.execute(text('INSERT INTO codetrace_schema_versions(version) VALUES(:v)'), {'v': VERSION})
        return [VERSION]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from database.connection import engine
    print(('Applied: ' if args.apply else 'Pending: ') + ', '.join(migrate(engine, args.apply)))
