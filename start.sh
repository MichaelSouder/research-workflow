#!/usr/bin/env bash
# Start backend + frontend at unique ports (backend 48721, frontend 48722).
# Override with BACKEND_PORT and FRONTEND_PORT. Run from project root:  ./start.sh

set -e
cd "$(dirname "$0")"

BACKEND_PORT=${BACKEND_PORT:-48721}
FRONTEND_PORT=${FRONTEND_PORT:-48722}
export BACKEND_PORT FRONTEND_PORT

echo "Starting backend (port $BACKEND_PORT)..."
BACKEND_LOG=$(mktemp)
python run_backend.py >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null; rm -f '$BACKEND_LOG'; exit" EXIT INT TERM

echo "Waiting for backend to be ready..."
for i in $(seq 1 15); do
  if curl -s -o /dev/null "http://127.0.0.1:$BACKEND_PORT/api/" 2>/dev/null; then
    echo "Backend is up."
    break
  fi
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "Backend exited. Last log lines:"
    tail -30 "$BACKEND_LOG"
    exit 1
  fi
  sleep 1
done
if ! curl -s -o /dev/null "http://127.0.0.1:$BACKEND_PORT/api/" 2>/dev/null; then
  echo "Backend did not become ready. Last log lines:"
  tail -30 "$BACKEND_LOG"
  exit 1
fi

echo "Starting frontend (port $FRONTEND_PORT)..."
echo ""
echo "  → Open http://localhost:$FRONTEND_PORT in your browser"
echo "  → Press Ctrl+C to stop both servers"
echo ""
cd frontend && npm run dev
