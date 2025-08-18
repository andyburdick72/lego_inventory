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
python -m scripts.smoke_test_crud

echo "🚀 Starting dev server on http://localhost:8000"
exec python -m app.server