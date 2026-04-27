#!/usr/bin/env bash
# Start backend, then Vite (foreground). Ctrl+C stops the backend we started.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-48721}"
if lsof -i ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "Backend already listening on :$BACKEND_PORT — only starting Vite."
else
  echo "Starting backend on :$BACKEND_PORT..."
  NO_RELOAD=1 python run_backend.py &
  BPID=$!
  trap "kill $BPID 2>/dev/null; exit" INT TERM EXIT
  sleep 1
fi

cd "$ROOT/frontend"
exec npm run dev
