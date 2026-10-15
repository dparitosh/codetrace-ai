"""Dependency-free regression checks of query parsing and evidence projection."""
import ast
import json
from pathlib import Path
import re
import unittest
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]

def load_function(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    function.decorator_list = []
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]

class ClientError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code

class SearchReviewContract(unittest.TestCase):
    def test_invalid_title_literal_returns_client_error(self):
        namespace = {'Query': lambda *args, **kwargs: None, 'Optional': Optional, 'Request': object,
                     'server_auth': lambda request: None,
                     'settings': type('Settings', (), {'MANAGED_REPOSITORIES': [type('Repository', (), {'id': 'demo'})() ]})(),
                     'HTTPException': ClientError, 're': re, 'json': json}
        query = load_function('api/oslc_routes.py', 'query_resources', namespace)
        with self.assertRaises(ClientError) as caught:
            query('demo', object(), 1, 50, r'dcterms:title="bad\q"')
        self.assertEqual(caught.exception.status_code, 400)

    def test_evidence_preserves_bounded_allowlisted_properties(self):
        namespace = {'re': re, 'settings': type('Settings', (), {'AI_CONTEXT_NODES': 35, 'AI_CONTEXT_RELATIONS': 80})()}
        retrieve = load_function('services/companion_service.py', 'context_evidence', namespace)
        graph = {'nodes': [{'id': 'test', 'label': 'Verification', 'type': 'test_result',
                            'properties': {'domain': 'QM', 'outcome': 'failed', 'deleted': True,
                                           'status': 'closed', 'description': 'x' * 5000, 'token': 'secret'}}],
                 'edges': [], 'metadata': {}}
        citations, _ = retrieve(graph, 'Explain this resource', 'test')
        properties = citations[0]['properties']
        self.assertEqual(properties['outcome'], 'failed')
        self.assertTrue(properties['deleted'])
        self.assertEqual(properties['status'], 'closed')
        self.assertEqual(len(properties['description']), 2000)
        self.assertNotIn('token', properties)

if __name__ == '__main__':
    unittest.main()
