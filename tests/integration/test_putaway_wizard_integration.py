"""Integration tests for Put-Away Wizard full flow."""

import importlib
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
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_putaway_")
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
        conn.execute(
            "INSERT INTO parts(design_id, name, ignore_in_inventory) VALUES ('STICKER', 'Sticker Sheet', 1)"
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
        conn.execute(
            "INSERT INTO containers(id, drawer_id, name, is_put_away_bin, deleted_at) VALUES (3, 1, 'Container 2', 0, NULL)"
        )

        # A set (need to use proper schema: id, set_num, name, etc.)
        conn.execute(
            "INSERT INTO sets(id, set_num, name, year, status) VALUES (1, 'TEST-1', 'Test Set', 2024, 'built')"
        )
        conn.execute(
            "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES ('TEST-1', '3001', 1, 10, 0)"
        )
        conn.execute(
            "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES ('TEST-1', '3023', 5, 5, 0)"
        )
        conn.execute(
            "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES ('TEST-1', 'STICKER', 1, 1, 0)"
        )

        # Some existing inventory in putaway bin
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3001', 5, 3, 'loose', 2)"
        )

        conn.commit()

    # Store original value
    original_db_path = os.environ.get("APP_DB_PATH")

    # Override database path
    os.environ["APP_DB_PATH"] = path

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
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.di import get_db_connection
    import sqlite3
    
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


def test_putaway_parts_from_set_filters_ignore_in_inventory(client, test_db):
    """Test that parts with ignore_in_inventory flag are filtered out."""
    response = client.get("/api/v1/putaway/parts-from-set/TEST-1")
    assert response.status_code == 200
    data = response.json()

    # Should only return 2 parts (STICKER should be filtered out)
    assert len(data) == 2
    design_ids = {part["design_id"] for part in data}
    assert "STICKER" not in design_ids
    assert "3001" in design_ids
    assert "3023" in design_ids


def test_putaway_parts_from_set_includes_suggestions(client, test_db):
    """Test that parts include storage location suggestions."""
    response = client.get("/api/v1/putaway/parts-from-set/TEST-1")
    assert response.status_code == 200
    data = response.json()

    # All parts should have suggestion (may be None)
    for part in data:
        assert "suggestion" in part
        if part["suggestion"]:
            assert "confidence" in part["suggestion"]
            assert part["suggestion"]["confidence"] in ["high", "medium", "low", "none"]


def test_putaway_bin_parts_includes_existing_inventory(client, test_db):
    """Test that putaway bin returns parts from the bin."""
    response = client.get("/api/v1/putaway/parts-in-bin")
    assert response.status_code == 200
    data = response.json()

    # Should have at least the part we seeded
    assert len(data) >= 1
    found = False
    for part in data:
        if part["design_id"] == "3001" and part["color_id"] == 5:
            found = True
            assert part["quantity"] == 3
            assert part["inventory_id"] is not None
            break
    assert found


def test_putaway_bin_parts_search_filter(client, test_db):
    """Test search filtering for putaway bin parts."""
    response = client.get("/api/v1/putaway/parts-in-bin?search=3001")
    assert response.status_code == 200
    data = response.json()

    # Should filter to parts matching search
    for part in data:
        assert "3001" in part["design_id"].lower() or "3001" in part.get("part_name", "").lower()


def test_putaway_full_flow_part_out(client, test_db):
    """Test full putaway wizard flow for set part-out."""
    # 1. Get parts from set
    parts_resp = client.get("/api/v1/putaway/parts-from-set/TEST-1")
    assert parts_resp.status_code == 200
    parts = parts_resp.json()
    assert len(parts) >= 2

    # 2. Create assignments for first part
    part = parts[0]
    assignments = [
        {
            "design_id": part["design_id"],
            "color_id": part["color_id"],
            "quantity": part["quantity"],
            "container_id": 1,  # Use Container 1
            "inventory_id": None,
        }
    ]

    # 3. Batch assign
    assign_resp = client.post("/api/v1/putaway/batch-assign", json={"assignments": assignments})
    assert assign_resp.status_code == 200
    result = assign_resp.json()
    assert result["total_requested"] == 1
    assert result["total_assigned"] == 1

    # 4. Verify inventory was created
    inventory_resp = client.get("/api/v1/inventory/loose")
    assert inventory_resp.status_code == 200
    inventory_items = inventory_resp.json()

    # Find the new inventory item
    found = False
    for item in inventory_items:
        if (
            item["part_id"] == part["design_id"]
            and item["color_id"] == part["color_id"]
            and item["container_id"] == 1
        ):
            found = True
            assert item["quantity"] == part["quantity"]
            assert item["status"] == "loose_parts"
            break
    assert found


