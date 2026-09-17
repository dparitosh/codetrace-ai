# Functional requirements — local-first product line

## Product scope

CodeTrace AI provides reusable software-analysis capabilities for local source folders and GitLab projects. It is designed as a product line: clients discover supported features through `GET /api/v1/capabilities` and select source and analysis options through versioned OpenAPI contracts.

## Mandatory capabilities

- Local folder graph construction from client-provided relative paths and UTF-8 contents.
- GitLab project graph construction for approved GitLab hosts.
- Typed code semantics for modules, classes, functions, and variables.
- NetworkX-based architecture audit: dependency cycles, high-complexity classes, potentially uncalled functions, and orphaned nodes.
- Local structural quality and static security checks.
- Bounded coding-agent context at `POST /api/v1/agent/context`.

## Quality constraints

- Local browser and editor clients keep authority over which files are sent.
- The service rejects traversal and absolute paths, limits a request to 500 files and 10 MB, and retains no selected source after the request completes.
- Agent context is versioned and includes provenance, symbols, relations, audit evidence, and safety guidance.
- Unsupported source extensions are rejected by the `strict` analysis profile.
- Changes must pass scanner regression tests, API contract tests, frontend type checking, and a production frontend build before release.

## Extension integration

A VS Code extension should use workspace trust, explicit user approval, secret-file exclusions, cancellation, and deterministic unit tests. See [VS Code agent integration](vscode-agent.md).
