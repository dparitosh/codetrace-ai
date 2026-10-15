"""Bounded SBOM import and npm lockfile inventory, without executing packages.

Generated CycloneDX is a lockfile inventory, not a built-artifact attestation or
vulnerability scan. External references are retained as data and never fetched.
"""
import hashlib
import json
from pathlib import Path
from core.config import settings


def read_json(path):
    with Path(path).open('rb') as stream:
        content = stream.read(settings.SBOM_MAX_BYTES + 1)
    if len(content) > settings.SBOM_MAX_BYTES:
        raise ValueError('SBOM/lockfile exceeds SBOM_MAX_BYTES')
    try:
        data = json.loads(content)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid or excessively nested SBOM JSON') from exc
    if not isinstance(data, dict):
        raise ValueError('SBOM/lockfile must be a JSON object')
    return data


def normalize(document):
    try:
        return _normalize(document)
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError('Invalid SBOM component/dependency structure') from exc


def _normalize(document):
    components, dependencies = [], []
    if document.get('bomFormat') == 'CycloneDX' and document.get('specVersion') in {'1.4', '1.5', '1.6'}:
        def visit(items):
            if not isinstance(items, list):
                raise ValueError('Invalid CycloneDX component list')
            for item in items:
                if not isinstance(item, dict) or not item.get('name') or not item.get('bom-ref'):
                    raise ValueError('Every imported component requires name and bom-ref')
                components.append({'ref': item['bom-ref'], 'name': item['name'], 'version': item.get('version'),
                                   'purl': item.get('purl'), 'licenses': item.get('licenses', [])})
                if len(components) > settings.SBOM_MAX_COMPONENTS:
                    raise ValueError('SBOM component limit exceeded')
                visit(item.get('components', []))
        visit(document.get('components', []))
        for item in document.get('dependencies', []):
            dependencies.extend((item['ref'], target) for target in item.get('dependsOn', []))
        # The metadata root is not a package component; its membership is added
        # from the managed repository rather than creating an unresolved edge.
        root = document.get('metadata', {}).get('component', {}).get('bom-ref')
        dependencies = [edge for edge in dependencies if edge[0] != root]
    elif document.get('spdxVersion') in {'SPDX-2.2', 'SPDX-2.3'}:
        for item in document.get('packages', []):
            components.append({'ref': item['SPDXID'], 'name': item['name'], 'version': item.get('versionInfo'),
                               'purl': next((ref['referenceLocator'] for ref in item.get('externalRefs', []) if ref.get('referenceType') == 'purl'), None),
                               'licenses': [item.get('licenseConcluded', 'NOASSERTION')]})
        for item in document.get('relationships', []):
            if item.get('relationshipType') == 'DEPENDS_ON':
                dependencies.append((item['spdxElementId'], item['relatedSpdxElement']))
            elif item.get('relationshipType') == 'DEPENDENCY_OF':
                dependencies.append((item['relatedSpdxElement'], item['spdxElementId']))
    else:
        raise ValueError('Supported SBOM formats: CycloneDX JSON 1.4–1.6 or SPDX JSON 2.2–2.3')
    refs = [item['ref'] for item in components]
    if any(not isinstance(ref, str) or not ref or len(ref) > 2048 for ref in refs):
        raise ValueError('Invalid SBOM component reference')
    if len(components) > settings.SBOM_MAX_COMPONENTS or len(refs) != len(set(refs)):
        raise ValueError('SBOM has duplicate references or too many components')
    if any(not isinstance(item['name'], str) or not item['name'] or len(item['name']) > 2048 for item in components):
        raise ValueError('Invalid SBOM component name')
    if any(item.get('version') is not None and (not isinstance(item['version'], str) or len(item['version']) > 2048) for item in components):
        raise ValueError('Invalid SBOM component version')
    known = set(refs)
    if len(dependencies) > settings.MAX_GRAPH_EDGES or any(source not in known or target not in known for source, target in dependencies):
        raise ValueError('SBOM dependency has an unknown endpoint or exceeds the edge limit')
    return components, sorted(set(dependencies))


def inventory(root, repository):
    try:
        return _inventory(root, repository)
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError('Invalid SBOM/lockfile structure') from exc


