import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('evidence', Path(__file__).parents[1] / 'services/evidence_algorithms.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class EvidenceAlgorithms(unittest.TestCase):
    def graph(self):
        return {'nodes': [{'id': key, 'label': label, 'type': 'function', 'properties': {}}
                          for key, label in [('a', 'chargeCustomer'), ('b', 'charge_customer'), ('c', 'shipOrder'), ('folder', 'Folder')]],
                'edges': [{'source': 'folder', 'target': key, 'type': 'urn:codetrace:vocab:contains'} for key in ['a', 'b', 'c']],
                'metadata': {}}

    def test_shared_folder_does_not_make_resources_similar(self):
        results = evidence.similar_resources(self.graph(), 'a')
        self.assertEqual([item['node_id'] for item in results], ['b'])
        self.assertEqual(results[0]['structural_overlap'], 0)
        self.assertEqual(results[0]['lexical_overlap'], 1)

    def test_direction_and_predicate_are_part_of_structural_similarity(self):
        graph = self.graph()
        graph['edges'] += [{'source': 'a', 'target': 'folder', 'type': 'calls'}, {'source': 'b', 'target': 'folder', 'type': 'imports'}]
        self.assertEqual(evidence.similar_resources(graph, 'a')[0]['structural_overlap'], 0)

    def test_deleted_resources_are_not_recommended(self):
        graph = self.graph()
        graph['nodes'][1]['properties']['deleted'] = True
        self.assertEqual(evidence.similar_resources(graph, 'a'), [])
        graph['metadata']['coverage'] = {'unlinked_requirements': ['b']}
        self.assertEqual(evidence.recommendations(graph), [])

    def test_partial_provider_has_explicit_recommendation_basis(self):
        graph = self.graph()
        graph['metadata']['connectors'] = [{'id': 'rm', 'status': 'partial'}]
        self.assertEqual(evidence.recommendations(graph)[0]['basis'], 'Provider status is partial')


if __name__ == '__main__':
    unittest.main()
