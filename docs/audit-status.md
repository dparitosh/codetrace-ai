# Current audit status

## Answer reliability and installation review (2026-11-02)

Optional embeddings now use a retrieval sub-budget, planning reserves time for
one tool-free final/JSON-repair attempt, and the frontend uses the total agent
budget while session AI configuration is loading. The parent execution deadline
is never extended. Invalid or invented citation IDs remain rejected. Model-mode
citations identify actual inline-used evidence; full observed context is retained
separately. Deterministic summaries obey the configured answer-length limit and
native output-token exhaustion has a specific diagnostic. See the
[detailed audit and remediation record](model-answer-reliability-audit.txt).

Windows setup now rejects unsupported Python before environment creation, and
the foreground frontend launcher invokes Node/Vite directly instead of the npm
PowerShell shim. Bash entrypoints have enforced LF endings for Windows checkouts.
Maintained installation, configuration, native-parser and agent-contract docs
were reconciled; removed hosted workflows remain removed. Historical audit counts
below describe their dated runs rather than current totals.

Validation: 408 backend/core tests, 55 frontend tests and 23 native contracts pass;
TypeScript, ESLint, PowerShell parsing and production build pass. Four offline
launcher regressions use disposable copies/fake executables. All ten tracked
Markdown documents were checked for local file links, with none broken. This is
not a fresh dependency installation or Linux/macOS runtime certification: Bash
was unavailable in this environment. Existing AG Grid bundle-size advice remains.
The local app passed a synthetic, AI-disabled API smoke check after activation;
no live Ollama or customer model/gateway execution was performed. The 50k-node
model benchmark completed, but overview/focus took 4.88/2.32 seconds in this run;
large-graph performance needs separate review and browser frame rate was not tested. Synchronous
network cancellation remains cooperative, not forced socket/CPU termination.

## Removed host integration verification (2026-10-29)

The follow-up check found two leftover scripts under `.github/scripts` that
called retired MCP endpoints. Those scripts and the remaining host-specific
issue/pull-request templates are removed. Verification read all 189 remaining
tracked files, including hidden paths, and classified each remaining host-name
match. Matches remain only in negative regression tests, historical audit
citations/inventories and third-party lockfile funding/homepage metadata.
No dependency artifact is resolved from the removed host. Live OpenAPI contains
56 paths and no removed-host or MCP route; local and GitLab analysis remain.
Regression guards now cover every file under the hidden host directory, runtime
source names/response contracts, manifests, launch scripts and registered routes.
This is verification of integration removal, not a complete repository security
or semantic correctness audit.

## Startup configuration diagnostics (2026-10-22)

URL settings now validate at their named fields, with indexed diagnostics for
the AI allowlist. HOST rejects schemes, ports and paths before generating public
URLs. Settings validation hides input values; the native launcher prints concise
field diagnostics instead of a traceback containing the settings dictionary.
Blank optional OSLC publication URLs retain their derived default. All 216
backend/core tests pass, including 14 startup regression cases. No live model
requests were made. A malformed configuration on another installation still
requires correcting the field identified by that installation's diagnostic.

## Page density and purpose audit (2026-10-21)

Removed repeated global metric cards, decorative slogans/eyebrows, snapshot
blocks, footer branding and duplicate configuration entry points. Shared context
is one compact source/snapshot/status line. Session retention, description search,
advanced graph controls and graph help are expandable. Classification legend and
projection limits remain visible. The companion opens on demand or row selection.

Source overview now provides structure/language inventory and filtering coverage;
quality leads with scores/recommendations, security with file findings, and domain
overviews with imported types, link counts and resources without explicit edges.
Graph and AG Grid occupy separate sub-tabs; keyboard tab navigation is supported.
The existing graph canvas and visited grid persist while their panels are hidden.
Provider gaps are reported explicitly rather than padded with repeated summaries.
Production build, TypeScript and ESLint pass, with 31 unit tests and 23 native
contracts. Browser verification used the configured 39,731-resource snapshot:
source inventory/languages, quality, security, empty RM overview, resource and
relationship grids, optional technical columns, retained filters, keyboard tabs,
row inspection, graph, delivery, review, administration and connections. Populated
remote lifecycle-provider views and live Ollama execution were not exercised.

## Shared graph workspace follow-up (2026-10-21)

Source overview, quality and security assessments now share the active review
with lifecycle domains, the persistent graph canvas, resource tables, search
and the companion. Assessments are computed from the graph's exact filtered
source files and retained in the same result. Domain selection scopes search
and initial agent retrieval. Inspecting a file includes its bounded static
findings in agent evidence. Model execution remains read-only and optional.
Review-history decisions propagate to the active view without replacing the
graph object for an unchanged result digest. Final automated validation:
202 backend/core/ORM tests, 23 frontend unit tests and 23 native frontend
contracts pass; TypeScript, ESLint and production build pass. The existing
deferred AG Grid bundle-size advisory remains. No live Ollama validation.

