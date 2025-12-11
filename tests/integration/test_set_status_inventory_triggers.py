"""Integration tests for set status change triggers and inventory updates."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path
repo_root = Path(__file__).parent.parent.parent
if str(repo_root / "src") not in sys.path:
    sys.path.insert(0, str(repo_root / "src"))


@pytest.fixture(scope="module")
def test_db():
    """Create a temporary database with full schema for integration tests."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_status_triggers_")
    os.close(fd)

    # Store original value
    original_db_path = os.environ.get("APP_DB_PATH")

    # Override database path
    os.environ["APP_DB_PATH"] = path

    # Create schema manually
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Create full schema
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS parts (
              design_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              part_url TEXT,
              part_img_url TEXT,
              ignore_in_inventory INTEGER DEFAULT 0,
              part_category_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS part_categories (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS colors (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              hex TEXT
            );
            CREATE TABLE IF NOT EXISTS themes (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS drawers (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              description TEXT,
              kind TEXT,
              cols INTEGER,
              rows INTEGER,
              sort_index INTEGER DEFAULT 0,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
              deleted_at TEXT
            );
            CREATE TABLE IF NOT EXISTS containers (
              id INTEGER PRIMARY KEY,
              drawer_id INTEGER NOT NULL REFERENCES drawers(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              description TEXT,
              row_index INTEGER,
              col_index INTEGER,
              sort_index INTEGER DEFAULT 0,
              is_put_away_bin INTEGER DEFAULT 0,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
              deleted_at TEXT,
              UNIQUE(drawer_id, row_index, col_index)
            );
            CREATE TABLE IF NOT EXISTS sets (
              id INTEGER PRIMARY KEY,
              set_num TEXT,
              name TEXT NOT NULL,
              year INTEGER,
              theme_id INTEGER,
              image_url TEXT,
              rebrickable_url TEXT,
              status TEXT,
              added_at TEXT
            );
            CREATE TABLE IF NOT EXISTS set_parts (
              id INTEGER PRIMARY KEY,
              set_num TEXT NOT NULL,
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
              container_id INTEGER REFERENCES containers(id),
              drawer TEXT,
              container TEXT,
              set_number TEXT
            );
            """
        )
        conn.commit()

    # Seed test data
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Parts
        conn.execute(
            "INSERT INTO parts(design_id, name, ignore_in_inventory) VALUES ('3001', 'Brick 2x4', 0)"
        )
        conn.execute(
            "INSERT INTO parts(design_id, name, ignore_in_inventory) VALUES ('3023', 'Plate 1x2', 0)"
        )

        # Colors
        conn.execute("INSERT INTO colors(id, name, hex) VALUES (1, 'Black', '000000')")
        conn.execute("INSERT INTO colors(id, name, hex) VALUES (5, 'Red', 'FF0000')")

        # Drawers and containers
        conn.execute("INSERT INTO drawers(id, name, deleted_at) VALUES (1, 'Drawer A', NULL)")
        conn.execute("INSERT INTO drawers(id, name, deleted_at) VALUES (2, 'Drawer B', NULL)")
        conn.execute(
            "INSERT INTO containers(id, drawer_id, name, is_put_away_bin, deleted_at) VALUES (1, 1, 'Container 1', 0, NULL)"
        )
        conn.execute(
            "INSERT INTO containers(id, drawer_id, name, is_put_away_bin, deleted_at) VALUES (2, 2, 'Putaway Bin', 1, NULL)"
        )

        # A set in 'loose' status with parts in storage
        conn.execute(
            "INSERT INTO sets(id, set_num, name, year, status) VALUES (1, 'TEST-1', 'Test Set', 2024, 'loose')"
        )
        conn.execute(
            "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES ('TEST-1', '3001', 1, 10, 0)"
        )
        conn.execute(
            "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES ('TEST-1', '3023', 5, 5, 0)"
        )

        # Inventory items in storage (Container 1, not putaway bin)
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3001', 1, 10, 'loose', 1)"
        )
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3023', 5, 5, 'loose', 1)"
        )

        conn.commit()

    try:
        yield path
    finally:
        # Restore original value
        if original_db_path is not None:
            os.environ["APP_DB_PATH"] = original_db_path
        elif "APP_DB_PATH" in os.environ:
            del os.environ["APP_DB_PATH"]

        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@pytest.fixture(scope="module")
def client(test_db):
    """Create FastAPI TestClient with test database."""
    import sqlite3

    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.di import get_db_connection

    # Override the database connection dependency to use our test database
    def override_get_db_connection():
        conn = sqlite3.connect(test_db, check_same_thread=False, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    app.dependency_overrides[get_db_connection] = override_get_db_connection

    yield TestClient(app)

    # Clean up: remove the override
    app.dependency_overrides.clear()


def test_loose_to_teardown_moves_to_putaway_bin(client, test_db):
    """Test that changing status from Loose to Teardown moves all parts to putaway bin."""
    # Verify initial state
    inventory_resp = client.get("/api/v1/inventory/loose")
    assert inventory_resp.status_code == 200
    initial_items = inventory_resp.json()

    items_in_container_1 = [
        item
        for item in initial_items
        if item.get("container_id") == 1 and item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_in_container_1) == 2

    # Change status to teardown
    status_resp = client.patch("/api/v1/sets/TEST-1/status", json={"status": "teardown"})
    assert status_resp.status_code == 200

    # Verify all parts moved to putaway bin (container_id = 2)
    inventory_resp_after = client.get("/api/v1/inventory/loose")
    assert inventory_resp_after.status_code == 200
    after_items = inventory_resp_after.json()

    items_in_putaway = [
        item
        for item in after_items
        if item.get("container_id") == 2 and item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_in_putaway) == 2

    # Verify nothing left in Container 1
    items_in_container_1_after = [
        item
        for item in after_items
        if item.get("container_id") == 1 and item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_in_container_1_after) == 0


def test_loose_to_built_removes_from_inventory(client, test_db):
    """Test that changing status from Loose to Built removes all parts from inventory."""
    # Reset set status to loose and add inventory back
    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE sets SET status = 'loose' WHERE set_num = 'TEST-1'")
        conn.execute("DELETE FROM inventory WHERE design_id IN ('3001', '3023')")
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3001', 1, 10, 'loose', 1)"
        )
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3023', 5, 5, 'loose', 1)"
        )
        conn.commit()

    # Change status to built
    status_resp = client.patch("/api/v1/sets/TEST-1/status", json={"status": "built"})
    assert status_resp.status_code == 200

    # Verify all parts removed from inventory
    inventory_resp = client.get("/api/v1/inventory/loose")
    assert inventory_resp.status_code == 200
    items = inventory_resp.json()

    items_for_set = [item for item in items if item.get("part_id") in ("3001", "3023")]
    assert len(items_for_set) == 0


def test_built_to_teardown_adds_to_putaway_bin(client, test_db):
    """Test that changing status from Built (or other) to Teardown adds all parts to putaway bin."""
    # Reset set status to built and ensure no inventory
    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE sets SET status = 'built' WHERE set_num = 'TEST-1'")
        conn.execute("DELETE FROM inventory WHERE design_id IN ('3001', '3023')")
        conn.commit()

    # Verify no inventory exists
    inventory_resp_before = client.get("/api/v1/inventory/loose")
    assert inventory_resp_before.status_code == 200
    items_before = inventory_resp_before.json()
    items_for_set_before = [
        item for item in items_before if item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_for_set_before) == 0

    # Change status to teardown
    status_resp = client.patch("/api/v1/sets/TEST-1/status", json={"status": "teardown"})
    assert status_resp.status_code == 200

    # Verify all parts added to putaway bin
    inventory_resp_after = client.get("/api/v1/inventory/loose")
    assert inventory_resp_after.status_code == 200
    items_after = inventory_resp_after.json()

    items_in_putaway = [
        item
        for item in items_after
        if item.get("container_id") == 2 and item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_in_putaway) == 2

    # Verify quantities match set parts
    for item in items_in_putaway:
        if item["part_id"] == "3001" and item["color_id"] == 1:
            assert item["quantity"] == 10
        elif item["part_id"] == "3023" and item["color_id"] == 5:
            assert item["quantity"] == 5


def test_ignore_in_inventory_parts_not_added_to_putaway(client, test_db):
    """Test that parts with ignore_in_inventory flag are not added to putaway bin."""
    # Add a part with ignore_in_inventory flag
    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO parts(design_id, name, ignore_in_inventory) VALUES ('STICKER', 'Sticker Sheet', 1)"
        )
        conn.execute(
            "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES ('TEST-1', 'STICKER', 1, 1, 0)"
        )
        conn.execute("UPDATE sets SET status = 'built' WHERE set_num = 'TEST-1'")
        conn.execute("DELETE FROM inventory WHERE design_id IN ('3001', '3023', 'STICKER')")
        conn.commit()

    # Change status to teardown
    status_resp = client.patch("/api/v1/sets/TEST-1/status", json={"status": "teardown"})
    assert status_resp.status_code == 200

    # Verify sticker is NOT in inventory
    inventory_resp = client.get("/api/v1/inventory/loose")
    assert inventory_resp.status_code == 200
    items = inventory_resp.json()

    sticker_items = [item for item in items if item.get("part_id") == "STICKER"]
    assert len(sticker_items) == 0

    # But other parts should be there
    other_items = [
        item
        for item in items
        if item.get("part_id") in ("3001", "3023") and item.get("container_id") == 2
    ]
    assert len(other_items) == 2


def test_teardown_to_loose_moves_to_putaway_bin(client, test_db):
    """Test that changing status from Teardown to Loose moves all parts to Put Away bin."""
    # Reset: Set status to teardown and ensure parts are in a different container
    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE sets SET status = 'teardown' WHERE set_num = 'TEST-1'")
        conn.execute("DELETE FROM inventory WHERE design_id IN ('3001', '3023')")
        # Add parts to Container 1 (not putaway bin)
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3001', 1, 10, 'loose', 1)"
        )
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3023', 5, 5, 'loose', 1)"
        )
        conn.commit()

    # Verify initial state: parts are in Container 1
    inventory_resp = client.get("/api/v1/inventory/loose")
    assert inventory_resp.status_code == 200
    initial_items = inventory_resp.json()

    items_in_container_1 = [
        item
        for item in initial_items
        if item.get("container_id") == 1 and item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_in_container_1) == 2

    # Change status to loose
    status_resp = client.patch("/api/v1/sets/TEST-1/status", json={"status": "loose"})
    assert status_resp.status_code == 200

    # Verify all parts moved to putaway bin (container_id = 2)
    inventory_resp_after = client.get("/api/v1/inventory/loose")
    assert inventory_resp_after.status_code == 200
    after_items = inventory_resp_after.json()

    items_in_putaway = [
        item
        for item in after_items
        if item.get("container_id") == 2 and item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_in_putaway) == 2

    # Verify nothing left in Container 1
    items_in_container_1_after = [
        item
        for item in after_items
        if item.get("container_id") == 1 and item.get("part_id") in ("3001", "3023")
    ]
    assert len(items_in_container_1_after) == 0
