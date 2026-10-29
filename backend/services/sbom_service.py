"""Bounded SBOM import and npm lockfile inventory, without executing packages.

Generated CycloneDX is a lockfile inventory, not a built-artifact attestation or
vulnerability scan. External references are retained as data and never fetched.
"""
import hashlib
import json
import base64
from pathlib import Path
from urllib.parse import quote
from packaging.licenses import canonicalize_license_expression, InvalidLicenseExpression
from core.config import settings


def license_choices(value):
    if not value:
        return []
    if not isinstance(value, str):
        raise ValueError('npm license must be a string')
    try:
        expression = str(canonicalize_license_expression(value))
    except InvalidLicenseExpression:
        return [{'license': {'name': value}}]
    return [{'expression': expression}]


def sri_hashes(value):
    hashes = []
    for part in str(value or '').split():
        algorithm, separator, digest = part.partition('-')
        if algorithm not in {'sha256', 'sha384', 'sha512'} or not separator:
            continue
        try:
            raw = base64.b64decode(digest.split('?')[0], validate=True)
        except ValueError as exc:
            raise ValueError('Invalid lockfile integrity hash') from exc
        if len(raw) != int(algorithm[3:]) // 8:
            raise ValueError('Invalid lockfile integrity hash length')
        hashes.append({'alg': 'SHA-' + algorithm[3:], 'content': raw.hex()})
    return hashes


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
    application_ref = None
    if document.get('bomFormat') == 'CycloneDX' and document.get('specVersion') in {'1.4', '1.5', '1.6'}:
        def visit(items):
            if not isinstance(items, list):
                raise ValueError('Invalid CycloneDX component list')
            for item in items:
                if not isinstance(item, dict) or not item.get('name'):
                    raise ValueError('Every imported component requires a name')
                reference = item.get('bom-ref')
                if reference is None:
                    reference = 'urn:codetrace:anonymous-component:' + hashlib.sha256(
                        (str(len(components)) + '\n' + json.dumps(item, sort_keys=True)).encode()).hexdigest()
                components.append({'ref': reference, 'name': item['name'], 'version': item.get('version'),
                                   'purl': item.get('purl'), 'licenses': item.get('licenses', []),
                                   'hashes': item.get('hashes', []), 'scope': item.get('scope')})
                if len(components) > settings.SBOM_MAX_COMPONENTS:
                    raise ValueError('SBOM component limit exceeded')
                visit(item.get('components', []))
        visit(document.get('components', []))
        for item in document.get('dependencies', []):
            dependencies.extend((item['ref'], target) for target in item.get('dependsOn', []))
        # The metadata root is not a package component; its membership is added
        # from the managed repository rather than creating an unresolved edge.
        root = document.get('metadata', {}).get('component', {}).get('bom-ref')
        if root is not None and (not isinstance(root, str) or not root or len(root) > 2048):
            raise ValueError('Invalid SBOM application reference')
        application_ref = root
        if root not in {item['ref'] for item in components if isinstance(item['ref'], str)}:
            dependencies = [edge for edge in dependencies if edge[0] != root]
    elif document.get('spdxVersion') in {'SPDX-2.2', 'SPDX-2.3'}:
        for item in document.get('packages', []):
            components.append({'ref': item['SPDXID'], 'name': item['name'], 'version': item.get('versionInfo'),
                               'purl': next((ref['referenceLocator'] for ref in item.get('externalRefs', []) if ref.get('referenceType') == 'purl'), None),
                               'license_declared': item.get('licenseDeclared', 'NOASSERTION'),
                               'license_concluded': item.get('licenseConcluded', 'NOASSERTION'),
                               'hashes': [{'alg': c['algorithm'], 'content': c['checksumValue']} for c in item.get('checksums', [])],
                               'licenses': list(dict.fromkeys([item.get('licenseDeclared', 'NOASSERTION'),
                                                              item.get('licenseConcluded', 'NOASSERTION')]))})
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
    if application_ref is not None:
        known.add(application_ref)
    if len(dependencies) > settings.MAX_GRAPH_EDGES or any(source not in known or target not in known for source, target in dependencies):
        raise ValueError('SBOM dependency has an unknown endpoint or exceeds the edge limit')
    return components, sorted(set(dependencies))