## 2026-10-21 P2 fixes and source-folder configuration

The 23 reproduced defects from the edge audit and four additional AI connection
defects are fixed in the working tree. The edge diagnostic now passes all 32
checks. Regression coverage includes session-owned companion routing/disable,
key headers, credential retention restricted to the same base/header, upstream
JSON validation, configuration-scoped OSLC resources/links, RDF evidence and
validators, TRS replay, SBOM imports, extraction, capacity and ORM locations.
The capacity diagnostic now expects an explicit HTTP 429 rejection.
Verification: 199 backend/core/optional ORM tests and 23 native frontend
contracts pass, including 44 new regression cases. A live read-only folder sync
of the configured external project processed 1,054 files into 39,731 resources
and 57,064 relationships, with generated Python environments excluded.

`SOURCE_FOLDER` selects the default local workspace independently of the launch
directory. An explicit `MANAGED_REPOSITORIES` catalog overrides it. See README.
No live Ollama, gateway, ALM or PostgreSQL server was used for verification.
Older source-traced findings below are historical and are not all covered by
this bounded repair pass. The table-bundle warning and unsupported OCR/ontology,
dedicated circuit-breaker and dedicated Ollama-concurrency options remain.

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


## Product-line optimization assessment (2026-11-06)

Custom GT/ROC cellular analysis and SPLE recommendations are implemented locally with configurable units, projection charts, incidence previews, candidate evidence and approved exports. No analyzed source files are rewritten. The PMem assessment is read-only and excludes generated/log/data folders explicitly; it is not a complete semantic audit of every artifact. Feature constraints and source-project regression results are not established. An explicitly approved live gpt-5-nano metadata review at api.openai.com completed on 2026-11-06. Candidate identifiers were validated; semantic advice remains unverified and source was not modified. Duplicate projections omit additional shared-module/import/configuration/test scaffolding; they are not realized reductions. Validation details and exact artifact hashes are in the external assessment receipt.

Validation: 422 backend/core tests and 57 frontend tests passed; TypeScript, ESLint and production build passed. A synthetic browser flow against actual local APIs verified analysis, matrix filtering/selection, approval eligibility, stale assumptions, the six-stage SPLE plan and session cleanup. ZIP contents/hashes were verified by API tests; browser ZIP download was not independently verified. Existing large vendor-chunk and dependency deprecation/cache warnings remain. No PMem tests ran. A subsequent explicitly approved live metadata-only model review completed; it did not change projections or establish source equivalence.


## Structured product context follow-up (2026-11-06)

The optimizer now accepts repository-independent capabilities, features, owners,
variation constraints, product variants, document evidence and explicit file or
function mappings. Offline OpenAPI JSON adds sanitized operation evidence; raw
contracts, remote references and server URLs are not executed/fetched or retained
in output. Deployment membership remains distinct from product feature mapping.

Optional AI classification uses the registered session Ollama or configured central
OpenAI-compatible endpoint. Without a feature model it may propose a provisional
taxonomy. Unknown IDs/citations and malformed/truncated answers are rejected. Model
proposals remain unverified; the UI can copy a selected proposal to draft context,
then requires another deterministic analysis. No automatic source change occurs.
No PMem-specific defaults or credentials were added.

Validation includes synthetic repositories in unrelated folders/languages,
feature constraints, exact function scope, OpenAPI privacy/ambiguity, session
isolation and mocked provider failures. Browser verification used synthetic source
and real local APIs: OpenAPI upload, configured mapping, invalid product diagnosis,
lexical draft acceptance, stale-result blocking, rerun, function evidence selection
and session cleanup passed. No new live provider request or PMem refactor ran.

Final classification validation: full backend/core suite 438 passed; focused final classification/optimizer suite 30 passed; frontend suite 59 passed. TypeScript, ESLint and production build passed. Existing pytest cache/dependency deprecation and large vendor-chunk advisories remain. Feature-profile groups use exact configured feature sets; they do not assert semantic equivalence.


## Completion verification (2026-11-09)

Fixed AI context omission of existing capability identifiers and central
capability-only context fallback. API and CLI now share standalone report/chart
artifact generation and central product-context/unit defaults. Approved API exports
include the full report and current/projected file-group chart as well as matrices,
call evidence and receipts. Source approval remains distinct from feature-model
correctness, and model proposals are not automatically promoted or exported.

Validation: 440 backend/core tests and 59 frontend tests passed; TypeScript, ESLint,
production build and diff whitespace checks passed. An actual CLI run against an
independent synthetic Python/JavaScript source folder used central product context
and offline OpenAPI, mapped two files, left one unresolved, checked two declared
products, verified all six artifact hashes and left source unchanged. The running
localhost API rejected pending export, accepted exact source approval, exported
all six hashed artifacts and then ended the disposable session. No new live model
request, PMem source change, credential copy, commit or push was performed.
Existing cache/dependency deprecation and vendor chunk-size advisories remain.


