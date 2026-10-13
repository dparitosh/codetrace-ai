#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python_bin="${PYTHON:-python3}"
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ required")'
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) { throw Error("Node.js 20+ required") }'
if [[ ! -f .env.local ]]; then cp .env.local.example .env.local; fi
if [[ ! -x .venv/bin/python ]]; then "$python_bin" -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements-local.txt -e codegraph_core
if [[ "${1:-}" == "--dev" ]]; then .venv/bin/python -m pip install -r backend/requirements-dev.txt; fi
(cd frontend && npm ci)
printf 'Installation complete. Run bash start.sh\n'
