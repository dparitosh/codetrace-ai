"""Managed repository, lifecycle, and delivery evidence assembled into one snapshot."""
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException

from api.graph_routes import build_graph_from_directory
from api.trace_routes import TraceManifest
from api.agent_routes import _build_architecture_audit
from core.config import PROJECT_ROOT, settings
from graph.traceability import materialize, node_domain, CT
from services.oslc_service import collect_oslc, local_path, read_response, server_secret, allowed_url
from services.git_isolation import git_command, git_environment
from services.sbom_service import inventory, attach as attach_sbom
from services.git_revision import raw_revision
from services.agent_workspace import coverage_gaps


def repository_config(source_id):
    repository = next((item for item in settings.MANAGED_REPOSITORIES if item.id == source_id), None)
    if repository is None:
        raise HTTPException(404, 'Managed source was not found')
    return repository


def read_repository(repository):
    def scan(path, env):
        before = raw_revision(path, env)
        graph = build_graph_from_directory(path, 'managed_repository')
        if repository.manifest_path:
            manifest_path = Path(repository.manifest_path)
            manifest_path = manifest_path if manifest_path.is_absolute() else path / manifest_path
            try:
                with manifest_path.open('rb') as stream:
                    content = stream.read(settings.MAX_TRACE_MANIFEST_BYTES + 1)
                if len(content) > settings.MAX_TRACE_MANIFEST_BYTES:
                    raise HTTPException(413, 'Managed manifest exceeds the configured limit')
                graph['trace_manifest'] = TraceManifest.model_validate_json(content).model_dump()
            except (OSError, ValueError) as exc:
                raise HTTPException(422, 'Managed manifest is unavailable or invalid. Check central configuration.') from exc
        try:
            graph['sbom_inventory'] = inventory(path, repository)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, 'Managed SBOM is invalid or exceeds configured limits') from exc
        after = raw_revision(path, env)
        revision = before if before and before == after else None
        return graph, revision
    if repository.kind == 'local':
        path = local_path(repository.path)
        if not path.is_dir():
            raise HTTPException(422, 'Managed repository directory is unavailable. Check central configuration.')
        with tempfile.TemporaryDirectory(prefix='codetrace-git-home-') as home:
            return scan(path, git_environment(home))
    with tempfile.TemporaryDirectory(prefix='codetrace-managed-') as directory:
        target = Path(directory) / 'source'
        command = git_command() + ['clone', '--depth', '1']
        token = server_secret(repository.token_env)
        if repository.token_env and not token:
            raise HTTPException(422, 'Managed Git credential variable is missing')
        if repository.ref:
            command.extend(['--branch', repository.ref])
        try:
            result = subprocess.run(command + ['--', repository.url, str(target)], capture_output=True,
                text=True, timeout=settings.GITLAB_CLONE_TIMEOUT_SECONDS, check=False,
                env=git_environment(Path(directory) / 'git-home', token))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(504, 'Managed repository clone failed or timed out.') from exc
        if result.returncode:
            raise HTTPException(422, 'Managed repository could not be cloned. Check configured URL and Git credentials.')
        return scan(target, git_environment(Path(directory) / 'git-home'))


def pipeline_context(source_id, repository_uri, revision):
    runs, statuses = [], []
    with httpx.Client(timeout=settings.OSLC_TIMEOUT_SECONDS, follow_redirects=False) as client:
        for provider in settings.CI_PROVIDERS:
            if provider.repository_id != source_id:
                continue
            token = server_secret(provider.token_env)
            headers = {'Accept': 'application/json'}
            if provider.token_env and not token:
                statuses.append({'id': provider.id, 'label': provider.label, 'domain': 'CI', 'status': 'unavailable'})
                continue
            if token:
                if provider.platform == 'github':
                    headers['Authorization'] = 'Bearer ' + token
                else:
                    headers['PRIVATE-TOKEN'] = token
            try:
                provider_runs, seen, seen_runs = [], set(), set()
                url = provider.endpoint
                partial = False
                pages = 0
                while url and pages < settings.CI_MAX_PAGES:
                    allowed_url(SimpleNamespace(allowed_base_url=provider.endpoint, endpoint=provider.endpoint), url)
                    if url in seen:
                        partial = True
                        break
                    seen.add(url)
                    data, _, next_url = read_response(client, url, headers, with_next=True)
                    pages += 1
                    payload = json.loads(data)
                    entries = payload.get('workflow_runs', []) if provider.platform == 'github' else payload
                    if not isinstance(entries, list):
                        raise ValueError('Unexpected pipeline response')
                    remaining = settings.CI_MAX_RUNS - len(provider_runs)
                    partial = len(entries) > remaining
                    for item in entries[:remaining]:
                        if not isinstance(item, dict):
                            raise ValueError('Unexpected pipeline entry')
                        if str(item['id']) in seen_runs:
                            continue
                        seen_runs.add(str(item['id']))
                        sha = item.get('head_sha') or item.get('sha')
                        provider_runs.append({'id': f'urn:codetrace:build:{provider.id}:{item["id"]}',
                            'label': item.get('name') or f'Pipeline {item["id"]}', 'provider_id': provider.id,
                            'status': item.get('conclusion') or item.get('status', 'unknown'),
                            'revision': sha, 'branch': item.get('head_branch') or item.get('ref'),
                            'at': item.get('updated_at') or item.get('created_at'), 'matches_revision': sha == revision and revision is not None,
                            'repository_uri': repository_uri})
                    url = urljoin(url, next_url) if next_url else None
                    if provider.platform == 'github' and isinstance(payload.get('total_count'), int):
                        partial = partial or payload['total_count'] > len(provider_runs)
                    if len(provider_runs) >= settings.CI_MAX_RUNS:
                        partial = partial or bool(url)
                        break
                partial = partial or bool(url)
                runs.extend(provider_runs)
                statuses.append({'id': provider.id, 'label': provider.label, 'domain': 'CI', 'status': 'partial' if partial else 'ready', 'resources': len(provider_runs), 'pages': pages})
            except (ValueError, KeyError, TypeError, AttributeError, httpx.HTTPError):
                statuses.append({'id': provider.id, 'label': provider.label, 'domain': 'CI', 'status': 'unavailable',
                                 'warnings': ['Pipeline data could not be read. Check central connection settings.']})
    return runs, statuses


