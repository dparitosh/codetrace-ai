"""Materialize code facts and explicit lifecycle assertions in one NetworkX KG.

No remote URI is dereferenced. OSLC assertions remain directed and retain their
predicate URIs; product-line relationships use a separate application vocabulary.
"""

import hashlib
import json
from collections import deque
from pathlib import PurePosixPath
from uuid import NAMESPACE_URL, uuid5

import networkx as nx

CT = 'urn:codetrace:vocab:'
RM = 'http://open-services.net/ns/rm#'
QM = 'http://open-services.net/ns/qm#'
RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
RDFS = 'http://www.w3.org/2000/01/rdf-schema#'
TYPE_URIS = {'requirement': RM + 'Requirement', 'test': QM + 'TestCase'}


def code_uri(repository_uri, code_id):
    """Stable within a repository across revisions, isolated across repositories."""
    return 'urn:codetrace:code:' + str(uuid5(NAMESPACE_URL, repository_uri + '\n' + code_id))


def materialize(code_graph, manifest, source_digest):
    repository = manifest['repository']
    repo_uri = repository['uri']
    graph = nx.MultiDiGraph()
    diagnostics = []
    provenance = {'origin': 'code_analyzer', 'repository_uri': repo_uri,
                  'revision': repository.get('revision'), 'source_digest': source_digest}
    graph.add_node(repo_uri, label=repository['label'], type='repository', properties=provenance)
    original = {node['id']: node for node in code_graph['nodes']}
    identities = {key: code_uri(repo_uri, key) for key in original}

    def edge(source, target, predicate, properties):
        # An identical assertion is idempotent, but evidence from another source
        # remains a separate multigraph edge.
        key = hashlib.sha256(json.dumps([source, target, predicate, properties], sort_keys=True).encode()).hexdigest()
        graph.add_edge(source, target, key=key, type=predicate, properties=properties)

    def package(path):
        uri = code_uri(repo_uri, 'package:' + path)
        if uri not in graph:
            graph.add_node(uri, label=path, type='package', properties={**provenance, 'path': path, 'classification': 'directory'})
            parent = repo_uri if path == '.' else package(PurePosixPath(path).parent.as_posix())
            edge(parent, uri, CT + 'contains', provenance)
        return uri

    for node in code_graph['nodes']:
        props = dict(node['properties'])
        kind = node['type']
        if kind == 'function' and original.get(props.get('owner'), {}).get('type') == 'class':
            kind = 'method'
        if props.get('owner') in identities:
            props['owner'] = identities[props['owner']]
        graph.add_node(identities[node['id']], label=node['label'], type=kind,
                       properties={**props, **provenance, 'code_id': node['id'],
                                   'extraction': 'python_ast' if props.get('language') == 'python' else 'structural_or_heuristic'})
        if kind == 'file':
            parent = package(PurePosixPath(props['path']).parent.as_posix())
            edge(parent, identities[node['id']], CT + 'contains', provenance)
    for item in code_graph['edges']:
        predicate = CT + ('contains' if item['type'] == 'defines' else item['type'])
        edge(identities[item['source']], identities[item['target']], predicate,
             {**item['properties'], **provenance})

    for resource in manifest.get('resources', []):
        uri = resource['uri']
        if uri in graph:
            raise ValueError('Lifecycle resource URI conflicts with code/repository identity: ' + uri)
        graph.add_node(uri, label=resource['label'], type=resource['kind'], properties={
            'origin': 'lifecycle_import', 'provider_uri': resource.get('provider_uri'),
            'configuration_uri': manifest.get('configuration_uri'),
        })

    def resolve(endpoint):
        if endpoint.get('code_id') is not None:
            key = endpoint['code_id']
            if key not in identities:
                raise ValueError('Unknown code_id: ' + key)
            return identities[key]
        uri = endpoint['uri']
        if uri not in graph:
            graph.add_node(uri, label=uri, type='external_resource', properties={'origin': 'lifecycle_import', 'resolved': False})
            diagnostics.append({'kind': 'unresolved_resource', 'uri': uri})
        return uri

    for link in manifest.get('links', []):
        source, target = resolve(link['source']), resolve(link['target'])
        edge(source, target, link['predicate'], {
            'origin': 'lifecycle_assertion', 'asserted_by': link['asserted_by'],
            'configuration_uri': manifest.get('configuration_uri'),
        })

    nodes = [{'id': key, **data} for key, data in sorted(graph.nodes(data=True))]
    edges = sorted(({'source': source, 'target': target, **data} for source, target, data in graph.edges(data=True)),
                   key=lambda value: (value['source'], value['target'], value['type'], json.dumps(value['properties'], sort_keys=True)))
    snapshot = hashlib.sha256(json.dumps([nodes, edges], sort_keys=True).encode()).hexdigest()
    return {'nodes': nodes, 'edges': edges, 'metadata': {
        'schema_version': '1.0', 'source': 'combined_trace', 'repository_uri': repo_uri,
        'revision': repository.get('revision'), 'configuration_uri': manifest.get('configuration_uri'),
        'snapshot_id': snapshot, 'nodes': len(nodes), 'edges': len(edges),
        'retention': 'request-only', 'diagnostics': diagnostics,
        'limitations': ['Directory-derived packages; non-Python semantics are heuristic.',
                        'Lifecycle assertions are supplied explicitly, not discovered or inferred.',
                        'Linked tests express traceability, not a passing test result.'],
    }}


