"""OSLC consumer used by Polarion, Codebeamer and generic provider profiles."""
import httpx
from rdflib import URIRef
from rdflib.namespace import DCTERMS

from core.config import settings
from services.oslc_service import OSLC, allowed_url, parse_rdf, provider_headers
from services.oslc_store import LINK_PREDICATES


class OSLCClient:
    def __init__(self, provider, transport=None):
        self.provider = provider
        self.headers = provider_headers(provider)
        self.client = httpx.Client(timeout=settings.OSLC_TIMEOUT_SECONDS, follow_redirects=False, transport=transport)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def resource(self, uri):
        allowed_url(self.provider, uri)
        with self.client.stream('GET', uri, headers=self.headers) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                if len(data) + len(chunk) > settings.OSLC_MAX_RESPONSE_BYTES:
                    raise ValueError('OSLC resource exceeds the configured size limit')
                data.extend(chunk)
            graph = parse_rdf(bytes(data), response.headers.get('content-type', '').split(';')[0])
            return graph, response.headers.get('ETag')

    def discovery(self):
        if not self.provider.discovery_url:
            return {'provider_id': self.provider.id, 'product': self.provider.product, 'status': 'not-configured',
                    'query_capabilities': [], 'creation_factories': [], 'dialogs': [], 'shapes': [],
                    'warning': 'Configure discovery_url to inspect this provider service catalog.'}
        graph, _ = self.resource(self.provider.discovery_url)
        visited = {self.provider.discovery_url}
        pending = sorted({str(value) for value in graph.objects(None, URIRef(OSLC + 'serviceProvider'))
                          if isinstance(value, URIRef)} - visited)
        while pending and len(visited) < settings.OSLC_MAX_PAGES:
            uri = pending.pop(0)
            if uri in visited:
                continue
            page, _ = self.resource(uri)
            visited.add(uri)
            graph += page
            if len(graph) > settings.MAX_GRAPH_EDGES:
                raise ValueError('Discovery exceeds the configured triple limit')
            pending.extend(sorted({str(value) for value in page.objects(None, URIRef(OSLC + 'serviceProvider'))
                                   if isinstance(value, URIRef)} - visited - set(pending)))
        def capabilities(predicate):
            values = []
            for subject, target in graph.subject_objects(URIRef(OSLC + predicate)):
                if not isinstance(target, URIRef):
                    continue
                allowed_url(self.provider, str(target))
                values.append({'uri': str(target), 'label': str(next(iter(graph.objects(subject, DCTERMS.title)), predicate))})
            return values
        queries, creations = capabilities('queryBase'), capabilities('creation')
        return {'provider_id': self.provider.id, 'product': self.provider.product,
                'status': 'partial' if pending or not (queries or creations) else 'ready',
                'query_capabilities': queries, 'creation_factories': creations,
                'dialogs': capabilities('dialog'), 'shapes': capabilities('resourceShape')}

    def prepare_link(self, source, predicate, target):
        if not self.provider.allow_writes:
            raise ValueError('Provider writes are disabled in central configuration')
        if predicate not in LINK_PREDICATES:
            raise ValueError('Predicate is outside the supported contextual-link profile')
        graph, etag = self.resource(source)
        if not etag or etag.startswith('W/'):
            raise ValueError('Remote collaboration requires a strong resource ETag')
        if not any(graph.triples((URIRef(source), None, None))):
            raise ValueError('The provider response does not describe the selected resource')
        return {'expected_etag': etag, 'already_linked': (URIRef(source), URIRef(predicate), URIRef(target)) in graph}

    def apply_link(self, source, predicate, target, expected_etag, authorize=None):
        if not self.provider.allow_writes or predicate not in LINK_PREDICATES:
            raise ValueError('This provider or predicate is read-only')
        graph, current_etag = self.resource(source)
        if current_etag != expected_etag:
            raise httpx.HTTPStatusError('ETag conflict', request=httpx.Request('PUT', source), response=httpx.Response(412))
        graph.add((URIRef(source), URIRef(predicate), URIRef(target)))
        content_type = self.provider.write_content_type
        body = graph.serialize(format='xml' if content_type == 'application/rdf+xml' else 'turtle').encode()
        if len(body) > settings.OSLC_MAX_RESPONSE_BYTES:
            raise ValueError('Updated OSLC representation exceeds the size limit')
        if authorize:
            authorize()
        # Redirects remain disabled, so credential-bearing writes never follow another endpoint.
        with self.client.stream('PUT', source, content=body, headers={**self.headers, 'Content-Type': content_type, 'If-Match': expected_etag}) as response:
            response.raise_for_status()
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > settings.OSLC_MAX_RESPONSE_BYTES:
                    raise ValueError('Remote write response exceeded the limit; reconcile before retrying')
            return {'etag': response.headers.get('ETag'), 'status_code': response.status_code}

    def link_exists(self, source, predicate, target):
        graph, _ = self.resource(source)
        if not any(graph.triples((URIRef(source), None, None))):
            raise ValueError('The response does not describe the selected resource')
        return (URIRef(source), URIRef(predicate), URIRef(target)) in graph
