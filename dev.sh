#!/usr/bin/env bash
set -euo pipefail

# repo root (where this script lives)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Load APP_SAFE_MODE from data/.env (backend convention) without `source` to avoid
# shell-expanding dotenv values (e.g. values containing `$...`).
if [ -z "${APP_SAFE_MODE:-}" ] && [ -f "${REPO_ROOT}/data/.env" ]; then
  app_safe_mode_line="$(grep -E '^APP_SAFE_MODE=' "${REPO_ROOT}/data/.env" | tail -n 1 || true)"
  if [ -n "${app_safe_mode_line}" ]; then
    app_safe_mode_val="${app_safe_mode_line#APP_SAFE_MODE=}"
    # Strip surrounding quotes
    app_safe_mode_val="${app_safe_mode_val%\"}"
    app_safe_mode_val="${app_safe_mode_val#\"}"
    app_safe_mode_val="${app_safe_mode_val%\'}"
    app_safe_mode_val="${app_safe_mode_val#\'}"
    export APP_SAFE_MODE="${app_safe_mode_val}"
  fi
fi

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

# Create temporary test database for contract tests
# Use mktemp with proper template (XXXXXX must be at the end for mktemp)
# Clean up any leftover test databases first
rm -f "${TMPDIR:-/tmp}"/test_contract_*.db 2>/dev/null || true
TEST_DB_PATH=$(mktemp "${TMPDIR:-/tmp}/test_contract_XXXXXX.db")
if [ ! -f "${TEST_DB_PATH}" ]; then
  echo "❌ Failed to create test database file"
  exit 1
fi
echo "📦 Creating temporary test database: ${TEST_DB_PATH}"

# Initialize test database with schema
# Set APP_DB_PATH before importing so settings picks it up
export APP_DB_PATH="${TEST_DB_PATH}"
python3 << PYTHON_SCRIPT
import sys
import os

# Add src to path for imports
repo_root = "${REPO_ROOT}"
sys.path.insert(0, os.path.join(repo_root, 'src'))

# Clear settings cache to ensure fresh read of APP_DB_PATH
from app.settings import get_settings
get_settings.cache_clear()

# Import the init_db function (DB_PATH will be set from APP_DB_PATH env var)
from infra.db.inventory_db import init_db

