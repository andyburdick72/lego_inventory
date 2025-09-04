#!/usr/bin/env bash
set -euo pipefail

# repo root (where this script lives)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Activate venv if not already active
if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ -d "${REPO_ROOT}/.venv" ]; then
    echo "🔗 Activating virtual environment..."
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/.venv/bin/activate"
  else
    echo "❌ No .venv found. Create one first: python3 -m venv .venv"
    exit 1
  fi
fi

# Ensure src/ is on PYTHONPATH for module imports (infra, app, scripts, etc.)
export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

echo "📦 Installing/updating dependencies..."
python -m pip install -r "${REPO_ROOT}/requirements.txt"
if [ -f "${REPO_ROOT}/requirements-dev.txt" ]; then
  echo "📦 Installing/updating dev dependencies..."
  python -m pip install -r "${REPO_ROOT}/requirements-dev.txt"
fi

echo "🛠️ Running smoke tests..."
if ! ALLOW_SMOKE_TESTS=1 pytest -q --no-cov tests/smoke/test_drawers_containers_smoke.py; then
  code=$?
  if [ "$code" -eq 5 ]; then
    echo "ℹ️ No smoke tests collected; continuing to start server..."
  else
    echo "❌ Smoke tests failed (exit $code)"
    exit "$code"
  fi
fi

echo "📜 Starting server for contract tests..."

LOG_FILE="${REPO_ROOT}/.server_test.log"
: > "$LOG_FILE"

# Start server (prefer module import; PYTHONPATH already includes src/)
( python -m app.server ) >>"$LOG_FILE" 2>&1 &
SERVER_PID=$!
trap 'kill ${SERVER_PID} >/dev/null 2>&1 || true' EXIT

# If process died immediately (e.g., import error), try script path fallback
sleep 0.5
if ! ps -p "$SERVER_PID" >/dev/null 2>&1; then
  ( python src/app/server.py ) >>"$LOG_FILE" 2>&1 &
  SERVER_PID=$!
fi

# Wait for server to accept connections (up to ~25s), accept any HTTP status
HEALTH_URLS=("http://127.0.0.1:8000/health" "http://127.0.0.1:8000/api/health" "http://127.0.0.1:8000/")
STARTED=0
for i in {1..50}; do
  for H in "${HEALTH_URLS[@]}"; do
    if curl -sS -o /dev/null "$H"; then
      STARTED=1
      break
    fi
  done
  if [ "$STARTED" -eq 1 ]; then
    break
  fi
  sleep 0.5
done

if [ "$STARTED" -ne 1 ]; then
  echo "❌ Server did not start in time for contract tests"
  echo "—— Last server log output ———————————————————————————————"
  tail -n 120 "$LOG_FILE" || true
  echo "—————————————————————————————————————————————————————————"
  kill ${SERVER_PID} >/dev/null 2>&1 || true
  exit 1
fi

echo "📜 Running contract tests..."
# Fast contract sanity for error taxonomy (run the file; it's small/quick)
if ! pytest --no-cov -q tests/contract/api/test_errors_normalized.py; then
  echo "❌ Error-normalization contract sanity failed"
  kill ${SERVER_PID} >/dev/null 2>&1 || true
  exit 1
fi

# Full contract suite
if ! pytest -m contract --no-cov -q; then
  echo "❌ Contract tests failed"
  kill ${SERVER_PID} >/dev/null 2>&1 || true
  exit 1
fi

# Stop background server before starting the dev server in the foreground
kill ${SERVER_PID} >/dev/null 2>&1 || true
trap - EXIT
wait ${SERVER_PID} 2>/dev/null || true

if [ "${1:-}" = "cov" ]; then
  echo "🧪 Running tests with coverage..."
  ALLOW_SMOKE_TESTS=1 pytest --cov=src --cov-report=term-missing --cov-branch
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
echo "🚀 Starting dev server on http://${HOST}:${PORT}"

# Try to detect LAN IP (common on en0 or en1)
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"
echo "💡 From another device: http://${LAN_IP}:${PORT}"

HOST="$HOST" PORT="$PORT" exec python -m app.server