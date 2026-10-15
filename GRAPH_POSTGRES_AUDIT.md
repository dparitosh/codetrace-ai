# Graph and PostgreSQL audit — 2026-10-13

Follow-up 2026-10-15: the persistence atomicity P1 below is now repaired and regression-tested; optional ORM/schema checks run against SQLite. Current validation and remaining gaps are in [AUDIT_2026-10-15.md](AUDIT_2026-10-15.md). The older validation limits below describe the October 13 run.

Scope: active graph projection/traversal plus legacy PostgreSQL scripts, configuration, ORM models and persistence. No live database was contacted or changed. Findings are prioritized by impact, not a claim of exhaustive bug discovery.

## Repaired findings

| Priority | Defect | Change |
| --- | --- | --- |
| P1 | Setup prints POSTGRES_PASSWORD on authentication failure; database status returns a credential-bearing URL. | Removed password-printing setup flow; status renders a redacted SQLAlchemy URL. |
| P1 | Enhanced migration writes fabricated CVSS/SBOM/SPDX evidence into repository ID 1. | Removed automatic sample insertion entirely. Bootstrap creates schema only. |
| P2 | Settings lacks POSTGRES fields/postgres_url, so database imports fail. | Added typed central configuration, identifier validation, escaped user/password URL construction, IPv6 handling and connection timeout. |
| P2 | setup_database.py hardcodes postgres/postgres, port 5433 and the old application name; duplicates schema definitions. | Both setup entry points delegate to one configured bootstrap. |
| P2 | create_tables uses a separate empty MetaData and init_db does not register model tables. | Uses Base.metadata and imports both model modules before creation. |
| P2 | Failed CREATE DATABASE leaks the connection; bootstrap failures still exit successfully. | Connection closes in finally, duplicate-create race handled, scripts exit 1 on failure with sanitized errors. |
| P2 | Enhanced schema creation and indexes commit separately. | Create missing tables and indexes in one engine transaction. Database creation itself remains outside a transaction. |
| P2 | Architecture overview hides code-symbol endpoints and consequently lifecycle links. | Keeps explicit lifecycle endpoints visible, preserving actual resource identity. |
| P3 | Edge cap silently drops relationships and can prefer containment over lifecycle evidence. | Prioritizes lifecycle links and reports omitted relationship count in the canvas. |

## Open findings

| Priority | Evidence | Consequence / next work |
| --- | --- | --- |
| P1 | RepositoryService.save_analysis_result commits a completed header before component persistence; _save_graph_analysis and other helpers commit independently. | Later failures can leave a completed analysis with missing graph/security components. Enclose full analysis persistence in one transaction and remove helper commits before enabling this legacy service in production. |
| P2 | PostgreSQL ORM is not wired to active review sessions or OSLC publication (which uses SQLite). | Running setup does not make current app sessions persistent or horizontally scalable. Do not claim otherwise. |
| P2 | create_all does not alter existing columns/constraints; no versioned migration chain accompanies these legacy scripts. | An existing schema can remain incompatible. Add reviewed Alembic migrations and upgrade/rollback tests against a database backup. |
| P2 | EnhancedGraphNode label/node_id and edge endpoints use VARCHAR(255), while imported labels can be 512 chars and resource URIs longer. | Legacy persistence can fail on valid active graph data. Use Text or validated compatible limits in a versioned migration. |
| P2 | Enhanced graph edge endpoints are strings without a graph-scoped foreign key to nodes, and node identity lacks a graph-scoped uniqueness constraint. | DB can accept dangling/duplicate graph identities. Add graph-scoped keys and constraints through migration. |
| P2 | EnhancedDatabase catches query failures and returns None/empty results, with process-memory fallback. | Callers can mistake database failures for successful writes or empty data. Require explicit unavailable states for persistent workflows. |
| P3 | Legacy graph analyzer accepts a languages list without applying it to scan and reports it as detected languages. | Results can misreport language detection. Core scans reset by default; derive detected languages from scanned files or implement the requested filter. |
| P3 | Resource-navigation domain shortcuts still use substring searches. | Canvas domain buttons filter exactly, but resource index shortcuts need an explicit domain filter. |

## Validation

Passed four dependency-free Python driver contract tests: keyword credentials, existing database idempotence, connection cleanup on failure, and missing-password failure before connecting. Passed three Node graph contract tests: overview lifecycle retention/edge prioritization, bounded valid endpoints/input immutability, and exact canvas domain filtering/local focus. Python syntax checks passed for six changed implementation files; git diff whitespace check passed.

Temporary dependency installation was declined. SQLAlchemy metadata execution, full backend suite, frontend production build, and live PostgreSQL DDL were **not rerun for these changes**. Earlier test/build results in CAPABILITY_AUDIT.md predate this audit. Run the optional dependency and PostgreSQL integration checks before approving these scripts for production.

References: [SQLAlchemy metadata](https://docs.sqlalchemy.org/en/20/core/metadata.html), [PostgreSQL CREATE DATABASE](https://www.postgresql.org/docs/current/sql-createdatabase.html).
