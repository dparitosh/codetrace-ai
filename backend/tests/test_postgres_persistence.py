"""Optional ORM integration checks using SQLite, with no external DB mutations."""
import asyncio
from unittest.mock import patch

import pytest

sqlalchemy = pytest.importorskip('sqlalchemy')
pytest.importorskip('databases')
pytest.importorskip('psycopg2')

from sqlalchemy.orm import sessionmaker
from database.connection import Base
from database.models import Repository, Analysis, File, QualityMetric
from database.enhanced_models import GraphAnalysis, EnhancedGraphNode, EnhancedGraphEdge
from services.repository_service import RepositoryService


@pytest.fixture
def persistence():
    engine = sqlalchemy.create_engine('sqlite://')
    Base.metadata.create_all(engine)
    service = RepositoryService()
    service.Session = sessionmaker(bind=engine)
    with service.get_session() as session, session.begin():
        session.add(Repository(id=1, owner='test', name='repo', full_name='test/repo', url='urn:test:repo'))
    yield service
    engine.dispose()


def test_analysis_components_rollback_together(persistence):
    async def fail(*args):
        raise RuntimeError('simulated final component failure')
    payload = {'quality': {'metrics': {'coverage': {'value': 1}}},
               'files': [{'path': 'a.py', 'filename': 'a.py'}],
               'graph': {'nodes': [{'id': 'one', 'label': 'One'}], 'edges': []}, 'security': {}}
    with patch.object(persistence, '_save_security_assessment', side_effect=fail), pytest.raises(RuntimeError):
        asyncio.run(persistence.save_analysis_result(1, payload))
    with persistence.get_session() as session:
        for model in [Analysis, File, QualityMetric, GraphAnalysis, EnhancedGraphNode]:
            assert session.query(model).count() == 0


def test_analysis_graph_nodes_and_edges_commit_together(persistence):
    result = asyncio.run(persistence.save_analysis_result(1, {'graph': {
        'nodes': [{'id': 'one', 'label': 'One'}, {'id': 'two', 'label': 'Two'}],
        'edges': [{'source': 'one', 'target': 'two', 'type': 'calls'}]}}))
    assert result['status'] == 'completed'
    with persistence.get_session() as session:
        assert session.query(Analysis).count() == 1
        assert session.query(EnhancedGraphNode).count() == 2
        assert session.query(EnhancedGraphEdge).count() == 1


def test_graph_identity_is_scoped_and_accepts_long_unicode_ids(persistence):
    identity = 'https://alm.example/' + '\u6d4b' * 1600
    for _ in range(2):
        asyncio.run(persistence.save_analysis_result(1, {'graph': {
            'nodes': [{'id': identity, 'label': 'Long resource'}], 'edges': []}}))
    with persistence.get_session() as session:
        nodes = session.query(EnhancedGraphNode).all()
        assert len(nodes) == 2 and all(node.node_id == identity for node in nodes)
        assert all(len(node.node_key) == 64 for node in nodes)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        asyncio.run(persistence.save_analysis_result(1, {'graph': {
            'nodes': [{'id': identity}, {'id': identity}], 'edges': []}}))


def test_graph_edge_cannot_reference_another_graph(persistence):
    from sqlalchemy import event
    engine = persistence.Session.kw['bind']
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        asyncio.run(persistence.save_analysis_result(1, {'graph': {
            'nodes': [{'id': 'one'}], 'edges': [{'source': 'one', 'target': 'missing'}]}}))
    with persistence.get_session() as session:
        assert session.query(GraphAnalysis).count() == 0
