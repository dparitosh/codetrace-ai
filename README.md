# CodeTrace AI

The **Change workbench** provides a durable conversation and evidence dossier for a
selected source snapshot. Run trace, coverage and change agents to capture evidence,
fill missing draft sections and update agent-owned proposals. Your edited fields are
preserved. Agents propose source-code corrections; they do not modify software files.
Review automated content, save the dossier and submit it to the local review queue.
Approval freezes an exact submitted version; further changes require a new draft revision.
Submitted conversation contents are included in the version digest. Older versions that
did not retain them disclose that gap. Recovery refresh preserves unsaved dossier edits
until you save or explicitly discard them.
Conversation, evidence graph, AG Grid and imported changes have separate views.

Set `CHANGE_DB_PATH`, `CHANGE_MAX_CASES` and `CHANGE_MAX_BYTES` in root `.env.local`
for durable SQLite storage and capacity. This queue is shared by active local review
sessions and survives their expiry; it does not provide enterprise accounts or independent
sign-off. Protect its database/WAL as source evidence. AI-disabled mode provides explicit
deterministic evidence summaries, without claiming model analysis or passing tests.

Approved dossiers can be downloaded with evidence and audit history. External change-ticket
creation is not configured: its UI action is disabled and its API returns 501 after approval.
Existing approved ALM relationship actions remain separate under advanced controls.