def inventory(root, repository):
    try:
        return _inventory(root, repository)
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError('Invalid SBOM/lockfile structure') from exc


def root_dependencies(document, components):
    """Only explicit application roots; inventory membership is not dependency."""
    known = {item['ref'] for item in components}
    roots = []
    root = None
    if document.get('bomFormat') == 'CycloneDX':
        root = document.get('metadata', {}).get('component', {}).get('bom-ref')
        if root in known:
            roots = [root]
        elif root:
            roots = [target for item in document.get('dependencies', []) if item['ref'] == root
                     for target in item.get('dependsOn', [])]
    else:
        described = document.get('documentDescribes', [])
        if not isinstance(described, list) or any(not isinstance(ref, str) for ref in described):
            raise ValueError('Invalid SPDX documentDescribes')
        roots.extend(described)
        for item in document.get('relationships', []):
            if item.get('relationshipType') == 'DESCRIBES' and item['spdxElementId'] == document.get('SPDXID'):
                roots.append(item['relatedSpdxElement'])
            elif item.get('relationshipType') == 'DESCRIBED_BY' and item['relatedSpdxElement'] == document.get('SPDXID'):
                roots.append(item['spdxElementId'])
    valid_targets = known | ({root} if document.get('bomFormat') == 'CycloneDX' and root else set())
    if any(ref not in valid_targets for ref in roots):
        raise ValueError('SBOM application root has an unknown dependency')
    return sorted(set(roots))


def _inventory(root, repository):
    if repository.sbom_path:
        path = Path(repository.sbom_path)
        document = read_json(path if path.is_absolute() else Path(root) / path)
        components, dependencies = normalize(document)
        return {'document': document, 'components': components, 'dependencies': dependencies,
                'root_dependencies': root_dependencies(document, components),
                'application_ref': document.get('metadata', {}).get('component', {}).get('bom-ref') if document.get('bomFormat') == 'CycloneDX' else None,
                'origin': 'imported_sbom', 'limitations': ['Imported supplier assertions; not independently verified.']}
    root = Path(root).resolve()
    components, dependencies, direct, unresolved = [], [], [], []
    def missing(lockfile, source, name, kind):
        unresolved.append({'lockfile': lockfile, 'source': source, 'name': name, 'kind': kind})
        if len(unresolved) > settings.MAX_GRAPH_EDGES:
            raise ValueError('SBOM unresolved dependency limit exceeded')
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
        application = packages.get('', {})
        for name in {**application.get('dependencies', {}), **application.get('devDependencies', {}),
                     **application.get('optionalDependencies', {})}:
            if 'node_modules/' + name in refs:
                direct.append(refs['node_modules/' + name])
            else:
                kind = ('optional' if name in application.get('optionalDependencies', {}) else
                        'required' if name in application.get('dependencies', {}) else 'development')
                missing(relative, '(application)', name, kind)
        for key, ref in refs.items():
            item = packages[key]
            name = item.get('name') or key.rsplit('node_modules/', 1)[-1]
            components.append({'type': 'library', 'bom-ref': ref, 'name': name,
                               'version': item['version'], 'licenses': license_choices(item.get('license')),
                               'purl': 'pkg:npm/' + quote(name, safe='/') + '@' + quote(item['version'], safe=''),
                               'hashes': sri_hashes(item.get('integrity')),
                               'properties': [{'name': 'codetrace:lockfile', 'value': relative}]})
            targets = []
            for name in {**item.get('dependencies', {}), **item.get('optionalDependencies', {}), **item.get('peerDependencies', {})}:
                peer_only = name in item.get('peerDependencies', {}) and name not in {**item.get('dependencies', {}), **item.get('optionalDependencies', {})}
                # Peers resolve in the consumer's parent installation context.
                directory = key.rsplit('/node_modules/', 1)[0] if peer_only and '/node_modules/' in key else '' if peer_only else key
                while True:
                    candidate = directory + '/node_modules/' + name if directory else 'node_modules/' + name
                    if candidate in refs:
                        targets.append(refs[candidate]); break
                    if not directory:
                        optional_peer = peer_only and item.get('peerDependenciesMeta', {}).get(name, {}).get('optional')
                        if not optional_peer:
                            missing(relative, ref, name, 'peer' if peer_only else 'optional' if name in item.get('optionalDependencies', {}) else 'required')
                        break
                    directory = directory.rsplit('/', 1)[0] if '/' in directory else ''
            dependencies.append({'ref': ref, 'dependsOn': sorted(set(targets))})
    if not components and not unresolved:
        return None
    root_ref = 'urn:codetrace:lockfile-application'
    document = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'version': 1,
                'components': components, 'dependencies': dependencies + [{'ref': root_ref, 'dependsOn': sorted(set(direct))}],
                'metadata': {'component': {'type': 'application', 'name': repository.label, 'bom-ref': root_ref},
                             'properties': [{'name': 'codetrace:scope', 'value': 'npm lockfile inventory; includes development dependencies'},
                                            {'name': 'codetrace:unresolved-dependencies', 'value': json.dumps(unresolved, sort_keys=True)}]}}
    if len(json.dumps(document).encode()) > settings.SBOM_MAX_BYTES:
        raise ValueError('Generated SBOM exceeds SBOM_MAX_BYTES')
    normalized, edges = normalize(document)
    limitations = ['npm lockfile inventory only; excludes unlisted ecosystems, vendored code and build artifacts.',
                   'Peer links use lockfile installation locations; workspace links are not resolved. No runtime or license compliance verdict.']
    if unresolved:
        limitations.append(f'{len(unresolved)} declared npm dependencies could not be resolved from the lockfile inventory. '
                           'Lineage is incomplete; optional entries may be omitted for this platform or install scope.')
    return {'document': document, 'components': normalized, 'dependencies': edges, 'application_ref': root_ref,
            'root_dependencies': root_dependencies(document, normalized), 'origin': 'npm_lockfile',
            'unresolved_dependencies': unresolved, 'limitations': limitations}


