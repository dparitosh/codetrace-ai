# Testing and verification

Run from the checkout root unless stated otherwise. Production ALM writes and
PostgreSQL migrations are not required for the normal regression suite.

## Automated checks

Install with `install.ps1 -Dev` or `bash install.sh --dev`. For optional ORM checks,
install `backend/requirements-postgres.txt` in the project virtual environment.
Those tests use SQLite and do not mutate PostgreSQL.

```powershell
.venv\Scripts\python.exe -m pytest -q
node --test frontend/graph-audit.test.mjs frontend/session-audit.test.mjs frontend/installation-audit.test.mjs
node frontend/graph-performance.mjs
Set-Location frontend
npm ci
npm run lint
npm test -- --run
npm run build
```

On macOS/Linux use `.venv/bin/python`. The frontend build includes TypeScript
checking. Node 24 is recommended. Dependency-free model/session contracts need a
supported recent Node runtime with `stripTypeScriptTypes`.

Coverage includes source validation, traversal/projection, URI identity, session
races, approval/export gates, shared storage/capacity, graph persistence, SBOM
bounds, TRS replay and mocked ALM writes. A green suite is not proof of no bugs
or live vendor conformance.

## Browser checks

Start `start.ps1 -NoBrowser` or `bash start.sh`, then open the printed frontend URL.
Use a disposable source/session.

1. Synchronize; check provider status and reported truncation.
2. Search a shared label, load more matches, select one and search its full ID.
3. Inspect properties and expand relationships beyond twelve edges.
4. Exercise hierarchy, direction, scope, depth, collapse/expand, fit and highlighting.
5. Switch force/hierarchy layouts; pause/resume/reheat, drag with and without pinning,
   release pins, and double-click or Shift+Enter to expand. Collapse then restore
   descendants and verify there are no stale-force crashes.
6. Filter domains and verify selected-filter feedback.
7. Check light/dark themes and graph/index/review/analysis navigation.
8. Verify pending exports are disabled. Approve a disposable result and inspect
   its exported result/SBOM. Confirm the review center shows link collaboration.
9. End the session; graph/inspector/review evidence and controls must clear/disable.

Stop services afterward. If cleanup is requested, remove only the dependency,
build and cache directories created for testing. Preserve `.env.local`, source,
lockfiles, user logs and existing runtime data.

## Live integration checks

- PostgreSQL: use a disposable database, bootstrap, inspect pending migrations,
  back up fixtures, apply twice, then verify long Unicode identities, scoped
  uniqueness, endpoint rejection and rollback on dirty legacy data.
- Polarion/Codebeamer: centrally configure a disposable provider and credentials.
  Verify discovery, configuration context, strong ETags and supported predicates.
  Prepare/reject one link; approve/apply a separate test link. Exercise stale ETags
  and uncertain responses, then reconcile before considering another write.
- TRS: verify provider base/cutoff semantics, changed representations, deletion,
  recreation, lost continuity and bounded/partial replay.
- Ollama: configure an already installed local model; verify real inference and
  valid citations, then stop the service to verify deterministic fallback.

Do not describe mock transports, SQLite checks or an unavailable model as a
successful live integration. Record actual environments and outcomes in the audit.