def build_managed_snapshot(source_id, include_lifecycle=True):
    repository = repository_config(source_id)
    code_graph, revision = read_repository(repository)
    repository_uri = repository.uri or 'urn:codetrace:repository:' + source_id
    resources, links, properties, events, statuses = collect_oslc(source_id) if include_lifecycle else ([], [], {}, [], [])
    manifest = {'repository': {'uri': repository_uri, 'label': repository.label, 'revision': revision},
                'resources': resources, 'links': links}
    if repository.manifest_path and include_lifecycle:
        imported = code_graph['trace_manifest']
        if imported['repository']['uri'] != repository_uri:
            raise HTTPException(422, 'Managed lifecycle manifest repository URI does not match the managed source')
        nodes_by_uri = {node['uri']: node for node in manifest['resources']}
        nodes_by_uri.update({node['uri']: node for node in imported['resources']})
        manifest['resources'] = list(nodes_by_uri.values())
        manifest['links'].extend(imported['links'])
        manifest['configuration_uri'] = imported.get('configuration_uri')
    pipeline_runs, ci_statuses = pipeline_context(source_id, repository_uri, revision)
    statuses.extend(ci_statuses)
    for run in pipeline_runs:
        manifest['resources'].append({'uri': run['id'], 'kind': 'build', 'label': str(run['label'])[:512]})
        # Only matching revisions get a provenance relationship to this snapshot.
        if run['matches_revision']:
            manifest['links'].append({'source': {'uri': repository_uri}, 'predicate': CT + 'builtBy',
                                     'target': {'uri': run['id']}, 'asserted_by': 'urn:codetrace:pipeline:' + run['provider_id']})
        properties[run['id']] = {**run, 'domain': 'CI', 'origin': 'pipeline_provider'}
    try:
        validated = TraceManifest.model_validate(manifest)
        graph = materialize(code_graph, validated.model_dump(), code_graph['metadata']['source_digest'])
        attach_sbom(graph, code_graph.get('sbom_inventory'), repository_uri)
    except ValueError as exc:
        raise HTTPException(422, 'Managed trace configuration could not be materialized: ' + str(exc)) from exc
    for node in graph['nodes']:
        node['properties'].update(properties.get(node['id'], {}))
        node['properties']['domain'] = node_domain(node)
    audit = _build_architecture_audit(code_graph)
    audit = {key: value[:100] if isinstance(value, list) else value for key, value in audit.items()}
    requirement_ids = {node['id'] for node in graph['nodes'] if node['type'] == 'requirement' and not node['properties'].get('deleted')}
    gaps = coverage_gaps(graph)
    no_trace = {item['node_id'] for item in gaps if item['missing_implementation'] and item['missing_validation']}
    traced = requirement_ids - no_trace
    graph['metadata'].update(source='managed_workspace', source_id=source_id, source_label=repository.label,
        revision=revision, indexed_at=datetime.now(timezone.utc).isoformat(), files=code_graph['metadata']['files'],
        skipped=code_graph['metadata'].get('skipped', {}),
        source_digest=code_graph['metadata']['source_digest'],
        retention='shared local SQLite until expiry' if settings.SESSION_STORE == 'sqlite' else 'session memory', connectors=statuses, coverage={'requirements': len(requirement_ids),
        'linked_requirements': len(traced), 'unlinked_requirements': sorted(no_trace),
        'missing_implementation': sorted(item['node_id'] for item in gaps if item['missing_implementation']),
        'missing_validation': sorted(item['node_id'] for item in gaps if item['missing_validation'])},
        schema_domains=['AM', 'RM', 'CM', 'QM', 'TRS', 'SCHEMA'],
        limits={'render_nodes': settings.WORKSPACE_RENDER_NODES, 'render_edges': settings.WORKSPACE_RENDER_EDGES})
    graph['architecture_audit'] = audit
    graph['source_assessments'] = code_graph.get('source_assessments')
    graph['trs_events'] = events
    graph['pipeline_runs'] = pipeline_runs
    # Bind approval to the enriched provider state, checkpoints, and scan evidence.
    graph['metadata']['snapshot_id'] = hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()
    return graph
