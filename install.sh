#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python_bin="${PYTHON:-python3}"
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ required")'
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (!((major === 22 && minor >= 19) || major === 24 || major >= 26)) throw Error("Use Node.js 22.19+ (22.x), 24.x or 26+")'
if [[ ! -f .env.local ]]; then cp .env.local.example .env.local; fi
if [[ ! -x .venv/bin/python ]]; then "$python_bin" -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements-local.txt -e codegraph_core
if [[ "${1:-}" == "--dev" ]]; then .venv/bin/python -m pip install -r backend/requirements-dev.txt; fi
(cd frontend && npm ci)
printf 'Installation complete. Run bash start.sh\n'
