# Bug fixes and verification

The current patch fixes duplicate and nonportable source paths, inconsistent request limits, dangling graph edges, same-name audit node collisions, query-independent agent selection, dependency-folder ingestion, false-positive dependency coupling, misleading empty-input quality grades, and false online status in the dashboard.

GitLab URLs reject embedded credentials, query strings, fragments, unsupported ports, and tree/file URLs. Clones run outside the API event loop, disable HTTP redirects and interactive prompts, and scan bounded UTF-8 source files using stable relative paths. The clone transport is tested with a mock; a live private GitLab deployment has not been tested. Clone disk quotas and complete cross-module symbol resolution remain future work.

Installer failures now stop execution and allow an explicit Python executable. Starter processes run hidden, paths are quoted, and the frontend requires the selected port instead of silently switching.

Removed: obsolete backend analysis generators, hardcoded graph pages/data, generated mapping reports, and the unused mock analysis route. These tracked files are recoverable from Git history. Existing user changes under `.github` were not included; the package cache was retained.

Verification: run `.venv\Scripts\python.exe -m pytest -q` from the repository root and `npm run build` in `frontend`. Tests include source validation, graph endpoint integrity, audit identity preservation, query ranking, quality measurement, and GitLab ingestion/error handling.