def neighborhood(data, start, direction='both', depth=4, max_nodes=100, predicates=None):
    """Bounded graph traversal with explicit direction and witness paths.

    This is reachability, not a claim of causal impact. Containment can be
    excluded by passing an explicit predicate filter.
    """
    graph = nx.MultiDiGraph()
    nodes = {node['id']: node for node in data['nodes']}
    graph.add_nodes_from(nodes)
    for index, edge in enumerate(data['edges']):
        if not predicates or edge['type'] in predicates:
            graph.add_edge(edge['source'], edge['target'], key=index, **{'record': edge})
    if start not in nodes:
        raise KeyError(start)
    queue = deque([(start, 0)])
    paths = {start: [start]}
    truncated = False
    while queue:
        current, distance = queue.popleft()
        neighbors = set()
        if direction in {'outgoing', 'both'}:
            neighbors.update(graph.successors(current))
        if direction in {'incoming', 'both'}:
            neighbors.update(graph.predecessors(current))
        for target in sorted(neighbors):
            if target in paths:
                continue
            if distance >= depth or len(paths) >= max_nodes:
                truncated = True
                continue
            paths[target] = paths[current] + [target]
            queue.append((target, distance + 1))
    result_edges = [edge for edge in data['edges'] if edge['source'] in paths and edge['target'] in paths
                    and (not predicates or edge['type'] in predicates)]
    return {'nodes': [nodes[key] for key in paths], 'edges': result_edges,
            'metadata': {**data['metadata'], 'query': {'start': start, 'direction': direction, 'depth': depth},
                         'total_nodes': len(nodes), 'nodes': len(paths), 'edges': len(result_edges),
                         'truncated': truncated, 'witness_paths': paths}}


def as_jsonld(data):
    """RDF-compatible projection with reified assertions preserving provenance."""
    records = []
    for node in data['nodes']:
        record = {'@id': node['id'], '@type': TYPE_URIS.get(node['type'], CT + node['type']),
                  RDFS + 'label': node['label']}
        for key in ('path', 'start', 'code_id', 'revision', 'source_digest'):
            if node['properties'].get(key) is not None:
                record[CT + key] = node['properties'][key]
        records.append(record)
    by_id = {record['@id']: record for record in records}
    for index, edge in enumerate(data['edges']):
        values = by_id[edge['source']].setdefault(edge['type'], [])
        if not isinstance(values, list):
            values = [values]
            by_id[edge['source']][edge['type']] = values
        target = {'@id': edge['target']}
        if target not in values:
            values.append(target)
        assertion = {'@id': 'urn:codetrace:assertion:' + data['metadata']['snapshot_id'] + ':' + str(index),
                     '@type': RDF + 'Statement', RDF + 'subject': {'@id': edge['source']},
                     RDF + 'predicate': {'@id': edge['type']}, RDF + 'object': target,
                     CT + 'origin': edge['properties']['origin']}
        for key in ('asserted_by', 'configuration_uri', 'repository_uri'):
            if edge['properties'].get(key):
                assertion[CT + key] = {'@id': edge['properties'][key]}
        records.append(assertion)
    return {'@graph': records}
