# Hierarchy and contextual traversal audit — 2026-10-15

Scope: the circular-node hierarchy, directional traversal, graph projection, collapse state, selection styling and layout cache added after the broader application audit. This is a targeted audit, not a guarantee that all application bugs have been discovered.

## Findings repaired

| Priority | Trigger / consequence | Fix |
| --- | --- | --- |
| P2 | A focused context replaces the domain-filtered candidate list, exposing other domains while a domain button remains active. | The projection now enforces explicit domain filters. Search and context actions deliberately switch the UI to All domains when revealing cross-domain context. |
| P2 | Changing relationship scope before selecting a focus node leaves all edge types visible. | Relationship scope applies to displayed edges in overview as well as focused context. |
| P2 | Selecting a hidden child in the inspector and focusing it leaves a collapsed ancestor hiding the root; context expansion can leave the selected container collapsed. | Focusing removes only collapsed ancestors hiding the root. Expand context additionally unfolds the selected container while preserving unrelated collapse choices. |
| P2 | Global degree ranking under a render cap can favor distant hubs over the traversal frontier, losing nearby path context. | Focused candidates preserve breadth-first discovery order, with the explicitly selected resource still prioritized. Caps remain visible. |
| P2 | Predicate matching by local name treats an unrelated URI ending in contains/defines as code containment. | Containment accepts bare core relations and explicit CodeTrace vocabulary URIs only. Metadata exclusion likewise uses explicit supported identities. Dangling endpoints do not participate in containment traversal. |
| P2 | Clicking an already selected node can change Cytoscape's native selection without changing React state, removing the expected outline. | The outline uses a controlled focused-resource class independent of native selection state. |
| P2 | A selected symbol can disappear in architecture overview, leaving inspector selection without a visible anchor. | Explicitly selected resources are eligible in overview, subject to domain, focus and collapse constraints. Focus controls reveal their context when needed. |
| P3 | Building containment lists copies the full child array for every added edge, becoming quadratic for high fan-out. | Child lists append in place during index construction. Source graph data is not modified. |

## Verification

- 19 Node contract checks pass, including regression cases for domain enforcement, scope filtering, bounded frontier order, revealing hidden roots and foreign predicate identities.
- 15 frontend Vitest tests pass.
- TypeScript checking, ESLint and the production build pass after a clean npm ci.
- Backend and dependency files were unchanged in this audit; their previous results were not presented as a new run.
- No new browser smoke test was run for this specific follow-up. The broader Siemens UI browser verification is recorded in AUDIT_2026-10-15.md.
- The production app chunk remains about 674 kB before gzip and produces Vite's size advisory. Further code splitting is an open performance task.

Remaining system gaps (Git clone isolation, SBOM functionality, durable incremental TRS, shared sessions, complete ALM proposal workflow and PostgreSQL migrations) remain as documented in AUDIT_2026-10-15.md. Temporary dependencies/build output are removed after testing per the user's earlier instruction.
