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
