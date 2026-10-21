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

Resource kinds include requirements, architecture, changes, tests/plans/scripts/execution records/results, features, variants, products, configurations, tracked resources, builds and resource shapes. Use the current `LifecycleResource` OpenAPI schema for the complete enum. An optional `provider_uri` identifies each resource's provider. Manifest-level `configuration_uri` identifies the lifecycle configuration. Every link requires an `asserted_by` URI. Unknown resource URIs create explicit unresolved placeholders and diagnostics; unknown code IDs are rejected.

`POST /api/v1/trace/query` takes the same source and manifest plus `start` (one of `uri` or `code_id`), `direction` (`incoming`, `outgoing`, `both`), `depth` (0–12), `max_nodes` (1–500), and optional `predicates`. Results contain witness node paths and a truncation flag. These describe graph reachability, not proven causal impact. With no predicate filter, containment participates in traversal; supply lifecycle predicates for focused trace queries.

`POST /api/v1/trace/jsonld` takes the materialization request and returns `application/ld+json`. It preserves predicate URIs and emits reified statements carrying assertion provenance. Imports are bounded to 2,000 resources and 5,000 links, in addition to existing source limits.

`POST /api/v1/agent/context` accepts optional `trace_manifest`. Its `lifecycle_trace` is a bounded neighborhood around the best-ranked code symbol (or repository if none), excluding containment edges to avoid treating shared ownership as lifecycle evidence.

## OSLC boundary

Use the standard [OSLC RM vocabulary](https://docs.oasis-open-projects.org/oslc-op/rm/v2.1/requirements-management-vocab.html) for `implementedBy` and `validatedBy`, preserving their direction. Requirement → feature → variant → product links use explicit application predicates such as `urn:codetrace:vocab:specifiesFeature`, `urn:codetrace:vocab:hasVariant`, and `urn:codetrace:vocab:includedIn`. These are CodeTrace conventions, not OSLC standard predicates.

Manifest processing treats URIs as identifiers and never fetches them. Separately, centrally configured network/file adapters support RDF ingestion, authenticated discovery and configuration-context headers. The bounded OSLC server profile under `/oslc` publishes approved resources with ETags, queries, shapes and TRS. Session-bound APIs under `/api/v1/oslc` publish approved snapshots and prepare/approve/apply/reconcile remote link proposals. This is a supported application profile, not a claim of full OSLC conformance or live vendor certification. Durable TRS replay and its conservative full-rebuild fallback are described in [Technical design](TSD.md). A requirement-to-test link does not imply a passing execution result. Feature links do not implement feature-model constraints or variant derivation.

Python extraction uses AST structure; other languages have structural/heuristic coverage. Complete cross-module semantic resolution is not provided. The UI renders a bounded projection with contextual traversal, filtering, hierarchy and reported omissions. Approved exports retain the full snapshot. Model stress tests do not establish browser frame-rate guarantees.

The force network includes functions, methods and variables by default. Its bounded preview grows along actual relationships, balances visible classifications and reserves the edge budget for a spanning forest before parallel links. It reports connected components and omitted nodes/edges; separate source components, domain/relationship filters and insufficient edge budgets can still produce multiple components. Search covers the full snapshot, and expanding a resource reveals its bounded context. Reset restores symbol visibility and the force network layout.

Node fill and letter identify the classification (for example class, function, method or feature); the outer ring identifies the lifecycle domain. The legend counts the visible projection, and the color selector can instead color by domain. Inspectors and the resource table use the same classification badges. Features require explicit manifest/provider artifacts and trace links; the scanner does not infer product features from source classes. A snapshot with zero imported features reports that fact in the graph legend.

## Verification

`backend/tests/test_traceability.py` covers hierarchy, lifecycle traversal, bounded queries, repository isolation, content-sensitive snapshots, invalid links, unresolved resources, duplicate assertion handling, JSON-LD provenance, agent integration, and OpenAPI registration. Run `.venv\Scripts\python.exe -m pytest -q` from the repository root.

## Managed workspace and SBOM

`POST /api/v1/workspace/sync` selects a centrally configured source ID and creates a pending graph review. The snapshot incorporates provider/CI status, SBOM components, deletion state and provenance before computing its digest. `POST /api/v1/workspace/context` retrieves a bounded neighborhood from an existing session review. `GET /api/v1/workspace/sbom/{review_id}` exports an approved inventory. See [testing.md](testing.md) and [audit-status.md](audit-status.md).
