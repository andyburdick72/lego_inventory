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
if ! ALLOW_SMOKE_TESTS=1 pytest -q tests/test_smoke_drawers_containers.py; then
  code=$?
  if [ "$code" -eq 5 ]; then
    echo "ℹ️ No smoke tests collected; continuing to start server..."
  else
    echo "❌ Smoke tests failed (exit $code)"
    exit "$code"
  fi
fi

if [ "${1:-}" = "cov" ]; then
  echo "🧪 Running tests with coverage..."
  ALLOW_SMOKE_TESTS=1 pytest --cov=src --cov-report=term-missing --cov-branch
fi

echo "🚀 Starting dev server on http://localhost:8000"
exec python -m app.server