try:
    # Initialize the database schema
    init_db()
    test_db_path = os.environ.get('APP_DB_PATH', 'unknown')
    
    # Verify tables were created and enable WAL mode for concurrent access
    import sqlite3
    conn = sqlite3.connect(test_db_path, timeout=10.0)
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")  # 10 second timeout
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    required_tables = ['drawers', 'containers', 'inventory', 'parts', 'sets', 'set_parts']
    missing = [t for t in required_tables if t not in tables]
    if missing:
        print(f"❌ Missing tables: {missing}", file=sys.stderr)
        print(f"   Found: {tables}", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Test database initialized: {test_db_path} ({len(tables)} tables, WAL mode enabled)")
except Exception as e:
    print(f"❌ Failed to initialize test database: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo "❌ Failed to create test database"
    rm -f "${TEST_DB_PATH}"
    unset APP_DB_PATH
    exit 1
fi

# Populate test database with minimal test data
echo "🌱 Seeding test database with sample data..."
python3 << PYTHON_SCRIPT
import sys
import os
import sqlite3

repo_root = "${REPO_ROOT}"
test_db_path = "${TEST_DB_PATH}"
sys.path.insert(0, os.path.join(repo_root, 'src'))

try:
    conn = sqlite3.connect(test_db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    
    # Insert colors
    colors = [
        (1, "Black", "#000000"),
        (5, "Red", "#FF0000"),
        (15, "Trans-Clear", "#FFFFFF"),
    ]
    for color_id, name, hex_code in colors:
        conn.execute(
            "INSERT OR IGNORE INTO colors(id, name, hex) VALUES (?, ?, ?)",
            (color_id, name, hex_code)
        )
    
    # Insert parts (design IDs that tests expect)
    parts = [
        ("3001", "Brick 2 x 4"),
        ("3002", "Brick 2 x 3"),
        ("3003", "Brick 2 x 2"),
        ("3023", "Plate 1 x 2"),
        ("3062", "Round Brick 1 x 1"),
        ("6223", "Plate 1 x 1"),
    ]
    for design_id, name in parts:
        conn.execute(
            "INSERT OR IGNORE INTO parts(design_id, name, ignore_in_inventory) VALUES (?, ?, 0)",
            (design_id, name)
        )
    
    # Insert part aliases (for alias tests)
    aliases = [
        ("BL-3001", "3001"),  # BrickLink alias for 3001
        ("BL-6223", "6223"),  # BrickLink alias for 6223
        ("3001-alt", "3001"),  # Alternative alias
        ("6223-alt", "6223"),  # Alternative alias
    ]
    for alias, design_id in aliases:
        conn.execute(
            "INSERT OR IGNORE INTO part_aliases(alias, design_id) VALUES (?, ?)",
            (alias, design_id)
        )
    
    # Insert drawers
    drawers = [
        (1, "Drawer A", None),
        (2, "Drawer B", None),
        (3, "General", None),
    ]
    for drawer_id, name, deleted_at in drawers:
        conn.execute(
            "INSERT OR IGNORE INTO drawers(id, name, deleted_at) VALUES (?, ?, ?)",
            (drawer_id, name, deleted_at)
        )
    
    # Insert containers
    containers = [
        (1, 1, "Container 1", 0, None),  # Regular container
        (2, 2, "Putaway Bin", 1, None),  # Putaway bin
        (3, 1, "Container 2", 0, None),
    ]
    for container_id, drawer_id, name, is_put_away_bin, deleted_at in containers:
        conn.execute(
            "INSERT OR IGNORE INTO containers(id, drawer_id, name, is_put_away_bin, deleted_at) VALUES (?, ?, ?, ?, ?)",
            (container_id, drawer_id, name, is_put_away_bin, deleted_at)
        )
    
    # Insert a theme (sets table requires theme_id, even if NULL)
    conn.execute(
        "INSERT OR IGNORE INTO themes(id, name) VALUES (?, ?)",
        (1, "Test Theme")
    )
    
    # Insert sets with different statuses
    sets_data = [
        ("TEST-1", "Test Set 1", 2024, 1, "loose"),
        ("TEST-2", "Test Set 2", 2024, 1, "teardown"),
        ("TEST-3", "Test Set 3", 2024, 1, "built"),
        ("TEST-4", "Test Set 4", 2024, 1, "in_box"),
        ("TEST-5", "Test Set 5", 2024, 1, "wip"),
    ]
    for set_num, name, year, theme_id, status in sets_data:
        conn.execute(
            "INSERT OR IGNORE INTO sets(set_num, name, year, theme_id, status) VALUES (?, ?, ?, ?, ?)",
            (set_num, name, year, theme_id, status)
        )
    
    # Insert set_parts (schema: set_num, design_id, color_id, quantity)
    set_parts_data = [
        ("TEST-1", "3001", 1, 10),  # loose set
        ("TEST-1", "3023", 5, 5),
        ("TEST-2", "3001", 1, 20),  # teardown set
        ("TEST-2", "3002", 1, 15),
        ("TEST-3", "3003", 1, 30),  # built set
        ("TEST-4", "3062", 15, 10),  # in_box set
        ("TEST-5", "6223", 1, 25),  # wip set
    ]
    for set_num, design_id, color_id, quantity in set_parts_data:
        conn.execute(
            "INSERT OR IGNORE INTO set_parts(set_num, design_id, color_id, quantity) VALUES (?, ?, ?, ?)",
            (set_num, design_id, color_id, quantity)
        )
    
    # Insert inventory items (loose inventory)
    inventory_data = [
        ("3001", 1, 10, "loose", 1, None, None),  # In container 1
        ("3023", 5, 5, "loose", 1, None, None),
        ("3002", 1, 15, "loose", 3, None, None),  # In container 3
        ("3062", 15, 10, "loose", None, "General", "All"),  # Old-style location
    ]
    for design_id, color_id, quantity, status, container_id, drawer, container in inventory_data:
        conn.execute(
            "INSERT OR IGNORE INTO inventory(design_id, color_id, quantity, status, container_id, drawer, container) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (design_id, color_id, quantity, status, container_id, drawer, container)
        )
    
    conn.commit()
    conn.close()
    
    print(f"✅ Test data seeded successfully")
except Exception as e:
    print(f"❌ Failed to seed test data: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo "❌ Failed to seed test data"
    cleanup_test_server true
    exit 1
fi

# Cleanup function to kill test server, remove test DB, and any processes on port 8001
# If delete_db is true, also deletes the test database file
cleanup_test_server() {
  local delete_db="${1:-false}"
  if [ -n "${SERVER_PID:-}" ]; then
    kill ${SERVER_PID} >/dev/null 2>&1 || true
    wait ${SERVER_PID} 2>/dev/null || true
  fi
  # Remove temporary test database only if explicitly requested
  if [ "$delete_db" = "true" ] && [ -n "${TEST_DB_PATH:-}" ] && [ -f "${TEST_DB_PATH}" ]; then
    rm -f "${TEST_DB_PATH}"
    echo "🧹 Cleaned up test database: ${TEST_DB_PATH}"
  fi
  # Also kill any processes on port 8001 (in case PID tracking fails)
  lsof -ti:8001 | xargs kill -9 2>/dev/null || true
}

# Kill any existing server on port 8001 to ensure fresh start (but don't delete test DB yet)
cleanup_test_server false
sleep 1

# APP_DB_PATH is already set from the initialization step above
echo "🔧 Using test database: ${APP_DB_PATH}"

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

# Verify test database exists and has tables before starting server
python3 << PYTHON_SCRIPT
import sys
import os
import sqlite3

repo_root = "${REPO_ROOT}"
test_db_path = "${TEST_DB_PATH}"
sys.path.insert(0, os.path.join(repo_root, 'src'))

# Verify database exists
if not os.path.exists(test_db_path):
    print(f"❌ Test database file does not exist: {test_db_path}", file=sys.stderr)
    sys.exit(1)

# Verify database has tables and WAL mode
try:
    conn = sqlite3.connect(test_db_path, timeout=10.0)
    # Ensure WAL mode is enabled
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    required_tables = ['drawers', 'containers', 'inventory', 'parts', 'sets', 'set_parts']
    missing = [t for t in required_tables if t not in tables]
    if missing:
        print(f"❌ Test database missing tables: {missing}", file=sys.stderr)
        print(f"   Found tables: {tables}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ Test database verified: {len(tables)} tables found")
except Exception as e:
    print(f"❌ Failed to verify test database: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo "❌ Test database verification failed"
    cleanup_test_server true
    exit 1
fi

# Start server with APP_DB_PATH explicitly set in the environment
# Use env to ensure the variable is passed to the subprocess
# The server process will import modules fresh, so DB_PATH will be set correctly from APP_DB_PATH
echo "🚀 Starting test server with APP_DB_PATH=${TEST_DB_PATH}"
# Verify the database file still exists before starting server
if [ ! -f "${TEST_DB_PATH}" ]; then
  echo "❌ Test database file disappeared: ${TEST_DB_PATH}"
  cleanup_test_server true
  exit 1
fi
( cd "$REPO_ROOT" && env APP_DB_PATH="${TEST_DB_PATH}" PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8001 ) >>"$LOG_FILE" 2>&1 &
SERVER_PID=$!
trap 'cleanup_test_server true' EXIT

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

# Verify server is using the test database by checking if it can access tables
if [ "$STARTED" -eq 1 ]; then
  # Give server a moment to fully initialize
  sleep 1
  # Try a simple endpoint that requires database access
  if ! curl -sSf "http://127.0.0.1:8001/api/v1/drawers" >/dev/null 2>&1; then
    echo "⚠️  Warning: Server started but may not be using test database correctly"
    echo "   Check server logs in ${LOG_FILE}"
  fi
fi

if [ "$STARTED" -ne 1 ]; then
    echo "❌ FastAPI server did not start in time for contract tests"
    echo "—— Last server log output ———————————————————————————————"
    tail -n 120 "$LOG_FILE" || true
    echo "—————————————————————————————————————————————————————————"
    cleanup_test_server true
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
  cleanup_test_server true
  exit 1
fi

# Full contract suite
if ! pytest -m contract ${CONTR_ARGS[@]}; then
  echo "❌ Contract tests failed"
  cleanup_test_server true
  exit 1
fi

# Stop background server before starting the dev server in the foreground
# Now delete the test database since tests are done
cleanup_test_server true
trap - EXIT

# Clear APP_DB_PATH so dev server uses default database
unset APP_DB_PATH

# Verify APP_DB_PATH is not set (safety check)
if [ -n "${APP_DB_PATH:-}" ]; then
  echo "⚠️  WARNING: APP_DB_PATH is still set to: ${APP_DB_PATH}"
  echo "   This should not happen - clearing it now..."
  unset APP_DB_PATH
fi

# Verify we're using the default database (not test database)
DEFAULT_DB_PATH="${REPO_ROOT}/data/lego_inventory.db"
echo ""
echo "🔒 SAFETY CHECK: Verifying database isolation..."
echo "   - Test database: ${TEST_DB_PATH:-N/A} (should be removed)"
if [ -n "${TEST_DB_PATH:-}" ] && [ -f "${TEST_DB_PATH}" ]; then
  echo "   ⚠️  WARNING: Test database still exists! Removing now..."
  rm -f "${TEST_DB_PATH}"
fi
echo "   - Production database: ${DEFAULT_DB_PATH}"
echo "   - APP_DB_PATH: ${APP_DB_PATH:-<unset - will use default>}"
echo "   ✅ Dev server will use production database"
echo ""

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
# Do NOT `source` data/.env here: dotenv values may contain `$...` which bash will expand.
# We only need to pass a client-visible safe mode flag into Next.js.
# Map backend safe mode flag to a client-visible flag if not explicitly set.
if [ -z "${NEXT_PUBLIC_APP_SAFE_MODE:-}" ] && [ -n "${APP_SAFE_MODE:-}" ]; then
  export NEXT_PUBLIC_APP_SAFE_MODE="${APP_SAFE_MODE}"
fi
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
echo "🔒 Database: Using production database at ${DEFAULT_DB_PATH}"
echo "   (Test database was isolated and has been removed)"
echo ""
echo "🌐 Access from other devices on your network:"
echo "   - Frontend: http://${LAN_IP}:3001"
echo "   - Backend:  http://${LAN_IP}:${PORT}"
echo "   - API Docs: http://${LAN_IP}:${PORT}/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

HOST="$HOST" PORT="$PORT" exec python -m uvicorn app.api.main:app --host "$HOST" --port "$PORT" --reload