## Visual business report (2026-11-09)

Replaced the JSON-led report with a self-contained visual HTML assessment:
current/projected differences, dependency-coefficient heatmap, declaration-fingerprint
code-overlap coefficients, identical-sample before/after matrix charts, similarity
network, file-cluster cards and explicit complete-link formation decisions. CSVs
remain optional engineering evidence with their distinct purposes explained.
The API and CLI use this shared report for any configured supported source.

Code similarity is Jaccard overlap of distinct parser declaration fingerprints,
not semantic equivalence. Comparison is bounded to 200 fingerprinted files,
prioritizing retained duplicate candidates then declaration count; positive pairs
are ranked and the top 100 retained (20 displayed). Uncompared files and missing
fingerprints are disclosed rather than scored zero. Dependency coefficients remain
separate and drive cell formation at the configured threshold. Matrix ordering
changes presentation only and is not a source refactor or savings claim.

Existing PMem and independent-validation reports were regenerated from captured
analysis evidence, with receipt hashes updated; no source scan, model request or
PMem modification occurred. Browser inspection verified charts, heatmap, matrix
previews and graph labels. Full suite: 443 backend/core tests passed. Final focused
render/export checks cover hashes, escaping, coefficient arithmetic, missing evidence
and bounded comparison behavior. Existing test/dependency advisory warnings remain.


## In-app visual report preview (2026-11-09)

Added a direct Open visual report action and a native modal viewer inside the
product-line workspace. The same report generator powers the session-owned preview
endpoint and approved export. A separate analysis run/download is not required.
Pending sources show a draft label; the server still gates export on exact source
approval. Assumption/context/contract changes invalidate cached previews. The
viewer isolates generated HTML in a sandboxed inline document with restrictive CSP,
no script or same-origin privileges, internal-only section navigation and disabled
supporting-file links. A close action restores focus to the report trigger.

Validation: 445 backend/core tests and 61 frontend tests passed, plus TypeScript,
ESLint and production build. Actual local API/browser checks verified pending and
approved controls, in-frame charts and section links, close/opener focus, toolbar
Escape, stale-assumption blocking and regeneration. The synthetic session and
preview fixture were removed. No PMem changes or new model requests occurred.
Existing advisory warnings remain; changes are local and uncommitted.


## Reduction projections and model recommendations (2026-11-09)

Added prominent low/planning/upper reduction quantities, remaining size and
percentage columns, with formulas and measured/illustrative similarity examples.
Optional report AI advice now shares the configured provider transport with
classification, includes existing capability context there, and validates a
bounded recommendation schema and candidate/evidence references. Computed
projections are never replaced by model output. Preview/export respects the
include_llm option; approval is checked before export calls a provider. Reports
show failed/disabled/not-requested model status without claiming a model review.
Historical saved reports retain their prior accepted advisory; regeneration in
this pass changed presentation only and invoked no live model or source scan.

Validation: 449 backend/core tests and 61 frontend tests passed; TypeScript,
ESLint and production build passed. Controlled fixtures verify projection
immutability, rejected invented references, report/export inclusion, opt-out,
approval gating and small percentage arithmetic. Browser verified reduction
charts and actual worked examples. No live Ollama test or new external model
request was performed. Existing advisory warnings remain.


## Pre-push review (2026-11-09)

Scope: pending product-line assessment/report/classification changes, extraction
metadata additions, workspace/API integration, tests and documentation. This is a
review of the change set, not a claim of a new whole-application or live-provider
audit. Generated customer reports, runtime data and private configuration are not
part of the commit.

Confirmed and fixed:

- OPT-A01 (Medium, API/reliability): report/ZIP rendering previously ran after the
  analysis worker was released, and export did not recheck session validity after
  serialization. Rendering/compression now stays inside the worker reservation;
  source-session validity and the total deadline are checked before returning.
  Regression tests end the session during ZIP rendering (401), verify the worker
  remains occupied, and advance the render clock beyond its deadline (504).
- OPT-A02 (Medium, AI/reliability): a model could consume the entire request budget,
  leaving no time to produce the evidence report. Model deadlines now reserve the
  configured final-answer allowance (capped at one quarter of the parent request)
  for rendering and response preparation. Request deadline checks still apply.

Validation: 451 backend/core tests and 61 frontend tests passed; TypeScript, ESLint,
production build and whitespace checks passed. Provider tests use controlled mocks;
no live Ollama or new external model request was performed. Existing pytest cache
permissions/dependency deprecation warnings and large vendor-chunk advisory remain.
Bounded parser coverage, unverified semantic recommendations and projected (not
achieved) reductions remain explicit product limitations.
