"""Deterministic graph recommendations and explainable lexical/structural ranking.

Scores measure retrieved feature overlap, not probability or semantic equivalence.
No embeddings, model calls or inferred lifecycle assertions are produced here.
"""
import re


def tokens(value):
    value = re.sub(r'([a-z])([A-Z])', r'\1 \2', str(value))
    return set(re.findall(r'[a-z0-9]+', value.lower())) - {'the', 'and', 'file', 'function'}


def similar_resources(graph, selected_id, limit=5):
    nodes = {node['id']: node for node in graph['nodes'] if not node.get('properties', {}).get('deleted')}
    if selected_id not in nodes:
        return []
    features = {key: set() for key in nodes}
    for edge in graph['edges']:
        source, target = edge['source'], edge['target']
        relation = edge['type'].split('#')[-1].split(':')[-1]
        if relation in {'contains', 'defines', 'instanceShape', 'serviceProvider'} or source not in nodes or target not in nodes:
            continue
        features[source].add(('out', edge['type'], target))
        features[target].add(('in', edge['type'], source))
    def overlap(left, right):
        return len(left & right) / len(left | right) if left | right else 0.0
    selected = nodes[selected_id]
    query = tokens(selected['label'])
    results = []
    for key, node in nodes.items():
        if key == selected_id or node['type'] != selected['type']:
            continue
        lexical = overlap(query, tokens(node['label']))
        structural = overlap(features[selected_id], features[key])
        score = (lexical + structural) / 2
        if score:
            results.append({'node_id': key, 'label': node['label'], 'score': round(score, 4),
                            'lexical_overlap': round(lexical, 4), 'structural_overlap': round(structural, 4),
                            'method': 'label-and-directed-neighbor-jaccard'})
    return sorted(results, key=lambda item: (-item['score'], item['node_id']))[:limit]


def recommendations(graph, limit=10):
    nodes = {node['id']: node for node in graph['nodes']}
    items = []
    for key in sorted(graph.get('metadata', {}).get('coverage', {}).get('unlinked_requirements', [])):
        if key in nodes and not nodes[key].get('properties', {}).get('deleted'):
            items.append({'kind': 'trace_gap', 'node_id': key, 'message': 'Review missing explicit implementation or validation links.', 'basis': 'Imported requirement has no supported link to an active resolved resource.'})
    for connector in graph.get('metadata', {}).get('connectors', []):
        if connector.get('status') != 'ready':
            items.append({'kind': 'incomplete_provider', 'provider_id': connector['id'],
                          'message': 'Restore provider evidence before assessing coverage.', 'basis': 'Provider status is ' + connector.get('status', 'unknown')})
    return items[:limit]
