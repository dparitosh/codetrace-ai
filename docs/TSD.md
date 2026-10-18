# Technical design

## Components

| Component | Responsibility |
| --- | --- |
| `frontend/src/workspace` | Siemens iX shell, D3 force graph, index, inspector, companion and ALM proposal UI |
| `backend/api` | Bounded FastAPI contracts, sessions/reviews, managed sync, OSLC publication/collaboration |
| `codegraph_core` | Python AST and configurable structural scanners; reusable graph/context core |
| `services/workspace_service.py` | Assemble code, lifecycle, CI and SBOM into one fingerprinted snapshot |
| `services/git_isolation.py` | Isolate Git configuration, templates, helpers and child environment |
| `services/oslc_service.py`, `oslc_client.py` | Bounded RDF consumption, discovery and conditional remote links |
| `services/trs_cache.py` | Durable per-provider/configuration checkpoints and incremental replay |
| `services/oslc_store.py` | SQLite publication identities, ETags, TRS bases/events and proposal audit transitions |
| `services/shared_reviews.py` | Optional shared SQLite sessions/results, atomic decisions and worker leases |
| `services/sbom_service.py` | Supported JSON import, npm lockfile inventory and graph attachment |
| `services/companion_service.py` | Evidence retrieval, allowlisted properties, AI requests and citation checks |
| `database` | Optional legacy ORM persistence, explicit bootstrap and PostgreSQL migrations |

## Data and approval flow

Managed source IDs resolve through central configuration. Scans do not execute
project code. Remote clones use isolated Git settings. OSLC pages stay inside
configured origin/path prefixes; redirects and external JSON-LD contexts are
disabled. Files, RDF, graph growth, AI context/output, CI windows and storage
have separate configured bounds.

Snapshots retain directed predicates, provenance, gaps, revision evidence and
tombstones. A digest covers the enriched result. Decisions use revision/digest
checks; exports and publication require approval. Link proposals capture a strong
ETag and immutable endpoints, then use versioned transitions before conditional
PUT. Conflicts/unknown outcomes cannot be automatically retried. Reconciliation
reads the current provider graph.

## Storage and scaling

Memory reviews require one process. Optional SQLite reviews hash tokens, share
transactions and worker leases across processes on one host, and survive restarts
until end/expiry. Publication and TRS caches also use local SQLite. Do not use a
network filesystem or treat this as multi-host coordination. Session access is
not account authentication; protect the app and its data directory accordingly.

Legacy PostgreSQL is not required by the active API. Bootstrap creates missing
tables. Explicit versioned migrations widen existing IDs/predicates and use
fixed-size SHA-256 endpoint keys to avoid indexing long Unicode URIs. Duplicate
or dangling legacy data fails the transaction rather than being discarded.
Database query failures raise storage errors instead of returning empty success.

## Graph and frontend performance

Projection enforces node/edge caps and preserves breadth-first order in focus.
Collapse builds one shared containment index per projection. Foreign predicate
local names do not become containment. Compatible views preserve positions and
viewport state; React controls selection while D3 owns mutable simulation copies.
The SVG renderer provides force, hierarchical force, circular, concentric and grid
layouts, drag/pin/release, pause/resume/reheat, zoom/pan and keyboard expansion.
It stops simulations and disconnects observers on unmount. Layout forces are
rebound before restoring collapsed nodes. Reduced-motion preference starts paused.

React, icons and modular D3 have separate production chunks. Graph, companion,
review, collaboration and optional analysis views load on demand. Run
`node frontend/graph-performance.mjs` for model benchmarks; these do not measure
browser layout or frame performance. See [testing.md](testing.md).

## Session AI and graph agents

`services/ai_connection.py` normalizes native Ollama REST operation URLs, enforces
registered exact bases, supports the three configured proxy key headers and bounds
request/response bytes and network timeouts. `/api/tags`, `/api/chat` and `/api/embed`
are called server-side without redirects or inherited HTTP proxies. Users configure
URL/key/chat/embedding models in Connections; no secret is sent to browser storage
or returned by settings APIs. Additional bases require central configuration.

