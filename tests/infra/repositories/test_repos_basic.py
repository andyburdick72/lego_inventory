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
        CREATE TABLE IF NOT EXISTS colors (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          hex TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parts (
          design_id TEXT PRIMARY KEY,
          name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
          id INTEGER PRIMARY KEY,
          design_id TEXT NOT NULL REFERENCES parts(design_id),
          color_id INTEGER NOT NULL REFERENCES colors(id),
          quantity INTEGER NOT NULL,
          status TEXT NOT NULL,
          container_id INTEGER,
          drawer TEXT,
          container TEXT,
          set_number TEXT
        );

        CREATE TABLE IF NOT EXISTS sets (
          set_num TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          year INTEGER,
          theme TEXT,
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
        "INSERT INTO sets(set_num, name, year, theme, image_url, rebrickable_url, status, added_at) VALUES (?,?,?,?,?,?,?,?)",
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


def test_sets_repo_basic_and_total(conn_rw):
    # create set_parts table locally for this test
    conn_rw.executescript(
        """
        CREATE TABLE IF NOT EXISTS set_parts (
          id INTEGER PRIMARY KEY,
          set_num TEXT NOT NULL REFERENCES sets(set_num),
          design_id TEXT NOT NULL REFERENCES parts(design_id),
          color_id INTEGER NOT NULL REFERENCES colors(id),
          quantity INTEGER NOT NULL,
          is_spare INTEGER DEFAULT 0
        );
        """
    )
    # seed a couple of set parts so total > 0
    conn_rw.execute(
        "INSERT INTO set_parts(set_num, design_id, color_id, quantity, is_spare) VALUES (?,?,?,?,?)",
        ("80000-1", "3001", 1, 3, 0),
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
