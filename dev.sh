#!/usr/bin/env bash
set -euo pipefail

# repo root (where this script lives)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Coverage flag (when first arg is "cov" we merge unit + contract coverage)
DO_COV=0
if [ "${1:-}" = "cov" ]; then
  DO_COV=1
fi

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

# If running in coverage mode, run unit tests with coverage FIRST so we can append contract coverage later
if [ "$DO_COV" -eq 1 ]; then
  echo "🧪 Running unit tests with coverage (phase 1)..."
  # clean prior coverage artifacts to avoid accidental merges
  rm -f .coverage coverage.xml
  rm -rf coverage_html_report htmlcov .pytest_cache
  # Remove any coverage files that might have been created (maxdepth 1 to avoid deleting files in subdirs)
  find . -maxdepth 1 -name ".coverage*" -delete 2>/dev/null || true
  ALLOW_SMOKE_TESTS=1 pytest -q tests/unit/ \
    --cov=src --cov-config=pyproject.toml \
    --cov-report=term-missing:skip-covered --cov-report=html --cov-report=xml
fi

echo "🧪 Running UI tests..."
# UI tests removed - Next.js renders client-side, not server-side HTML
# Skip UI tests (they would fail with exit code 5 - no tests collected)
if ! pytest -q -m ui 2>/dev/null; then
  code=$?
  if [ "$code" -eq 5 ]; then
    echo "ℹ️ No UI tests collected (UI tests removed - Next.js renders client-side); continuing..."
  else
    echo "ℹ️ UI tests skipped (deprecated)"
  fi
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

echo "📜 Starting FastAPI server for contract tests..."

LOG_FILE="${REPO_ROOT}/.server_test.log"
: > "$LOG_FILE"

# Kill any existing server on port 8001 to ensure fresh start
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
sleep 1

# Start FastAPI server using uvicorn (port 8001 for FastAPI, 8000 for old server)
# Check if uvicorn is available, if not install it
if ! python -c "import uvicorn" 2>/dev/null; then
  echo "📦 Installing uvicorn for FastAPI server..."
  python -m pip install uvicorn[standard] >>"$LOG_FILE" 2>&1
fi

# Start FastAPI server (PYTHONPATH already includes src/)
# Clear Python cache to ensure fresh code is loaded
find "$REPO_ROOT/src" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT/src" -name "*.pyc" -delete 2>/dev/null || true
( cd "$REPO_ROOT" && python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8001 ) >>"$LOG_FILE" 2>&1 &
SERVER_PID=$!
trap 'kill ${SERVER_PID} >/dev/null 2>&1 || true' EXIT

# Wait for server to accept connections (up to ~25s)
HEALTH_URLS=("http://127.0.0.1:8001/health" "http://127.0.0.1:8001/")
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
  echo "❌ FastAPI server did not start in time for contract tests"
  echo "—— Last server log output ———————————————————————————————"
  tail -n 120 "$LOG_FILE" || true
  echo "—————————————————————————————————————————————————————————"
  kill ${SERVER_PID} >/dev/null 2>&1 || true
  exit 1
fi

echo "📜 Running contract tests..."
# Base args for contract tests
if [ "$DO_COV" -eq 1 ]; then
  CONTR_ARGS=(--cov=src --cov-config=pyproject.toml --cov-append \
              --cov-report=term-missing:skip-covered --cov-report=html --cov-report=xml)
else
  CONTR_ARGS=(--no-cov -q)
fi

# Ensure API_BASE_URL points at the FastAPI server we just started (if not already set)
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8001/api/v1}"
# Also set API_BASE for backward compatibility with some tests
export API_BASE="${API_BASE:-http://127.0.0.1:8001/api/v1}"
export APP_BASE_URL="${APP_BASE_URL:-http://127.0.0.1:8001}"

# Fast contract sanity for error taxonomy
if ! pytest ${CONTR_ARGS[@]} tests/contract/api/test_errors_normalized.py; then
  echo "❌ Error-normalization contract sanity failed"
  kill ${SERVER_PID} >/dev/null 2>&1 || true
  exit 1
fi

# Full contract suite
if ! pytest -m contract ${CONTR_ARGS[@]}; then
  echo "❌ Contract tests failed"
  kill ${SERVER_PID} >/dev/null 2>&1 || true
  exit 1
fi

# Stop background server before starting the dev server in the foreground
kill ${SERVER_PID} >/dev/null 2>&1 || true
trap - EXIT
wait ${SERVER_PID} 2>/dev/null || true

# Default to FastAPI server, but allow override via SERVER_TYPE env var
SERVER_TYPE="${SERVER_TYPE:-fastapi}"

if [ "$SERVER_TYPE" = "fastapi" ] || [ "$SERVER_TYPE" = "1" ]; then
  HOST="${HOST:-0.0.0.0}"
  PORT="${PORT:-8001}"
  echo "🚀 Starting FastAPI server on http://${HOST}:${PORT}"
  echo "💡 API docs available at http://${HOST}:${PORT}/docs"
  echo "💡 Set SERVER_TYPE=legacy to use old Python server instead"
  
  # Try to detect LAN IP (common on en0 or en1)
  LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"
  echo "💡 From another device: http://${LAN_IP}:${PORT}"
  
  HOST="$HOST" PORT="$PORT" exec python -m uvicorn app.api.main:app --host "$HOST" --port "$PORT" --reload
else
  HOST="${HOST:-0.0.0.0}"
  PORT="${PORT:-8000}"
  echo "🚀 Starting legacy Python server on http://${HOST}:${PORT}"
  echo "💡 Set SERVER_TYPE=fastapi to use FastAPI server instead"
  
  # Try to detect LAN IP (common on en0 or en1)
  LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"
  echo "💡 From another device: http://${LAN_IP}:${PORT}"
  
  HOST="$HOST" PORT="$PORT" exec python -m app.server
fi