# CodeTrace AI

The application shell uses [Siemens Industrial Experience React](https://ix.siemens.io/docs/home/installation/react), with light/dark themes, managed-source selection, graph exploration and an evidence-grounded companion. Current audit results and open capability gaps are in [AUDIT_2026-10-15.md](AUDIT_2026-10-15.md).

Local-first source analysis, dependency graphs, quality checks, static security patterns, and explicit OSLC lifecycle links. The browser submits supported UTF-8 source files to a local FastAPI service. No database, cloud account, or access token is needed for local folders.

## Install on Windows

Prerequisites: Python 3.10+ and Node.js 22.12+ (22.x), 24.x or 26+ with npm on PATH. Node 24 is used in CI. Git is required only for GitLab ingestion. Use a real Python installation, not the Windows Store app-execution alias.

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

Install Python 3.10+, its venv support, Node.js 20+, npm, and optionally Git. From the checkout:

```bash
bash install.sh              # add --dev for Python test dependencies
bash start.sh                # Ctrl+C stops both services
```

Set `PYTHON=/path/to/python3` to select an interpreter. Scripts anchor paths to their own checkout. Docker is not a supported installation path; the legacy compose file is not a working deployment.

## Configuration

One root `.env.local` configures the backend, frontend dev/preview server, launch URLs, review sessions, and source limits. It is ignored by Git. `.env.local.example` documents supported keys; `config/defaults.json` centralizes shared defaults.

Precedence: process environment > root `.env.local` > root `.env` (legacy) > defaults. Restart both services after editing. Backend loading is independent of the current working directory. Vite also supports its standard mode-specific env files; avoid them when the backend must share the same settings.

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

## Review and session workflow

1. Select a folder and analyze it. Dependency/build folders and unsupported files are filtered before reading/uploading; the UI reports the skipped count.
2. Inspect the result and enter review notes. Every result begins **pending**.
3. Approve or reject that exact result. Decisions are final; rerun analysis for a new review.
4. Download an approved result with its audit history and digest. Server-side export refuses pending/rejected reviews.

The session bar displays remaining time, an explicit keepalive, review history, and an end-session action. Reading session status/history does not prolong idle time; analysis/review actions do. Absolute expiry cannot be extended. History lets you recover results after navigation or a timed-out response. Ending/expiring a session clears server-held reviews. A browser reload loses its in-memory session token; old server data expires automatically.

This is a local reviewer workflow, not authentication, independent sign-off, or certification that code is correct. Session tokens isolate browser sessions. Review records/audit events live only in memory and disappear on backend restart. Run **one backend process/worker**; multiple workers require a shared session store. Export any records you need to keep before ending a session.

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

The current local-first API uses in-memory review sessions and SQLite OSLC publication. PostgreSQL tools prepare the legacy ORM schema; they do not switch the active app to PostgreSQL.

Set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and optional `POSTGRES_CONNECT_TIMEOUT_SECONDS` in root `.env.local`. No password is supplied by default. The configured user must have permission to create the database, or an administrator must create it first.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-postgres.txt
.\.venv\Scripts\python.exe backend/setup_postgresql.py
.\.venv\Scripts\python.exe backend/database/migrate_enhanced.py
```

These scripts create missing tables/indexes without sample records. They do not upgrade existing columns. Review [GRAPH_POSTGRES_AUDIT.md](GRAPH_POSTGRES_AUDIT.md) before using legacy persistence in production.

Graph controls support child collapse/expand, context expansion, background-click highlight clearing and reset. Companion similarity uses label and directed-neighbor feature overlap; it does not assert semantic equivalence. Recommendations identify missing supported links and incomplete providers. See [SESSION_GRAPH_AI_AUDIT.md](SESSION_GRAPH_AI_AUDIT.md) for the final audit and validation boundaries.
