# Code index and lifecycle knowledge graph

The NetworkX materializer combines two independent inputs: an analyzed source snapshot and explicitly supplied lifecycle assertions. No GitHub account or lifecycle server connection is required. Code hierarchy is repository → directory-derived package → file → class → method/function. Top-level functions belong directly to their file.

Code identifiers are repository-scoped stable URNs. The original scanner identifier remains in `properties.code_id`; use it when linking lifecycle artifacts to code. IDs remain stable while repository URI and scanner identity remain unchanged, not across renames. Snapshot fingerprints include source content and lifecycle assertions. A supplied revision is a caller assertion, not an independently verified Git commit.

## Input and endpoints

First call `/api/v1/graph/local` or `/api/v1/graph/gitlab` to obtain actual code IDs. Then submit the same source and a manifest to `POST /api/v1/trace/materialize`:

```json
{
  "source": {"files": [{"path": "billing.py", "content": "def charge():\n    return 1\n"}]},
  "manifest": {
    "repository": {"uri": "urn:example:repository:billing", "label": "Billing"},
    "resources": [
      {"uri": "https://alm.example/requirements/42", "kind": "requirement", "label": "Charge payment"}
    ],
    "links": [{
      "source": {"uri": "https://alm.example/requirements/42"},
      "predicate": "http://open-services.net/ns/rm#implementedBy",
      "target": {"code_id": "function:billing.py::charge"},
      "asserted_by": "urn:example:export:1"
    }]
  }
}
```

Alternatively `source` can be `{"project_url":"https://gitlab.com/group/project"}` under the existing GitLab allowlist and clone policy. For the browser upload, save only the `manifest` object as JSON; the folder or URL supplies `source`. Folder selection may add the selected directory name to file paths, so retrieve code IDs from that exact input before linking.

Resource kinds: `requirement`, `feature`, `variant`, `test`, `product`. An optional `provider_uri` identifies each resource's provider. Manifest-level `configuration_uri` identifies the lifecycle configuration. Every link requires an `asserted_by` URI. Unknown resource URIs create explicit unresolved placeholders and diagnostics; unknown code IDs are rejected.

`POST /api/v1/trace/query` takes the same source and manifest plus `start` (one of `uri` or `code_id`), `direction` (`incoming`, `outgoing`, `both`), `depth` (0–12), `max_nodes` (1–500), and optional `predicates`. Results contain witness node paths and a truncation flag. These describe graph reachability, not proven causal impact. With no predicate filter, containment participates in traversal; supply lifecycle predicates for focused trace queries.

`POST /api/v1/trace/jsonld` takes the materialization request and returns `application/ld+json`. It preserves predicate URIs and emits reified statements carrying assertion provenance. Imports are bounded to 2,000 resources and 5,000 links, in addition to existing source limits.

`POST /api/v1/agent/context` accepts optional `trace_manifest`. Its `lifecycle_trace` is a bounded neighborhood around the best-ranked code symbol (or repository if none), excluding containment edges to avoid treating shared ownership as lifecycle evidence.

## OSLC boundary

Use the standard [OSLC RM vocabulary](https://docs.oasis-open-projects.org/oslc-op/rm/v2.1/requirements-management-vocab.html) for `implementedBy` and `validatedBy`, preserving their direction. Requirement → feature → variant → product links use explicit application predicates such as `urn:codetrace:vocab:specifiesFeature`, `urn:codetrace:vocab:hasVariant`, and `urn:codetrace:vocab:includedIn`. These are CodeTrace conventions, not OSLC standard predicates.

This is normalized assertion ingestion and JSON-LD export, not a conformant OSLC server or live OSLC client. URIs are identifiers and are never fetched during manifest processing. Provider discovery, authentication, remote RDF import, persistent storage, incremental synchronization, and configuration negotiation remain future integrations. A requirement-to-test link does not imply a passing execution result. Feature links do not implement feature-model constraints or variant derivation.

Python extraction uses AST structure; other languages have structural/heuristic coverage. Complete cross-module semantic resolution is not provided. The UI is a bounded preview with a full JSON download, not a large-graph exploration engine.

## Verification

`backend/tests/test_traceability.py` covers hierarchy, lifecycle traversal, bounded queries, repository isolation, content-sensitive snapshots, invalid links, unresolved resources, duplicate assertion handling, JSON-LD provenance, agent integration, and OpenAPI registration. Run `.venv\Scripts\python.exe -m pytest -q` from the repository root.