`ReviewStore.ai_profile` stores memory-mode session overrides. SQLite mode uses a
session-owned `session_ai` table with Fernet-encrypted JSON and cascading expiry/end
removal; the encryption key derives from the caller's unpersisted session token.
This supports same-host workers, not distributed identity or an enterprise secret
vault. Anyone holding a session token already controls that session's evidence and
AI settings. Deploy behind an appropriate authenticated boundary.

`services/agent_workspace.py` provides three role profiles and a bounded native
Ollama tool-call loop: search_graph, inspect_resource, traverse_graph, coverage_gaps
and similar_resources. Tool arguments are validated and tools are read-only; there
is no arbitrary HTTP, filesystem, code execution or autonomous publication tool.
Only observed citation IDs are accepted. This checks citation identifiers, not
semantic truth of every model sentence. Session ownership is checked during tools,
REST reads and final response. Budgets cap model steps, batches, context and response
size; network reads retain the configured per-read timeout, so the elapsed deadline
is cooperative rather than a preemptive process-kill guarantee.

Graph search weights resource identity/labels above contextual neighbor matches.
Hybrid retrieval embeds allowlisted properties and up to six directed neighbors,
uses Nomic task prefixes when appropriate, and combines bounded cosine similarity
with lexical scores. Each request builds an ephemeral index of at most
AI_EMBEDDING_MAX_NODES candidates, reused within its agent run; there is no persistent
vector database or background full-corpus index yet. Results disclose candidate
coverage and embedding failures. Model/tool traces and agent answers are response
artifacts, not a durable workflow/job history; long-running durable workers,
streaming execution events and resumable agent memory remain future work.

Endpoints under `/api/v1/workspace`:

- `GET/PUT/DELETE /ai/config`: masked session settings, registration, reset.
- `POST /ai/models`, `POST /ai/test`: discovery and chat/embedding connectivity.
- `POST /search`: review_id, query, domain, limit, semantic; scored resource results.
- `POST /agent/run`: review_id, question, selected_id, agent_id; verified answer,
  citations, ordered tool trace and highlight IDs.

Frontend settings, contextual search, agent selector/trace and graph evidence focus
use the existing review session. Hidden graph views retain exploration state and
pause physics. Parallel-edge labels follow their individual curved paths. The
post-timing-refresh session check prevents late request results from resurrecting
ended evidence. Local source-analysis results are cleared on session expiry/end.

Managed Git inspection no longer calls worktree status. `git_revision.py` compares
raw file blob hashes with HEAD and lists paths without invoking clean/process
filters. It returns no revision for dirty/untracked, symlink/submodule, oversized or
unknown state. Raw-byte line-ending conversions may conservatively suppress revision
matching. Before/after revision checks reduce concurrent-change misattribution;
an immutable commit snapshot is still preferable for fully isolated ingestion.

Reference patterns were reviewed in PMem's frontend CredentialSettings and backend
ollama_auth/graph_embeddings modules; its service mesh and browser token persistence
were not copied. Native REST contracts follow [Ollama chat](https://docs.ollama.com/api/chat),
[embeddings](https://docs.ollama.com/api/embed), and [model discovery](https://docs.ollama.com/api/tags).

### Editable agent configuration

The session AI profile includes agent_configuration (registered agent IDs to system_prompt/tools), tool_configuration (registered tool IDs to descriptions), and companion_system_prompt. GET /ai/config exposes resolved defaults and registered tools; PUT validates nonblank bounded prompts and unique nonempty registered tool lists. Overrides share the existing encrypted session profile lifecycle. GraphAgent uses the resolved tool list both for model schemas and execution authorization, including automatic evidence collection. A separate runtime system message specifies the response contract; server citation/schema/budget checks remain authoritative. The legacy companion accepts its configured prompt without adding tools.

Administration contains the editor. AG Grid Community provides virtualized resource and relationship tables, loaded lazily with client-side row-model, pagination and text-filter modules. All filtered resources are available; pagination replaces the former 150-row preview. Relationship eligibility uses a set lookup over resource IDs. This is a local session administration surface, not an RBAC or organization-wide policy store.
