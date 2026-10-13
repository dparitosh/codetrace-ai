#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python || ! -f frontend/node_modules/vite/bin/vite.js ]]; then
  echo 'Run bash install.sh first.' >&2
  exit 1
fi
.venv/bin/python -c 'import sys; sys.path.insert(0,"backend"); from core.config import settings; print("Frontend: " + settings.frontend_url)'
.venv/bin/python backend/main.py &
backend_pid=$!
(cd frontend && exec node node_modules/vite/bin/vite.js) &
frontend_pid=$!
cleanup() { kill "$backend_pid" "$frontend_pid" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT TERM
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do sleep 1; done
echo 'A service exited; stopping the other service.' >&2
exit 1
