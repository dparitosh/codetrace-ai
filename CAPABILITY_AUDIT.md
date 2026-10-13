# Capability audit — 2026-10-13

Scope: active local-first API and managed workspace on `codex/local-first-spl-agent`, with inspection of legacy Git, SBOM and persistence code. Severity: P1 incorrect critical evidence or security exposure; P2 broken behavior/capability; P3 usability or operational limitation. This is a source and regression-test audit, not a guarantee that every bug has been found.

## Confirmed defects repaired

| Priority | Trigger and consequence | Repair / regression evidence |
| --- | --- | --- |
| P1 | Local Git files change after HEAD: CI SHA matches HEAD but not the analyzed bytes. | Dirty or unknown Git status no longer supplies a commit revision for build matching. Test: dirty checkout. |
| P1 | A TRS tombstone is approved and published: deleted resource becomes an active OSLC resource again. | Publication excludes tombstones; prior publications emit Deletion and return 410. Test: persistence, stable base and deletion. |
| P2 | A CI response contains a valid run followed by an invalid entry: partial evidence survives while the connector reports unavailable, or AttributeError escapes. | Validate into a temporary collection, publish atomically, catch malformed payloads; responses over 20 entries are partial. |
| P2 | A requirement has only schema/metadata, an unresolved target, or a deleted target: coverage claims it is traced. | Coverage requires a supported lifecycle-link predicate and two active resolved endpoints. This is link coverage, not proof of implementation or passing tests. |
| P2 | Administrator changes backend port: catalog/resource identities still point to 8009. | Public base derives from configured host/port unless explicitly overridden. |
| P2 | Managed manifest is absent or invalid: synchronization returns an unhandled 500. | Bounded manifest validation returns actionable 422, oversized files 413. |
| P2 | Remote PUT returns an arbitrarily large body. | Stream and bound the write response; error instructs reconciliation before retry because remote mutation may already have occurred. |
| P2 | TRS cutoff/change URIs cannot be dereferenced. | Authenticated event resource endpoint added. |

## Open findings and capability boundaries

| Priority | Finding | Impact / required next work |
| --- | --- | --- |
| P1 | Remote clone uses the host Git configuration and credential helpers; a configured checkout filter can execute during clone. | Restrict the service account's Git configuration/filters and isolate clone execution before accepting untrusted remote repository administration. URLs are centrally configured, redirects disabled, hooks disabled and prompts blocked; these do not sandbox Git filters. |
| P2 | SBOM is represented only by legacy SQLAlchemy models and sample migration records. No mounted SBOM importer/generator/exporter or frontend workflow exists. | Do not advertise SBOM compliance or infer a component inventory from code imports. Implement bounded CycloneDX/SPDX ingestion, document-scoped component identity, declared dependencies, provenance and schema validation. |
| P2 | CI reads one configured response, with a 20-run display cap; no complete historical pagination. | Connector reports partial for responses above the cap; a matching build outside the returned window is unavailable evidence, not a failed build. |
| P2 | TRS consumer rebuilds bounded snapshots; checkpoint metadata is not a durable incremental synchronization cursor. | Page/resource limits produce partial status. Add durable per-provider/configuration cursors and atomic base/log replay before claiming incremental indexing. |
| P2 | TRS bases retain the last 20 publication cutoffs rather than a time-based retention SLA. | Old bases return 410 requiring resynchronization. Document and implement retention windows for production providers. |
| P2 | Review sessions remain process-local memory. SQLite publications persist but sessions do not survive restart or support multiple workers. | Use one backend worker; introduce shared session/job storage before horizontal scaling. |
| P2 | Polarion/Codebeamer profiles have bounded RDF/auth/conditional-write primitives, but no complete in-app link-proposal approval/apply/reconcile flow yet. | Do not enable external writes for users expecting approval gates. Live vendor conformance and permissions need separate integration tests. |
| P2 | Legacy CLI references removed routes and legacy deployment/database setup is outside the supported installation. | Use documented local installation; repair or retire legacy interfaces before advertising them. |
| P3 | Graph overview can omit lifecycle links targeting hidden symbols, and domain-navigation search is substring-based. | Use symbol view/resource inspector for complete links pending projection and exact domain-filter fixes. |
| P3 | Sequential remote page requests have per-request deadlines but no shared synchronization deadline. | A large provider set can outlast the browser deadline; add cooperative aggregate deadlines and cancellable background jobs. |

## Verification and external limits

Regression coverage includes publication conflicts, stale resource ETags, capacity rollback, persistence, deletion, stable base membership, dirty Git provenance and malformed CI responses, in addition to existing session, parser, traceability and managed-provider tests. Provider HTTP behavior is tested with mocks; no live GitLab CI, Polarion, Codebeamer or Ollama model credentials/service were available for this audit. No external ALM data was changed.

Protocol references: [OASIS TRS specification](https://docs.oasis-open-projects.org/oslc-op/trs/v3.0/os/tracked-resource-set.html), [CycloneDX overview](https://cyclonedx.org/specification/overview/). TRS requires a base cutoff and retained change-log behavior; a source dependency graph alone is not a validated SBOM.
