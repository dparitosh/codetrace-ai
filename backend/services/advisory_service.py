"""Opt-in, administrator-configured advisory lookup; no public fallback."""
import json
import time
from datetime import datetime, timezone

import httpx
from core.config import settings
from services.oslc_service import server_secret


def advisory_evidence(sbom):
    evidence = {'status': 'disabled', 'provider': settings.VULNERABILITY_PROVIDER,
                'checked_at': None, 'checked_components': 0, 'skipped_components': 0,
                'matches': [], 'limitations': ['Package advisory matches do not prove runtime exploitability or license compliance.']}
    if settings.VULNERABILITY_PROVIDER == 'disabled':
        return evidence
    evidence['checked_at'] = datetime.now(timezone.utc).isoformat()
    components = sbom['components']
    queries, refs = [], []
    for component in components:
        purl, version = component.get('purl'), component.get('version')
        if not isinstance(purl, str) or not purl.startswith('pkg:') or len(purl) > 4096 or not isinstance(version, str) or not version:
            evidence['skipped_components'] += 1
            continue
        queries.append({'package': {'purl': purl}, 'version': version})
        refs.append(component['ref'])
    if not queries:
        evidence['status'] = 'unavailable'
        evidence['limitations'].append('No versioned package URLs were available for advisory lookup.')
        return evidence
    token = server_secret(settings.VULNERABILITY_TOKEN_ENV)
    headers = {'Accept': 'application/json'}
    if token:
        headers[settings.VULNERABILITY_KEY_HEADER] = ('Bearer ' if settings.VULNERABILITY_KEY_HEADER == 'Authorization' else '') + token
    deadline = time.monotonic() + settings.VULNERABILITY_TIMEOUT_SECONDS
    total_bytes = 0
    try:
        with httpx.Client(follow_redirects=False, trust_env=False) as client:
            size = settings.VULNERABILITY_BATCH_SIZE
            for start in range(0, len(queries), size):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('deadline')
                batch = queries[start:start + size]
                data = bytearray()
                with client.stream('POST', settings.VULNERABILITY_API_URL, json={'queries': batch}, headers=headers, timeout=remaining) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        total_bytes += len(chunk)
                        data.extend(chunk)
                        if total_bytes > settings.VULNERABILITY_MAX_RESPONSE_BYTES or time.monotonic() > deadline:
                            raise ValueError('response budget')
                payload = json.loads(data)
                results = payload['results']
                if not isinstance(results, list) or len(results) != len(batch):
                    raise ValueError('result cardinality')
                matches = []
                for offset, result in enumerate(results):
                    if not isinstance(result, dict) or not isinstance(result.get('vulns', []), list):
                        raise ValueError('result schema')
                    for advisory in result.get('vulns', []):
                        if not isinstance(advisory, dict) or not isinstance(advisory.get('id'), str) or not advisory['id'] or len(advisory['id']) > 512:
                            raise ValueError('advisory identity')
                        matches.append({'component_ref': refs[start + offset], 'advisory_id': advisory['id']})
                evidence['matches'].extend(matches)
                evidence['checked_components'] += len(batch)
        evidence['status'] = 'partial' if evidence['skipped_components'] else 'complete'
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RecursionError):
        evidence['status'] = 'partial' if evidence['checked_components'] else 'unavailable'
        evidence['limitations'].append('Advisory service failed, timed out or returned invalid/bounded data. Unchecked packages have unknown vulnerability status.')
    return evidence
