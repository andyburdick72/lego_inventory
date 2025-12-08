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

# Run unit tests (with or without coverage depending on DO_COV flag)
if [ "$DO_COV" -eq 1 ]; then
  echo "🧪 Running unit tests with coverage (phase 1)..."
  # clean prior coverage artifacts to avoid accidental merges
  rm -f .coverage coverage.xml
  rm -rf coverage_html_report htmlcov .pytest_cache
  # Remove any coverage files that might have been created (maxdepth 1 to avoid deleting files in subdirs)
  find . -maxdepth 1 -name ".coverage*" -delete 2>/dev/null || true
  ALLOW_SMOKE_TESTS=1 pytest -q tests/unit/ tests/infra/ \
    --cov=src --cov-config=pyproject.toml \
    --cov-report=term-missing --cov-report=html --cov-report=xml
else
  echo "🧪 Running unit tests..."
  ALLOW_SMOKE_TESTS=1 pytest -q --no-cov tests/unit/ tests/infra/
fi

# UI tests skipped - Next.js renders client-side, not server-side HTML
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

# Cleanup function to kill test server and any processes on port 8001
cleanup_test_server() {
  if [ -n "${SERVER_PID:-}" ]; then
    kill ${SERVER_PID} >/dev/null 2>&1 || true
    wait ${SERVER_PID} 2>/dev/null || true
  fi
  # Also kill any processes on port 8001 (in case PID tracking fails)
  lsof -ti:8001 | xargs kill -9 2>/dev/null || true
}

# Kill any existing server on port 8001 to ensure fresh start
cleanup_test_server
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
trap cleanup_test_server EXIT

# Wait for server to accept connections (up to ~25s)
HEALTH_URLS=("http://127.0.0.1:8001/health" "http://127.0.0.1:8001/")
STARTED=0
for i in {1..50}; do
  for H in "${HEALTH_URLS[@]}"; do
    if curl -sSf -o /dev/null "$H" 2>/dev/null; then
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
  cleanup_test_server
  exit 1
fi

echo "📜 Running contract tests..."
# Base args for contract tests
if [ "$DO_COV" -eq 1 ]; then
  CONTR_ARGS=(--cov=src --cov-config=pyproject.toml --cov-append \
              --cov-report=term-missing --cov-report=html --cov-report=xml)
else
  CONTR_ARGS=(--no-cov -q)
fi

# Ensure API_BASE_URL points at the FastAPI server we just started (if not already set)
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8001/api/v1}"
export APP_BASE_URL="${APP_BASE_URL:-http://127.0.0.1:8001}"

# Fast contract sanity for error taxonomy
if ! pytest ${CONTR_ARGS[@]} tests/contract/api/test_errors_normalized.py; then
  echo "❌ Error-normalization contract sanity failed"
  cleanup_test_server
  exit 1
fi

# Full contract suite
if ! pytest -m contract ${CONTR_ARGS[@]}; then
  echo "❌ Contract tests failed"
  cleanup_test_server
  exit 1
fi

# Stop background server before starting the dev server in the foreground
cleanup_test_server
trap - EXIT

# Cleanup function for frontend server
cleanup_frontend() {
  if [ -n "${FRONTEND_PID:-}" ]; then
    kill ${FRONTEND_PID} >/dev/null 2>&1 || true
    wait ${FRONTEND_PID} 2>/dev/null || true
  fi
  # Also kill any processes on port 3001
  lsof -ti:3001 | xargs kill -9 2>/dev/null || true
}

# Kill any existing frontend server on port 3001
cleanup_frontend
sleep 1

# Start Next.js frontend in the background
echo "🚀 Starting Next.js frontend on http://localhost:3001..."
cd "$REPO_ROOT/frontend"
# Source NVM if available, then start Next.js
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" 2>/dev/null || true
if [ -f package.json ]; then
  npm run dev >/dev/null 2>&1 &
  FRONTEND_PID=$!
  # Wait a moment for frontend to start
  sleep 2
  if kill -0 ${FRONTEND_PID} 2>/dev/null; then
    echo "✅ Next.js frontend started (PID: ${FRONTEND_PID})"
  else
    echo "⚠️  Frontend may have failed to start. Check manually: cd frontend && npm run dev"
    FRONTEND_PID=""
  fi
else
  echo "⚠️  Frontend package.json not found. Start manually: cd frontend && npm run dev"
  FRONTEND_PID=""
fi
cd "$REPO_ROOT"

# Set up trap to cleanup frontend on exit (always set, even if frontend didn't start)
trap cleanup_frontend EXIT

# Start FastAPI backend server
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"

# Try to detect LAN IP (common on en0 or en1)
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"

echo "🚀 Starting FastAPI backend on http://${HOST}:${PORT}"
echo "💡 API docs available at http://${HOST}:${PORT}/docs"
echo "💡 From another device: http://${LAN_IP}:${PORT}"
echo ""
echo "✅ Both servers running:"
echo "   - Frontend: http://localhost:3001"
echo "   - Backend:  http://${HOST}:${PORT}"
echo "   - API Docs: http://${HOST}:${PORT}/docs"
echo ""
echo "🌐 Access from other devices on your network:"
echo "   - Frontend: http://${LAN_IP}:3001"
echo "   - Backend:  http://${LAN_IP}:${PORT}"
echo "   - API Docs: http://${LAN_IP}:${PORT}/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

HOST="$HOST" PORT="$PORT" exec python -m uvicorn app.api.main:app --host "$HOST" --port "$PORT" --reload