def test_putaway_full_flow_putaway_bin(client, test_db):
    """Test full putaway wizard flow for putaway bin."""
    # 1. Get parts in putaway bin
    bin_resp = client.get("/api/v1/putaway/parts-in-bin")
    assert bin_resp.status_code == 200
    bin_parts = bin_resp.json()
    assert len(bin_parts) >= 1

    # Find the part we seeded
    test_part = None
    for part in bin_parts:
        if part["design_id"] == "3001" and part["color_id"] == 5:
            test_part = part
            break

    if not test_part:
        pytest.skip("Test part not found in putaway bin")

    # 2. Create assignment to move from bin to container
    assignments = [
        {
            "design_id": test_part["design_id"],
            "color_id": test_part["color_id"],
            "quantity": test_part["quantity"],
            "container_id": 1,  # Move to Container 1
            "inventory_id": test_part["inventory_id"],
        }
    ]

    # 3. Batch assign
    assign_resp = client.post("/api/v1/putaway/batch-assign", json={"assignments": assignments})
    assert assign_resp.status_code == 200
    result = assign_resp.json()
    assert result["total_requested"] == 1
    assert result["total_assigned"] == 1

    # 4. Verify inventory was moved
    inventory_resp = client.get("/api/v1/inventory/loose")
    assert inventory_resp.status_code == 200
    inventory_items = inventory_resp.json()

    # Find the moved inventory item
    found = False
    for item in inventory_items:
        if (
            item["part_id"] == test_part["design_id"]
            and item["color_id"] == test_part["color_id"]
            and item["container_id"] == 1
        ):
            found = True
            assert item["quantity"] == test_part["quantity"]
            assert item["status"] == "loose_parts"
            break
    assert found

    # Verify it's no longer in putaway bin
    bin_resp_after = client.get("/api/v1/putaway/parts-in-bin")
    assert bin_resp_after.status_code == 200
    bin_parts_after = bin_resp_after.json()

    still_in_bin = any(
        p["design_id"] == test_part["design_id"] and p["color_id"] == test_part["color_id"]
        for p in bin_parts_after
    )
    assert not still_in_bin


def test_putaway_merge_existing_inventory(client, test_db):
    """Test that assigning to a location with existing inventory merges quantities."""
    # First, create some inventory at a location
    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO inventory(design_id, color_id, quantity, status, container_id) VALUES ('3023', 1, 5, 'loose', 1)"
        )
        conn.commit()

    # Now assign more of the same part/color to the same container
    assignments = [
        {
            "design_id": "3023",
            "color_id": 1,
            "quantity": 3,
            "container_id": 1,
            "inventory_id": None,
        }
    ]

    assign_resp = client.post("/api/v1/putaway/batch-assign", json={"assignments": assignments})
    assert assign_resp.status_code == 200
    result = assign_resp.json()
    assert result["total_assigned"] == 1
    assert "merged" in result["assignments"][0]["message"].lower()

    # Verify quantity was merged (should be 5 + 3 = 8)
    inventory_resp = client.get("/api/v1/inventory/loose")
    assert inventory_resp.status_code == 200
    inventory_items = inventory_resp.json()

    found = False
    for item in inventory_items:
        if item["part_id"] == "3023" and item["color_id"] == 1 and item["container_id"] == 1:
            found = True
            assert item["quantity"] == 8
            break
    assert found
