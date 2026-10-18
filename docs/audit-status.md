# Current audit status

The [2026-10-18 follow-up audit](audit-2026-10-18.md) records 35 findings at review time
from 50 checks, including the historical P1 repository-local Git filter execution
path. The subsequent agent implementation removes worktree status inspection and
adds a passing filter-isolation regression. It also fixes tracking-only coverage,
the post-refresh session race, expiry cleanup in local analysis, parallel labels
and graph navigation state. Other findings in that dated report remain open. Earlier resolved rows below are historical and do not supersede that audit.

Updated 2026-10-18. Scope: the active local-first workspace, graph/search/inspection,
Git boundary, sessions/reviews, SBOM, TRS/CI, OSLC collaboration and optional ORM.
This is bounded source/test/browser evidence, not a guarantee that all bugs have
been found, a security certification or a claim of production readiness.

## Resolved in the current branch

| Priority | Finding | Result |
| --- | --- | --- |
| P1 | Git clones inherit executable host filters, helpers and templates | Isolated configuration/environment, empty templates, disabled helpers/hooks/redirects; managed private tokens use named server variables |
| P1 | Legacy persistence can commit partial analyses | One transaction with rollback coverage |
| P2 | Sessions only work in one process | Optional SQLite sessions with hashed tokens, atomic review decisions, shared worker leases and expiry/end cleanup |
| P2 | Database errors look like empty success | Explicit unavailable/failed-operation errors; no blind write retry |
| P2 | Existing PostgreSQL schemas lack upgrade steps | Explicit transactional versioned migration for long IDs, scoped identity uniqueness and endpoint constraints |
| P2 | No active SBOM inventory | Supported JSON imports, npm lockfile generation, graph attachment and approval-gated export |
| P2 | TRS checkpoints are display metadata only | Durable replay with exact-event continuity, deletion/recreation and full-rebuild fallback |
| P2 | CI reads only one response | Validated same-endpoint pagination with explicit page/run bounds |
| P2 | Remote link client has no in-app approval flow | Prepare, approve/reject, conditional apply, conflict/unknown states and read-only reconciliation |
| P2 | Search/index and inspector silently hide extra matches/links | Identity-aware search, visible totals and expandable result/relationship lists |
| P2 | AI evidence drops status/outcome/deletion properties | Bounded allowlisted properties accompany citations; unrelated credential fields are excluded |
| P2 | Invalid OSLC title escapes become server errors | Malformed literals return HTTP 400 |
| P2 | Hierarchy/filter/selection loses context | Directed/scope-aware traversal, controlled highlights, explicit containment identities, preserved frontier/viewport and collapse state |
| P3 | Siemens filter selectors miss custom-element hosts | Native Siemens variants and pressed-state feedback |
| P3 | Repeated collapse indexing and oversized entry chunk | One containment index per projection, deferred views and separate vendor chunks |

Earlier installation/lockfile, dependency, CORS, RDF bounds, publication tombstone,
session race and provenance fixes remain covered by the maintained regression suite.

## D3 migration verification (2026-10-18)

- Removed the old graph package from runtime dependencies, lockfile and build chunks.
- Dynamic SVG rendering uses modular D3 force, drag and zoom with bounded projections.
- Fixed stale position-force targets crashing collapsed-node restoration, overlapping
  self-links, and mixed containment/lifecycle hierarchy layering.
- 22 native frontend contracts and 20 Vitest tests pass; TypeScript, ESLint and build pass.
- Graph engine chunk: 62.09 kB (21.11 kB gzip), previously 441.69 kB.
- Browser checks used a disposable eight-resource AM/RM/CM/QM/CODE/SBOM fixture
  with the actual React graph component: motion changes, pause stability, physical
  drag/pin/release, collapse/restore, Shift+Enter expansion and snapshot clearing.
  This pass did not revalidate live backend/vendor integration or large-graph frame rates.

## Earlier full-workspace verification (2026-10-15)

- Backend/core and optional ORM suite: 136 tests pass (SQLite ORM; no live PostgreSQL migration).
- Native graph/session/install contracts: 21 tests pass.
- Frontend Vitest: 15 tests pass in the final validation run.
- TypeScript, ESLint and production build pass. Current entry chunk is about 499 kB;
  no chunk exceeds the default 500 kB advisory. This is chunking/deferred loading,
  not a claim that the entire transferred application shrank by the same amount.
- Model benchmark on this workstation: 50,000 nodes / 99,997 edges; overview 49 ms,
  six-hop context 37 ms, capped focus 26 ms, 40 collapsed roots 47 ms, ID search 16 ms.
  Timings vary and exclude browser layout/rendering.
- Browser: latest workspace synchronized code plus SBOM; search expanded 12 to 24
  of 1,995 matches; inspector expanded 12 to all 14 relationships; containment
  collapsed 15 visible nodes to 2 and expanded again; selected SBOM filter was visible. The latest browser pass also verified downstream containment, wrapped hierarchy labels, light/dark themes, approval-gated SBOM controls and clearing all graph/inspector evidence on session end.

## Remaining deployment and integration limits

- Live Polarion/Codebeamer, Ollama inference and PostgreSQL migration validation
  need configured services/disposable fixtures; they were not available locally.
- SQLite coordination is for workers on one host/local disk, not multiple hosts.
  Memory mode still requires one worker. Sessions do not provide user accounts,
  independent sign-off, RBAC or an authenticated enterprise admin boundary.
- SBOM generation covers configured npm lockfiles; imports preserve supplier
  assertions. No build-artifact attestation, full ecosystem inventory, vulnerability
  database evaluation or license compliance verdict is provided.
- TRS/CI remain bounded. Lost/expired bases or checkpoints require resynchronization.
  Published bases have a bounded retention window. Test each vendor's exact profile.
- Git still needs a trusted executable/service account/local repository configuration;
  clone disk quotas and interruption of individual parser operations are not provided.
- Static extraction, similarity and graph reachability do not prove semantic
  equivalence, complete call resolution, passing tests or causal impact.

## Documentation cleanup

This page replaces overlapping dated root audit/fix/completion reports, including
legacy MCP and Pareto claims. The obsolete E2E guide and bugfix history are replaced
by [testing.md](testing.md). Historical content remains in Git history. Empty Compose
configuration, duplicate environment template, obsolete diagnostic scripts and
unused packaging exclusions are removed; active source, lockfiles and private
`.env.local` configuration are preserved.

## Agent runtime follow-up

Session Ollama registration (URL/key/header/chat/embedding models), native REST
connectivity checks, bounded contextual embeddings, three read-only graph-agent
roles, model-directed tools, citation validation and evidence highlights are now
implemented. See README for user configuration and TSD for limits. Final validation:
152 backend/core/ORM tests, 20 Vitest tests, 23 native frontend contracts, TypeScript,
ESLint, production build and the disposable HTTP-fixture browser flow pass. No real
Ollama model or live ALM/PostgreSQL integration was tested in this pass. Durable
agent jobs, streaming/resume, long-term memory, distributed coordination and a
persistent whole-corpus vector index are not implemented.
