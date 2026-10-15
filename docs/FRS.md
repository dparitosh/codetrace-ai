# Functional requirements

## Scope

CodeTrace AI is a local-first code and lifecycle evidence workspace. The Siemens
iX React shell provides a contextual graph, resource index, property inspector,
evidence-grounded AI companion, review center and connection status. Administrator
configuration belongs in root `.env.local`; users select managed identities
rather than entering provider URLs or credentials.

## Implemented capabilities

- Analyze supported UTF-8 source uploads or centrally managed local/Git sources.
- Extract typed code facts and bounded architecture, quality and static security
  evidence. Coverage is structural/heuristic outside supported language parsers.
- Combine explicit AM, RM, CM, QM, configuration and ResourceShape assertions with
  stable repository-scoped code identities; preserve full predicate URIs.
- Consume bounded RDF exports/network providers and TRS changes. Incremental replay
  requires a matching base and exact event checkpoint; otherwise rebuild.
- Import CI results from configured GitHub/GitLab endpoints. Only matching revisions
  link builds to source; partial windows remain explicit.
- Import supported CycloneDX/SPDX JSON or generate an npm lockfile inventory.
  Display SBOM components/dependencies and export an approved inventory.
- Explore circular nodes with hierarchical, circular, organic and other layouts;
  choose traversal direction, relationship scope and depth; expand/collapse
  containment, highlight context, and inspect identity/provenance.
- Search labels, identifiers, URIs, domains and source paths. Additional results
  and inspector relationships remain reachable with visible counts.
- Ask centrally configured Ollama or compatible AI for cited answers. Retain a
  deterministic evidence summary when AI is disabled or unavailable/invalid.
- Bind decisions/exports to a result digest and session. Enforce idle, absolute,
  storage and concurrency limits. Support memory or shared SQLite sessions on one host.
- Publish approved managed snapshots through a bounded OSLC server profile.
  Prepare, approve/reject, conditionally apply and reconcile remote link proposals
  for centrally enabled writable provider profiles.

## Constraints and acceptance

Reachability and similarity scores are retrieval evidence, not proven causal
impact or semantic equivalence. Test links do not imply passing execution. SBOM
inventories do not establish complete artifact provenance or compliance. Session
tokens isolate browser sessions but do not authenticate independent users.
The app is not a distributed hostile multi-tenant service or a certified OSLC
implementation. Vendor-specific validation remains necessary.

Changes must pass applicable checks in [testing.md](testing.md). Current evidence
and deployment limitations are recorded in [audit-status.md](audit-status.md).
