# VS Code coding-agent integration

CodeTrace exposes a bounded, versioned REST contract for an editor extension:

`POST http://localhost:8009/api/v1/agent/context`

The extension must read only workspace files that the user has approved, then send relative paths and UTF-8 text. The API does not read arbitrary workstation paths. This makes the trust boundary explicit and lets the extension decide whether to exclude secrets, generated files, or unsaved buffers.

```ts
const response = await fetch('http://localhost:8009/api/v1/agent/context', {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    query: 'What is the smallest safe change for this task?',
    files: workspaceFiles,
    profile: 'strict',
    max_symbols: 40,
  }),
})
const context = await response.json()
```

Use `context.symbols`, `context.relations`, and `context.audit` as structured evidence for a language-model tool. Keep `agent_guidance` in the tool result. The response has `schema_version: "1.0"`; reject or deliberately migrate unknown major versions.

For VS Code, implement this as a Language Model Tool when the integration needs editor APIs (workspace trust, active editor, diagnostics, or code actions). Use an MCP tool only when the same capability must also be available outside VS Code. Keep request collection, prompt construction, and response rendering as separate deterministic modules so they can be unit tested without a model call.

Before publishing, add workspace-trust checks, a user confirmation for sending files, secret-file exclusions, cancellation handling, telemetry opt-in, and extension integration tests.
