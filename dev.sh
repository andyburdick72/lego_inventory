#!/usr/bin/env bash
set -euo pipefail

# repo root (where this script lives)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
pip install -r "${REPO_ROOT}/requirements.txt"

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
python -m app.server &
SERVER_PID=$!
trap 'kill ${SERVER_PID} >/dev/null 2>&1 || true' EXIT

# Wait for server to accept connections (up to ~10s)
for i in {1..40}; do
  if curl -sS http://localhost:8000/ >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
  if [ "$i" -eq 40 ]; then
    echo "❌ Server did not start in time for contract tests"
    kill ${SERVER_PID} >/dev/null 2>&1 || true
    exit 1
  fi
done

echo "📜 Running contract tests..."
if ! pytest -m contract --no-cov -q; then
  echo "❌ Contract tests failed"
  kill ${SERVER_PID} >/dev/null 2>&1 || true
  exit 1
fi

# Stop background server before starting the dev server in the foreground
kill ${SERVER_PID} >/dev/null 2>&1 || true
trap - EXIT

if [ "${1:-}" = "cov" ]; then
  echo "🧪 Running tests with coverage..."
  ALLOW_SMOKE_TESTS=1 pytest --cov=src --cov-report=term-missing --cov-branch
fi

echo "🚀 Starting dev server on http://localhost:8000"
exec python -m app.server