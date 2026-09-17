# Technical design — local-first CodeTrace AI

## Components

| Component | Responsibility |
| --- | --- |
| React frontend | Lets a user select a source folder and renders analysis results. |
| FastAPI service | Validates bounded requests and exposes OpenAPI endpoints. |
| `codegraph_core` | Extracts typed semantic facts using Python AST and configurable generic scanners. |
| NetworkX audit | Evaluates architecture cycles, complex classes, potentially uncalled functions, and orphaned nodes. |
| GitLab adapter | Clones an allowlisted project into a temporary folder and discards it after analysis. |

## Data flow

1. The browser or editor extension selects files under its own trust boundary.
2. It sends relative paths and UTF-8 content to the local API.
3. The API enforces path, size, file-count, and source-extension constraints.
4. `codegraph_core` returns typed file/module/class/function/variable semantics.
5. The service serializes a graph, quality/security results, or bounded agent context.

## Public contracts

- `/api/v1/capabilities` is the feature-discovery manifest.
- `/api/v1/graph/local` and `/api/v1/graph/gitlab` return graph data.
- `/api/v1/agent/context` returns a `schema_version` and structured evidence suitable for an editor tool.

## Security boundaries

- The API never accepts absolute or traversal source paths.
- Browser/editor clients decide which files leave the workspace.
- Local source payloads are limited to 500 files and 10 MB.
- GitLab clone URLs use HTTPS and must match `GITLAB_ALLOWED_HOSTS`.
- Source data is request-only; no selected source is persisted by these routes.

## Extensibility

New product-line features should be independently discoverable in the capability manifest, version their response contracts, and include deterministic tests. Register language-specific scanners through `CodeGraph.register_scanner` rather than coupling provider or UI code to parser internals.