def attach(graph, sbom, repository_uri):
    if not sbom:
        return
    identities = {item['ref']: 'urn:codetrace:component:' + hashlib.sha256((repository_uri + '\n' + item['ref']).encode()).hexdigest() for item in sbom['components']}
    if len(graph['nodes']) + len(identities) > settings.MAX_GRAPH_NODES:
        raise ValueError('Combined SBOM graph exceeds node limit')
    roots = sbom.get('root_dependencies', [])
    endpoints = dict(identities)
    if sbom.get('application_ref') and sbom['application_ref'] not in endpoints:
        endpoints[sbom['application_ref']] = repository_uri
    if len(graph['edges']) + len(identities) + len(sbom['dependencies']) + len(roots) > settings.MAX_GRAPH_EDGES:
        raise ValueError('Combined SBOM graph exceeds edge limit')
    for item in sbom['components']:
        uri = identities[item['ref']]
        graph['nodes'].append({'id': uri, 'label': str(item['name'])[:512] + ('@' + str(item['version'])[:100] if item.get('version') else ''),
                               'type': 'sbom_component', 'properties': {**item, 'domain': 'SBOM', 'origin': sbom['origin']}})
        graph['edges'].append({'source': repository_uri, 'target': uri, 'type': 'urn:codetrace:vocab:contains', 'properties': {'origin': sbom['origin']}})
    graph['edges'].extend({'source': endpoints[source], 'target': endpoints[target], 'type': 'urn:codetrace:vocab:depends_on',
                           'properties': {'origin': sbom['origin']}} for source, target in sbom['dependencies'])
    graph['edges'].extend({'source': repository_uri, 'target': endpoints[target], 'type': 'urn:codetrace:vocab:depends_on',
                          'properties': {'origin': sbom['origin'], 'root_dependency': True}} for target in roots)
    graph['sbom'] = {'document': sbom['document'], 'origin': sbom['origin'], 'limitations': sbom['limitations']}
    graph['metadata']['sbom'] = {'components': len(identities), 'dependencies': len(sbom['dependencies']),
                               'root_dependencies': len(roots), 'root_known': bool(roots), 'limitations': sbom['limitations'],
                               'unresolved_dependencies': sbom.get('unresolved_dependencies', []),
                               'resolution_complete': not sbom.get('unresolved_dependencies')}
    from services.advisory_service import advisory_evidence
    graph['metadata']['sbom']['advisory_lookup'] = advisory_evidence(sbom)
    graph['metadata'].update(nodes=len(graph['nodes']), edges=len(graph['edges']))
