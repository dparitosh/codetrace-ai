# Session, graph interaction and AI audit — 2026-10-13

This branch includes the local-first refactor and preceding capability/PostgreSQL audit fixes, plus the following review.

## Fixed

- P1: Ending a session during creation could resurrect it when the response arrived. Creation now checks a cancellation generation.
- P2: Late review approval, export and history responses could escape into a changed session. They now validate the original session token before returning or downloading. OSLC session 401 responses invalidate the client session too.
- P2: Workspace retained graph evidence after session end/expiry. The workspace now clears it when its owning session changes or expires.
- P2: Late companion answers could overwrite newer snapshot context. Request generations discard outdated answers and reset busy state on graph changes.
- P2: Graph had no explicit collapse/expand controls. Directed containment traversal now supports child collapse/expand, iterative context expansion and reset, with cycle handling and capped previews. Selected resources are prioritized under caps; background clicks clear highlights. Pan/zoom and existing positions survive projection changes.
- P2: Domain sidebar used substring search, causing false matches. It now applies exact domain filters; QM navigation and supplied test outcomes are displayed.
- P2: Similarity treated shared container neighbors as semantic overlap and mixed feature tags with resource IDs. Core similarity excludes containment and namespaces direction, predicate, neighbor identity and feature tags.
- P2: Similarity and recommendations lacked an accessible active-workspace path. Companion responses now include bounded, explainable label/directed-neighbor Jaccard ranking and recommendations based on unlinked active requirements or incomplete providers. Scores are retrieval features, not semantic equivalence, confidence or proof of correctness.
- P2: AI evidence could include dangling edge endpoints and malformed citation collections. Retrieval now filters invalid edges and validates citation arrays; empty evidence skips model inference.
- P3: AI relation/output/response limits shared unrelated constants. They now have central AI_CONTEXT_RELATIONS, AI_MAX_OUTPUT_TOKENS, AI_MAX_RESPONSE_BYTES and AI_MAX_ANSWER_CHARACTERS settings.
- P3: Companion footer claimed local Ollama even for disabled/remote providers. It now reflects the configured provider.

## Validation and open limits

Dependency-free graph/session tests cover lifecycle retention, truncation, collapse/expand, cycles, selected-resource limits, creation cancellation, late approval responses and session coalescing. Algorithm contract tests cover shared-folder exclusion, predicate direction, deleted-resource filtering and recommendation evidence. PostgreSQL driver contracts remain passing.

Dependency installation was declined in the preceding audit and remains declined. Full backend tests, React/browser interaction checks, TypeScript production build and real Ollama/vendor integration tests were not rerun for the final changes. CI is configured to run tests/builds on this new codex branch. Do not treat earlier full-suite results as verification of the final diff.

Open: no embedding-based semantic similarity, trained recommendation ranking, causal impact guarantees, durable multi-worker sessions or complete link-proposal workflow. Prior P1 legacy persistence atomicity and Git checkout isolation findings remain open. See CAPABILITY_AUDIT.md and GRAPH_POSTGRES_AUDIT.md. Appearance/default model names remain configurable examples; presentation colors and fixed protocol terms are intentional code constants.