The application shell uses [Siemens Industrial Experience React](https://ix.siemens.io/docs/home/installation/react), with light/dark themes, managed-source selection, graph exploration and an evidence-grounded companion. Current verification and limitations are in [current audit status](docs/audit-status.md).

Local-first source analysis, dependency graphs, quality checks, static security patterns, and explicit OSLC lifecycle links. The browser submits supported UTF-8 source files to a local FastAPI service. No database, cloud account, or access token is needed for local folders.

## Install on Windows

Prerequisites: Python 3.10+ and Node.js 22.19+ (22.x), 24.x or 26+ with npm on PATH. Node 24 is used in CI. Git is required for remote Git/GitLab ingestion and local revision evidence. Use a real Python installation, not the Windows Store app-execution alias.

Frontend dependencies use npm and the committed `frontend/package-lock.json`. Run `npm ci` from the `frontend` directory. On Windows, use `npm.cmd ci` if PowerShell blocks `npm.ps1`. If npm reports `EUSAGE` with missing or invalid lock entries, update to this branch's repaired package manifest and lockfile together; avoid bypassing peer checks with `--force` or `--legacy-peer-deps`.

```powershell
Set-Location D:\path\to\codetrace-ai
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
# Optional: .\install.ps1 -PythonPath C:\Python312\python.exe -Dev
.\start.ps1
```

The installer creates `.venv`, installs the local backend/core and locked frontend dependencies, and copies `.env.local.example` to `.env.local` only if it does not exist. It preserves existing configuration. Review `.env.local` before starting.

`start.ps1` launches both services in the background, checks readiness, and prints the actual URLs. Defaults are the frontend at `http://127.0.0.1:3001` and API docs at `http://127.0.0.1:8009/docs`. Use `-NoBrowser` to skip opening a browser. Logs are written under `LOG_DIR`.

```powershell
.\stop.ps1
```

For foreground debugging, run `start-backend.ps1` and `start-frontend.ps1` in separate terminals. Batch compatibility: `start.bat setup`, `start.bat`, and `start.bat stop`.

## Install on macOS or Linux

Install Python 3.10+, its venv support, Node.js 22.19+ (22.x), 24.x or 26+, npm, and optionally Git. From the checkout:

```bash
bash install.sh              # add --dev for Python test dependencies
bash start.sh                # Ctrl+C stops both services
```

Set `PYTHON=/path/to/python3` to select an interpreter. Scripts anchor paths to their own checkout. Docker deployment is not provided; use the maintained native installers.

## Configure Ollama and graph agents

Open **Administration → Connect Ollama REST** and start a review session. Enable
Ollama, enter its REST URL, optional API key, key header, installed chat model and
embedding model (default `nomic-embed-text`). Use **Save and discover models**,
select models, then **Save and test chat + embeddings**. Models are not downloaded
by this app. Blank key input preserves an existing key; use the explicit removal
checkbox to remove it.

The configured central `AI_BASE_URL` is allowed automatically. For another endpoint,
register its exact base in root `.env.local`, for example
`AI_ALLOWED_BASE_URLS=["https://models.example/ollama"]`, then restart. Native operation
URLs such as `/api/chat` are normalized to their base; proxy prefixes are preserved.
Keys support Bearer `Authorization`, `api-key`, or `Ocp-Apim-Subscription-Key`.

Profiles belong to the current review session. Keys are never returned or stored
in browser storage. Memory profiles disappear with the session/process. SQLite
profiles are encrypted using a key derived from the client's unpersisted session
token, shared across workers on one host, and removed with session end/expiry.
This session mechanism is not enterprise account authentication or RBAC.

Synchronize a source, then use **Contextual graph search** for lexical/hybrid
retrieval. Semantic search reports its bounded candidate index; it is not a full
vector-database search. Select results or use **Explore highlighted context** to
traverse evidence. Choose Trace explorer, Coverage reviewer or Change analyst in
the companion. The model can execute allowlisted search, inspect, directed-traverse,
coverage and similarity tools. Expand **Agent execution** to inspect steps and
highlight their evidence. Unsupported model calls/invalid citations/budget exhaustion
fall back to explicit evidence. Agents cannot execute shell commands or modify ALM
links; the existing reviewed approval flow remains responsible for writes.

For architecture, limits and API contracts see [technical design](docs/TSD.md).

## Configuration

One root `.env.local` configures the backend, frontend dev/preview server, launch URLs, review sessions, and source limits. It is ignored by Git. `.env.local.example` documents supported keys; `config/defaults.json` centralizes shared defaults.

Set `SOURCE_FOLDER=D:/GenAI_Projects/Apps/PMem` in `.env.local` to analyze that
folder through the default managed workspace. Any readable local folder can be
selected; it does not need to contain this application or be a Git checkout.
Relative paths resolve from the application checkout. Restart both services
after changing it. The folder is checked when synchronizing, so an unavailable
folder produces an explicit error without scanning another directory.
An explicit `MANAGED_REPOSITORIES` JSON catalog takes precedence over
`SOURCE_FOLDER`; remove that override to use the single-folder setting.
For a catalog entry, relative `manifest_path`, `sbom_path` and `sbom_lockfiles`
resolve inside its selected repository, including a cloned Git repository.
`SOURCE_EXTENSIONS` and `SOURCE_EXCLUDES` configure the supported UTF-8 artifact
selection; file/byte/graph limits remain configurable. A folder scan reports
skipped unsupported/non-UTF-8 files and excluded directories in result metadata.
Selecting a folder does not execute its code, install its dependencies or change
its files. Binary documents and OCR are not parsed by this source scanner.
Python environments containing `pyvenv.cfg` are excluded from managed folder
scans even when they have a custom directory name. Increase `MAX_LOCAL_FILES`
and the documented byte/graph limits explicitly for larger project folders;
exceeding a limit reports an error rather than returning a partial graph.

Precedence: process environment > root `.env.local` > root `.env` (legacy) > defaults. Restart both services after editing. Backend loading is independent of the current working directory. Vite also supports its standard mode-specific env files; avoid them when the backend must share the same settings.

If startup reports an invalid configuration, run `.venv\Scripts\python.exe backend/local_config.py` from the checkout. Diagnostics name the invalid setting without printing its value or the full settings dictionary. Check both `.env.local` and process environment overrides. `HOST` is a bare hostname/IP such as `127.0.0.1`, with no scheme, port or path. `AI_BASE_URL` is a complete HTTP(S) URL; `AI_ALLOWED_BASE_URLS` is a JSON array of complete URLs. AI connections allow HTTP by default (`AI_REQUIRE_HTTPS=false`); set `AI_REQUIRE_HTTPS=true` to require HTTPS for central and session AI endpoints, including loopback. The configured scheme is preserved. `AI_PROVIDER=ollama` selects the native Ollama API for the explicitly configured local or remote endpoint; `openai-compatible` selects the legacy companion's OpenAI-style contract. Additional session AI bases still need central registration. `OSLC_PUBLIC_BASE_URL` may be left blank to derive it from the host and backend port. Remote Git/OSLC/CI connections retain their HTTPS rules; credentials belong in named secret variables or the session AI settings, never embedded in a URL.

Configure local Ollama with, for example, `AI_BASE_URL=http://127.0.0.1:1434` and the exact installed `AI_MODEL`. No model is downloaded automatically. Loopback hostname aliases retain the configured port and proxy path. The embedding-model default comes from `AI_EMBEDDING_MODEL`; the change workbench's request timeout follows `AI_AGENT_DEADLINE_SECONDS` plus `CONTROL_REQUEST_TIMEOUT_SECONDS`, rather than a fixed browser timeout. Restart services after changing root settings; existing session overrides remain separate.

| Setting | Default | Purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Backend and frontend bind address; keep loopback for local use |
| `BACKEND_PORT` / `FRONTEND_PORT` | `8009` / `3001` | Distinct service ports; no silent port fallback |
| `CORS_ORIGINS` | derived from frontend | Optional JSON list of allowed browser origins |
| `MAX_LOCAL_FILES` | `500` | Maximum submitted source files |
| `MAX_LOCAL_PAYLOAD_BYTES` | `10000000` | Maximum UTF-8 source content per request |
| `MAX_SOURCE_FILE_BYTES` | `2000000` | Per-file limit; oversized sources are rejected explicitly |
| `SOURCE_EXTENSIONS` / `SOURCE_EXCLUDES` | parser defaults | Optional JSON lists replacing extensions/directory exclusions |
| `GITLAB_ALLOWED_HOSTS` | `["gitlab.com"]` | Allowed GitLab hosts |
| `GITLAB_CLONE_TIMEOUT_SECONDS` | `60` | Git subprocess timeout |
| `SECURITY_MAX_FINDINGS` | `200` | Returned finding limit; totals/truncation remain visible |
| `GRAPH_PREVIEW_NODES` / `GRAPH_PREVIEW_EDGES` | `100` / `220` | Bounded browser graph preview |
| `MAX_TRACE_MANIFEST_BYTES` | `1000000` | Lifecycle manifest bound |
| `MAX_GRAPH_NODES` / `MAX_GRAPH_EDGES` | `50000` / `100000` | Extraction and trace graph growth limits |
| `CONTROL_REQUEST_TIMEOUT_SECONDS` | `15` | Browser configuration/session/decision request deadline |
| `REVIEW_PREVIEW_ITEMS` | `100` | History preview items per array; memoized and rendered on demand |
| `STARTUP_TIMEOUT_SECONDS` | `30` | Windows service readiness deadline |
| `REQUEST_TIMEOUT_SECONDS` | `120` | Browser analysis deadline and server result-acceptance deadline |
| `SESSION_IDLE_SECONDS` / `SESSION_MAX_SECONDS` | `1800` / `28800` | Idle timeout and absolute session lifetime |
| `MAX_SESSIONS` / `MAX_REVIEWS_PER_SESSION` | `32` / `10` | Review capacity |
| `MAX_REVIEW_STORAGE_BYTES` | `50000000` | Combined retained serialized review results |
| `MAX_CONCURRENT_ANALYSES` | `2` | Concurrent review analyses; excess requests return 429 |
| `UPLOAD_DIR` / `TEMP_DIR` / `LOG_DIR` | `data/uploads`, `temp`, `logs` | Paths relative to the checkout |

Use JSON arrays for list settings, not comma-separated strings. `PORT` remains a backend compatibility alias; use `BACKEND_PORT` for new configuration. Old `VITE_HOST`/`VITE_*_PORT` overrides are replaced by the shared settings above. The old database, Redis, Neo4j, JWT, and webhook keys were removed from the template because the active app does not use those services. API routes remain relative; production hosting must proxy `/api` to the backend. `npm run preview` uses the same configured proxy.

## Documentation

- [Functional requirements](docs/FRS.md)
- [Technical design](docs/TSD.md)
- [Graph and OSLC contracts](docs/trace-knowledge-graph.md)
- [Testing and live integration checklist](docs/testing.md)
- [Current audit status](docs/audit-status.md)
- [VS Code agent contract](docs/vscode-agent.md)
- [Contributing](CONTRIBUTING.md)

## Review and session workflow

Source overview, Quality assessment, Security patterns and lifecycle domains use
one workspace snapshot. Synchronize the configured source once to populate its
graph, source metrics and static security findings. Source and domain pages lead
with their own Overview, Assessment or Findings, with separate Graph and Data grid
sub-tabs using the same selection and companion. Search
and agent planning start in the selected domain and can follow cross-domain
evidence. A security finding selects its file for graph inspection and agent
explanation. Decisions made in review history also update the active snapshot.

Use **Analyze a different folder** in Source overview to replace the active
workspace with an uploaded-folder graph and its assessments. Synchronizing the
configured source restores its managed lifecycle connections. Uploaded folders
do not inherit lifecycle links from a different source. Graph layout, selection
and pins persist while navigating views of the same snapshot; a different
snapshot or ended session clears the associated evidence.

1. Select a folder and analyze it. Dependency/build folders and unsupported files are filtered before reading/uploading; the UI reports the skipped count.
2. Inspect the result and enter review notes. Every result begins **pending**.
3. Approve or reject that exact result. Decisions are final; rerun analysis for a new review.
4. Download an approved result with its audit history and digest. Server-side export refuses pending/rejected reviews.

The session bar displays remaining time, an explicit keepalive, review history, and an end-session action. Reading session status/history does not prolong idle time; analysis/review actions do. Absolute expiry cannot be extended. History lets you recover results after navigation or a timed-out response. Ending/expiring a session clears server-held reviews. A browser reload loses its in-memory session token; old server data expires automatically.

This is a local reviewer workflow, not authentication, independent sign-off, or certification that code is correct. Session tokens isolate browser sessions. `SESSION_STORE=memory` is the default and requires **one backend process/worker**. Set `SESSION_STORE=sqlite` and a shared `SESSION_DB_PATH` on private local disk for multiple workers on one host. SQLite reviews survive worker restarts until session end or expiry; ending a session deletes its reviews. Restrict file access and include the database/WAL in your storage protection and backup policy. SQLite is not a distributed multi-host session service. Export records before ending their session.

Git clones run with isolated user/system configuration, templates, hooks, credential helpers and environment. A private managed repository can name `token_env`; host credential helpers are deliberately unavailable. Local repository administration and the Git executable remain trusted.

Managed snapshots automatically inventory supported npm v2/v3 lockfiles (`sbom_lockfiles`, default root and frontend package-lock.json), without installing or executing packages. Set a managed repository's `sbom_path` to import CycloneDX JSON 1.4–1.6 or SPDX JSON 2.2–2.3 instead. Components and declared dependency edges appear in the SBOM graph domain. After approving the graph, `GET /api/v1/workspace/sbom/{review_id}` with the session header exports the inventory. This is supplier/lockfile evidence, not a built-artifact attestation, vulnerability scan, complete cross-ecosystem inventory or license compliance verdict.

Network TRS providers use a durable cache (`TRS_INCREMENTAL`, `TRS_CACHE_PATH`). Replay checks the exact saved event and base identity, dereferences changed resources, retains deletion tombstones, and replaces a complete checkpoint atomically. Missing continuity or a changed base triggers a full rebuild; bounded/incomplete rebuilds never replace the last complete checkpoint. CI follows same-endpoint Link pagination up to `CI_MAX_PAGES` / `CI_MAX_RUNS`; bounded windows are reported as partial.

The review center provides contextual link proposals for centrally configured network providers with `allow_writes=true`. Approve the managed snapshot, choose existing source/target resources and a supported predicate, prepare a strong ETag, approve/reject the proposal, then apply the approved link. A stale ETag becomes a conflict. Timeouts become unknown outcomes and require read-only reconciliation before preparing any further write. This workflow is session-bound and records an audit history; it does not provide independent reviewer authentication or vendor certification. Only test against disposable ALM resources until your provider profile is verified.

For existing PostgreSQL schemas, back up first, run `python backend/database/migrations.py` to list pending versions, then `python backend/database/migrations.py --apply` in your configured environment. The transactional migration widens resource IDs/predicates and adds graph-scoped hashed identity uniqueness and endpoint foreign keys. Existing duplicate/dangling graph data causes rollback and must be reconciled explicitly. Bootstrap creates missing tables; it does not migrate existing columns. No migration runs automatically during app startup.

Requests fail fast when capacity is full. A browser timeout cancels waiting, not Python execution. The backend discards results past the configured deadline; an individual parser operation cannot be interrupted mid-file. Git has its own subprocess timeout but no clone disk quota. These bounds are suitable for a local tool, not a hostile multi-tenant service.

## API and limitations

Live OpenAPI: `/docs`. Source endpoints remain available for programmatic analysis independently of the browser review workflow:

- `POST /api/v1/graph/local`, `/graph/local/analyze`, `/graph/gitlab`
- `GET /api/v1/graph/configuration` (public limits only)
- `POST /api/v1/quality/local`, `/security/local`, `/agent/context`
- `POST /api/v1/trace/materialize`, `/trace/query`, `/trace/jsonld`
- Session/review endpoints under `/api/v1/review` (see OpenAPI)

GitLab sources accept HTTPS project URLs; self-hosted instances require adding their hostname to `GITLAB_ALLOWED_HOSTS`. Private projects use your existing noninteractive Git credential helper. [Lifecycle manifests](docs/trace-knowledge-graph.md) add explicit requirement/test/product links. [Agent integration](docs/vscode-agent.md) describes the source-context contract.

Python uses AST-based extraction with limited intra-module call resolution. Non-Python symbols are heuristic and are included in agent context, but not in the typed Python architecture audit. Cross-module resolution and complete package-cycle detection remain incomplete. Security checks are limited static patterns, not a complete vulnerability/SBOM scanner. The legacy `cli/` repository-host commands are not compatible with the local-first API and are not installed by these scripts.

## Verification and cleanup

```powershell
.\install.ps1 -Dev
.\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend
npm test -- --run
npm run build
```

On macOS/Linux use `.venv/bin/python` and the same npm commands. CI runs the core/API and frontend checks on Windows and Linux. The obsolete MCP workflow is now a manual local-source audit, without calls to removed endpoints.

To uninstall development dependencies, stop the services and remove only this checkout's `.venv` and `frontend/node_modules` directories. Generated `frontend/dist`, `.runtime`, and log directories may also be removed. Keep `.env.local` if you want to preserve your settings; deleting these folders does not uninstall system Python or Node.js.

## Optional PostgreSQL schema bootstrap

The active local-first API uses configurable memory/SQLite reviews, SQLite OSLC publication and a durable TRS cache. PostgreSQL tools prepare the legacy ORM schema; they do not switch the active app to PostgreSQL.

Set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and optional `POSTGRES_CONNECT_TIMEOUT_SECONDS` in root `.env.local`. No password is supplied by default. The configured user must have permission to create the database, or an administrator must create it first.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-postgres.txt
.\.venv\Scripts\python.exe backend/setup_postgresql.py
.\.venv\Scripts\python.exe backend/database/migrate_enhanced.py
```

These scripts create missing tables/indexes without sample records. They do not upgrade existing columns. Use the explicit versioned runner in [Technical design](docs/TSD.md) to migrate existing columns; verify against a disposable PostgreSQL instance before deployment.

Graph controls support child collapse/expand, context expansion, background-click highlight clearing and reset. Companion similarity uses label and directed-neighbor feature overlap; it does not assert semantic equivalence. Recommendations identify missing supported links and incomplete providers. See [audit status](docs/audit-status.md) for validation boundaries.

Graph resources use classification colors and type glyphs with domain rings and an enlarged selection outline. Force network is the initial layout; hierarchical, circular, concentric and grid layouts remain available. Expand Traversal & layout controls to traverse upstream, downstream or both directions over 1–6 hops. Choose containment hierarchy or code/lifecycle evidence separately to avoid treating a shared container as impact evidence.

Current graph review results and known limits are consolidated in [audit status](docs/audit-status.md).

### Agent administration and graph tables

Open **Administration** to edit the system prompt and registered tool selection for each graph agent, tool descriptions, and legacy companion instructions. Save AI connection applies these changes to subsequent runs in your review session; restore agent and tool defaults preserves the connection and saved key. Configuration is session-owned and removed with the session. This local admin module does not add account-based administrator authorization. Runtime citation validation, registered tool implementations/parameter schemas, read-only restrictions and execution budgets remain enforced. Custom shell/HTTP tools cannot be registered from the form.

The Data grid sub-tab uses AG Grid Community, separate from the Graph and page assessments. Resources and Relationships switches provide sortable/filterable columns, resizable headers and pagination. Enable **IDs & properties** for resource identifiers and raw JSON. Relationship rows include links incident to the filtered resource set; selecting one opens the inspector for its source resource. Filtering uses the immutable review snapshot and does not change graph data. AG Grid loads on first opening Data grid and preserves its state when switching evidence tabs. The Agent & inspector button opens or hides the companion without replacing the active panel.
### Supply-chain lineage

Synchronize a managed source, then open **Supply-chain lineage**. npm lockfiles v2/v3 are inventoried automatically from the configured `sbom_lockfiles`; use `sbom_path` for CycloneDX JSON 1.4–1.6 or SPDX JSON 2.2–2.3. Folder uploads do not import SBOMs. Existing snapshots need synchronization to acquire the new application-root evidence.

Choose **Dependencies**, **Dependents**, **Shortest dependency path**, or **Full inventory**. Filter the root and target selectors by package name, version, purl or lockfile identity. Traversal uses every recorded dependency in the retained snapshot, independently of the graph explorer's hop limits, and terminates safely on cycles. Path mode shows one shortest directed path; an absent path means no path was recorded, not that a component is unused.

The **Lineage graph** provides hierarchical/force layouts, zoom, fit, pause and node inspection. **Data table · AG Grid** is separate and contains all matching resources and dependency relationships. The canvas and SVG diagram show at most 200 nodes and 500 edges; counts disclose any truncation. After approving the snapshot in **Review center**, export the diagram as SVG or the complete analysis as JSON. Exports recheck server approval and session ownership, then verify the returned snapshot digest.

Arrows mean **consumer → dependency**. Repository inventory membership never creates a dependency shortcut. Application roots come only from declared npm root dependencies (including development/optional dependencies), CycloneDX metadata-root dependency assertions, or SPDX document `DESCRIBES`/`DESCRIBED_BY` relationships. CycloneDX references back to a metadata-only application root retain their direction and cycles. Without explicit root evidence, select a component as the starting point. Unresolved npm declarations produce a visible incomplete-lineage warning, with required/development/optional evidence retained in the snapshot, generated SBOM and JSON analysis export. Optional dependencies may be absent for the current platform or installation scope. Peer/workspace resolution and runtime reachability remain incomplete; these views do not assert vulnerabilities or exploitability.
