import os
import sqlite3
import sys
import tempfile

import pytest

# Ensure repo root and 'src/' are on sys.path for imports like 'from src.core import enums'
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_SRC_PATH = os.path.join(_REPO_ROOT, "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


API_ENV_VAR = "API_BASE_URL"


def pytest_addoption(parser):
    parser.addoption(
        "--api-base-url",
        action="store",
        default=None,
        help="Override base URL for contract tests (e.g. http://localhost:8000/api)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "contract: mark a test as a contract test")


@pytest.fixture(scope="session")
def api_base_url(pytestconfig):
    # Priority: CLI flag > env var > None (contract tests will skip)
    cli = pytestconfig.getoption("--api-base-url")
    if cli:
        return cli
    return os.environ.get(API_ENV_VAR)


@pytest.fixture
def skip_if_no_api(api_base_url):
    if not api_base_url:
        pytest.skip(
            f"Skipping contract tests: {API_ENV_VAR} is unset and --api-base-url not provided"
        )


# --- SQLite test DB fixtures ---


@pytest.fixture()
def temp_db_path():
    fd, path = tempfile.mkstemp(prefix="lego_", suffix=".db")
    os.close(fd)
    try:
        yield path
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@pytest.fixture()
def conn_rw(temp_db_path):
    """Read/write SQLite connection for repo tests with minimal schema + seed data."""
    conn = sqlite3.connect(temp_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # --- Minimal schema for repo tests ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS parts (
          design_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          part_url TEXT,
          part_img_url TEXT
        );
        CREATE TABLE IF NOT EXISTS colors (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          hex TEXT
        );
        CREATE TABLE IF NOT EXISTS sets (
          set_num TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          year INTEGER,
          status TEXT
        );
        CREATE TABLE IF NOT EXISTS set_parts (
          id INTEGER PRIMARY KEY,
          set_num TEXT NOT NULL REFERENCES sets(set_num) ON DELETE CASCADE,
          design_id TEXT NOT NULL REFERENCES parts(design_id),
          color_id INTEGER NOT NULL REFERENCES colors(id),
          quantity INTEGER NOT NULL,
          is_spare INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS inventory (
          id INTEGER PRIMARY KEY,
          design_id TEXT NOT NULL REFERENCES parts(design_id),
          color_id INTEGER NOT NULL REFERENCES colors(id),
          quantity INTEGER NOT NULL,
          status TEXT NOT NULL,
          container_id INTEGER,
          drawer TEXT,
          container TEXT
        );
        """
    )

    # --- Seed minimal data ---
    conn.execute(
        "INSERT INTO parts(design_id, name) VALUES (?, ?) ON CONFLICT(design_id) DO NOTHING",
        ("3001", "Brick 2 x 4"),
    )
    conn.execute(
        "INSERT INTO parts(design_id, name) VALUES (?, ?) ON CONFLICT(design_id) DO NOTHING",
        ("3023", "Plate 1 x 2"),
    )
    conn.execute(
        "INSERT INTO colors(id, name, hex) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING",
        (1, "Black", "#000000"),
    )
    conn.execute(
        "INSERT INTO colors(id, name, hex) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING",
        (5, "Red", "#FF0000"),
    )

    # Loose inventory rows
    conn.execute(
        "INSERT INTO inventory(design_id,color_id,quantity,status,drawer,container) VALUES (?,?,?,?,?,?)",
        ("3001", 1, 10, "loose", "Drawer A", "All"),
    )
    conn.execute(
        "INSERT INTO inventory(design_id,color_id,quantity,status,drawer,container) VALUES (?,?,?,?,?,?)",
        ("3023", 5, 5, "loose", "Drawer B", "All"),
    )

    # A set with parts so set_total > 0
    conn.execute(
        "INSERT INTO sets(set_num, name, year, status) VALUES (?,?,?,?)",
        ("80000-1", "Test Set", 2024, "wip"),
    )
    conn.execute(
        "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES (?,?,?,?,?)",
        ("80000-1", "3001", 1, 100, 0),
    )
    conn.execute(
        "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES (?,?,?,?,?)",
        ("80000-1", "3023", 5, 50, 0),
    )

    conn.commit()
    try:
        yield conn
    finally:
        conn.close()
