"""Managed repository, lifecycle, and delivery evidence assembled into one snapshot."""
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import HTTPException

from api.graph_routes import build_graph_from_directory
from api.trace_routes import TraceManifest
from api.agent_routes import _build_architecture_audit
from core.config import PROJECT_ROOT, settings
from graph.traceability import materialize, CT
from services.oslc_service import collect_oslc, local_path, read_response, server_secret
from services.oslc_store import LINK_PREDICATES


def repository_config(source_id):
    repository = next((item for item in settings.MANAGED_REPOSITORIES if item.id == source_id), None)
    if repository is None:
        raise HTTPException(404, 'Managed source was not found')
    return repository


def read_repository(repository):
    def scan(path):
        graph = build_graph_from_directory(path, 'managed_repository')
        try:
            revision = subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                capture_output=True, text=True, timeout=5, check=False).stdout.strip() or None
            state = subprocess.run(['git', '-C', str(path), 'status', '--porcelain', '--untracked-files=normal'],
                capture_output=True, text=True, timeout=5, check=False)
            # A commit identifies committed bytes only. Never attach commit build
            # evidence to modified/untracked local source or an unknown Git state.
            if state.returncode or state.stdout.strip():
                revision = None
        except (OSError, subprocess.TimeoutExpired):
            revision = None
        return graph, revision
    if repository.kind == 'local':
        path = local_path(repository.path)
        if not path.is_dir():
            raise HTTPException(422, 'Managed repository directory is unavailable. Check central configuration.')
        return scan(path)
    with tempfile.TemporaryDirectory(prefix='codetrace-managed-') as directory:
        target = Path(directory) / 'source'
        command = ['git', '-c', 'http.followRedirects=false', '-c', 'core.hooksPath=', 'clone', '--depth', '1']
        if repository.ref:
            command.extend(['--branch', repository.ref])
        try:
            result = subprocess.run(command + ['--', repository.url, str(target)], capture_output=True,
                text=True, timeout=settings.GITLAB_CLONE_TIMEOUT_SECONDS, check=False,
                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'Never'})
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(504, 'Managed repository clone failed or timed out.') from exc
        if result.returncode:
            raise HTTPException(422, 'Managed repository could not be cloned. Check configured URL and Git credentials.')
        return scan(target)


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
                data, _ = read_response(client, provider.endpoint, headers)
                payload = json.loads(data)
                entries = payload.get('workflow_runs', []) if provider.platform == 'github' else payload
                if not isinstance(entries, list):
                    raise ValueError('Unexpected pipeline response')
                provider_runs = []
                for item in entries[:20]:
                    if not isinstance(item, dict):
                        raise ValueError('Unexpected pipeline entry')
                    sha = item.get('head_sha') or item.get('sha')
                    provider_runs.append({'id': f'urn:codetrace:build:{provider.id}:{item["id"]}',
                        'label': item.get('name') or f'Pipeline {item["id"]}', 'provider_id': provider.id,
                        'status': item.get('conclusion') or item.get('status', 'unknown'),
                        'revision': sha, 'branch': item.get('head_branch') or item.get('ref'),
                        'at': item.get('updated_at') or item.get('created_at'), 'matches_revision': sha == revision and revision is not None,
                        'repository_uri': repository_uri})
                runs.extend(provider_runs)
                statuses.append({'id': provider.id, 'label': provider.label, 'domain': 'CI', 'status': 'partial' if len(entries) > 20 else 'ready', 'resources': len(provider_runs)})
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
        path = local_path(repository.manifest_path)
        try:
            if path.stat().st_size > settings.MAX_TRACE_MANIFEST_BYTES:
                raise HTTPException(413, 'Managed manifest exceeds the configured limit')
            imported = TraceManifest.model_validate_json(path.read_bytes()).model_dump()
        except (OSError, ValueError) as exc:
            raise HTTPException(422, 'Managed manifest is unavailable or invalid. Check central configuration.') from exc
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
    except ValueError as exc:
        raise HTTPException(422, 'Managed trace configuration could not be materialized: ' + str(exc)) from exc
    domains = {'requirement': 'RM', 'architecture': 'AM', 'change_request': 'CM', 'test': 'QM',
               'test_plan': 'QM', 'test_script': 'QM', 'test_execution_record': 'QM', 'test_result': 'QM',
               'configuration': 'CONFIG', 'tracked_resource': 'TRS', 'resource_shape': 'SCHEMA', 'build': 'CI'}
    for node in graph['nodes']:
        node['properties'].update(properties.get(node['id'], {}))
        node['properties'].setdefault('domain', domains.get(node['type'], 'EXTERNAL' if node['type'] == 'external_resource' else 'CODE'))
    audit = _build_architecture_audit(code_graph)
    audit = {key: value[:100] if isinstance(value, list) else value for key, value in audit.items()}
    requirement_ids = {node['id'] for node in graph['nodes'] if node['type'] == 'requirement' and not node['properties'].get('deleted')}
    traced = set()
    nodes_by_id = {node['id']: node for node in graph['nodes']}
    for edge in graph['edges']:
        endpoints = [nodes_by_id.get(edge[key], {}) for key in ('source', 'target')]
        evidence_valid = all(node and node['type'] != 'external_resource' and not node.get('properties', {}).get('deleted') for node in endpoints)
        if edge['properties'].get('origin') == 'lifecycle_assertion' and edge['type'] in LINK_PREDICATES and evidence_valid:
            traced.update({edge['source'], edge['target']} & requirement_ids)
    graph['metadata'].update(source='managed_workspace', source_id=source_id, source_label=repository.label,
        revision=revision, indexed_at=datetime.now(timezone.utc).isoformat(), files=code_graph['metadata']['files'],
        retention='session memory', connectors=statuses, coverage={'requirements': len(requirement_ids),
        'linked_requirements': len(traced), 'unlinked_requirements': sorted(requirement_ids - traced)},
        schema_domains=['AM', 'RM', 'CM', 'QM', 'TRS', 'SCHEMA'],
        limits={'render_nodes': settings.WORKSPACE_RENDER_NODES, 'render_edges': settings.WORKSPACE_RENDER_EDGES})
    graph['architecture_audit'] = audit
    graph['trs_events'] = events
    graph['pipeline_runs'] = pipeline_runs
    # Bind approval to the enriched provider state, checkpoints, and scan evidence.
    graph['metadata']['snapshot_id'] = hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()
    return graph
