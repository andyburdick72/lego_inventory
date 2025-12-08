import sqlite3
from pathlib import Path

import pytest

from infra.db.repositories.colors_repo import ColorsRepo
from infra.db.repositories.inventory_repo import InventoryRepo
from infra.db.repositories.parts_repo import PartsRepo
from infra.db.repositories.sets_repo import SetsRepo


@pytest.fixture
def conn_rw():
    db_path = Path(":memory:")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS colors (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          hex TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parts (
          design_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          part_url TEXT,
          part_img_url TEXT
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

        CREATE TABLE IF NOT EXISTS sets (
          id INTEGER PRIMARY KEY,
          set_num TEXT,
          name TEXT NOT NULL,
          year INTEGER,
          theme_id INTEGER REFERENCES themes(id),
          image_url TEXT,
          rebrickable_url TEXT,
          status TEXT,
          added_at TEXT
        );
        """
    )
    conn.execute("INSERT INTO colors(id, name, hex) VALUES (1, 'Red', '#FF0000')")
    conn.execute("INSERT INTO parts(design_id, name) VALUES ('3001', 'Brick 2 x 4')")
    conn.execute(
        "INSERT INTO inventory(design_id, color_id, quantity, status, container_id, drawer, container, set_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("3001", 1, 10, "loose", None, None, None, None),
    )
    conn.execute(
        "INSERT INTO sets(set_num, name, year, theme_id, image_url, rebrickable_url, status, added_at) VALUES (?,?,?,?,?,?,?,?)",
        ("80000-1", "Test Set", 2024, None, None, None, "wip", None),
    )
    conn.commit()
    yield conn
    conn.close()


def test_inventory_repo_inventory_by_part_and_loose_total(conn_rw):
    inv = InventoryRepo(conn_rw)
    rows = inv.inventory_by_part("3001")
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["status"] == "loose"
    # loose_total should reflect the seeded quantity (10)
    assert inv.loose_total() >= 10


def test_inventory_repo_crud_operations(conn_rw):
    """Test CRUD operations on inventory items."""
    inv = InventoryRepo(conn_rw)
    
    # Get inventory ID directly from database (iter_loose_parts requires containers/drawers)
    cursor = conn_rw.execute(
        "SELECT id FROM inventory WHERE status = 'loose' LIMIT 1"
    )
    row = cursor.fetchone()
    if not row:
        pytest.skip("No loose inventory items in test database")
    inventory_id = row["id"]
    
    # Get the inventory item by ID
    existing_item = inv.get_inventory_by_id(inventory_id)
    assert existing_item is not None
    
    # Test get_inventory_by_id - verify it returns the correct structure
    item = inv.get_inventory_by_id(inventory_id)
    assert item is not None
    assert item["part_id"] == existing_item["part_id"]
    assert item["color_id"] == existing_item["color_id"]
    
    # Test update_inventory_quantity
    original_quantity = item["quantity"]
    new_quantity = original_quantity + 5
    inv.update_inventory_quantity(inventory_id, new_quantity)
    
    updated_item = inv.get_inventory_by_id(inventory_id)
    assert updated_item is not None
    assert updated_item["quantity"] == new_quantity
    
    # Test update_inventory_location (set container_id)
    inv.update_inventory_location(inventory_id, None)
    item_no_location = inv.get_inventory_by_id(inventory_id)
    assert item_no_location is not None
    assert item_no_location.get("container_id") is None
    
    # Restore original quantity
    inv.update_inventory_quantity(inventory_id, original_quantity)
    
    # Test move_inventory - create a second inventory item to move to
    # First, create another inventory item
    conn_rw.execute(
        "INSERT INTO inventory(design_id, color_id, quantity, status) VALUES (?, ?, ?, ?)",
        ("3001", 1, 5, "loose")
    )
    conn_rw.commit()
    
    # Get the new inventory ID
    cursor = conn_rw.execute(
        "SELECT id FROM inventory WHERE design_id = ? AND color_id = ? AND status = 'loose' AND id != ? LIMIT 1",
        ("3001", 1, inventory_id)
    )
    new_inventory_id = cursor.fetchone()["id"]
    
    # Test move_inventory
    move_quantity = 2
    inv.move_inventory(new_inventory_id, None, move_quantity)
    
    # Verify source quantity decreased
    source_item = inv.get_inventory_by_id(new_inventory_id)
    assert source_item is not None
    assert source_item["quantity"] == 5 - move_quantity
    
    # Test delete_inventory
    inv.delete_inventory(new_inventory_id)
    deleted_item = inv.get_inventory_by_id(new_inventory_id)
    assert deleted_item is None
    
    # Test error cases
    # get_inventory_by_id returns None for non-existent items (doesn't raise)
    assert inv.get_inventory_by_id(999999) is None
    
    # Other methods raise ValueError for non-existent items
    with pytest.raises(ValueError, match="not found"):
        inv.update_inventory_quantity(999999, 10)
    
    with pytest.raises(ValueError, match="not found"):
        inv.delete_inventory(999999)
    
    with pytest.raises(ValueError, match="not found"):
        inv.move_inventory(999999, None, 1)
    
    # Test insufficient quantity for move
    if updated_item["quantity"] > 0:
        with pytest.raises(ValueError, match="Insufficient quantity"):
            inv.move_inventory(inventory_id, None, updated_item["quantity"] + 100)


def test_sets_repo_basic_and_total(conn_rw):
    # create set_parts table locally for this test
    # Note: set_parts uses set_num as part of composite primary key, not a foreign key to sets.id
    conn_rw.executescript(
        """
        CREATE TABLE IF NOT EXISTS set_parts (
          set_num TEXT NOT NULL,
          design_id TEXT NOT NULL REFERENCES parts(design_id),
          color_id INTEGER NOT NULL REFERENCES colors(id),
          quantity INTEGER NOT NULL,
          PRIMARY KEY (set_num, design_id, color_id)
        );
        """
    )
    # seed a couple of set parts so total > 0
    conn_rw.execute(
        "INSERT INTO set_parts(set_num, design_id, color_id, quantity) VALUES (?,?,?,?)",
        ("80000-1", "3001", 1, 3),
    )
    conn_rw.commit()

    sets = SetsRepo(conn_rw)
    row = sets.get_set_by_num("80000-1")
    assert row is not None
    assert row["set_num"] == "80000-1"
    total = sets.set_total_for_statuses(["wip", "built", "in_box", "teardown"])
    assert total >= 3


def test_parts_repo_fetch_name(conn_rw):
    parts = PartsRepo(conn_rw)
    assert parts.fetch_part_name("3001") == "Brick 2 x 4"


def test_colors_repo_resolve_alias(conn_rw):
    # create color_aliases for this test
    conn_rw.executescript(
        """
        CREATE TABLE IF NOT EXISTS color_aliases (
          alias_id INTEGER PRIMARY KEY,
          color_id INTEGER NOT NULL REFERENCES colors(id)
        );
        """
    )
    conn_rw.execute(
        "INSERT OR IGNORE INTO color_aliases(alias_id, color_id) VALUES (?, ?)",
        (999, 1),
    )
    conn_rw.commit()

    colors = ColorsRepo(conn_rw)
    assert colors.resolve_color_alias(999) == 1