def _inventory(root, repository):
    if repository.sbom_path:
        from services.oslc_service import local_path
        document = read_json(local_path(repository.sbom_path))
        components, dependencies = normalize(document)
        return {'document': document, 'components': components, 'dependencies': dependencies,
                'origin': 'imported_sbom', 'limitations': ['Imported supplier assertions; not independently verified.']}
    root = Path(root).resolve()
    components, dependencies = [], []
    for relative in repository.sbom_lockfiles:
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('SBOM lockfile must stay within the managed repository')
        if not path.is_file():
            continue
        lock = read_json(path)
        if lock.get('lockfileVersion') not in {2, 3} or not isinstance(lock.get('packages'), dict):
            raise ValueError('SBOM generation requires npm package-lock version 2 or 3')
        packages = lock['packages']
        refs = {key: relative + '#' + key for key, item in packages.items() if key and not item.get('link') and item.get('version')}
        for key, ref in refs.items():
            item = packages[key]
            components.append({'type': 'library', 'bom-ref': ref, 'name': item.get('name') or key.rsplit('node_modules/', 1)[-1],
                               'version': item['version'], 'licenses': [{'license': {'name': str(item['license'])}}] if item.get('license') else [],
                               'properties': [{'name': 'codetrace:lockfile', 'value': relative}]})
            targets = []
            for name in {**item.get('dependencies', {}), **item.get('optionalDependencies', {})}:
                directory = key
                while True:
                    candidate = directory + '/node_modules/' + name if directory else 'node_modules/' + name
                    if candidate in refs:
                        targets.append(refs[candidate]); break
                    if not directory:
                        break
                    directory = directory.rsplit('/', 1)[0] if '/' in directory else ''
            dependencies.append({'ref': ref, 'dependsOn': sorted(set(targets))})
    if not components:
        return None
    document = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'version': 1,
                'components': components, 'dependencies': dependencies,
                'metadata': {'properties': [{'name': 'codetrace:scope', 'value': 'npm lockfile inventory; includes development dependencies'}]}}
    if len(json.dumps(document).encode()) > settings.SBOM_MAX_BYTES:
        raise ValueError('Generated SBOM exceeds SBOM_MAX_BYTES')
    normalized, edges = normalize(document)
    return {'document': document, 'components': normalized, 'dependencies': edges, 'origin': 'npm_lockfile',
            'limitations': ['npm lockfile inventory only; excludes unlisted ecosystems, vendored code and build artifacts.',
                            'Peer/workspace dependency resolution is not inferred; no vulnerability or license compliance verdict.']}


def attach(graph, sbom, repository_uri):
    if not sbom:
        return
    identities = {item['ref']: 'urn:codetrace:component:' + hashlib.sha256((repository_uri + '\n' + item['ref']).encode()).hexdigest() for item in sbom['components']}
    if len(graph['nodes']) + len(identities) > settings.MAX_GRAPH_NODES:
        raise ValueError('Combined SBOM graph exceeds node limit')
    if len(graph['edges']) + len(identities) + len(sbom['dependencies']) > settings.MAX_GRAPH_EDGES:
        raise ValueError('Combined SBOM graph exceeds edge limit')
    for item in sbom['components']:
        uri = identities[item['ref']]
        graph['nodes'].append({'id': uri, 'label': str(item['name'])[:512] + ('@' + str(item['version'])[:100] if item.get('version') else ''),
                               'type': 'sbom_component', 'properties': {**item, 'domain': 'SBOM', 'origin': sbom['origin']}})
        graph['edges'].append({'source': repository_uri, 'target': uri, 'type': 'urn:codetrace:vocab:contains', 'properties': {'origin': sbom['origin']}})
    graph['edges'].extend({'source': identities[source], 'target': identities[target], 'type': 'urn:codetrace:vocab:depends_on',
                           'properties': {'origin': sbom['origin']}} for source, target in sbom['dependencies'])
    graph['sbom'] = {'document': sbom['document'], 'origin': sbom['origin'], 'limitations': sbom['limitations']}
    graph['metadata']['sbom'] = {'components': len(identities), 'dependencies': len(sbom['dependencies']), 'limitations': sbom['limitations']}
    graph['metadata'].update(nodes=len(graph['nodes']), edges=len(graph['edges']))
