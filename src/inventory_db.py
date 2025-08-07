"""
SQLite data‑access layer, **v2**.

Canonical keys = Rebrickable IDs.
BrickLink / Instabrick IDs are kept only in alias tables.

Schema
------

colors
    id INTEGER PRIMARY KEY          – Rebrickable colour id
    name TEXT
    hex  TEXT
    r, g, b INTEGER                 – pre‑split RGB (convenience)

color_aliases
    alias_id INTEGER PRIMARY KEY    – BrickLink colour id
    color_id INTEGER REFERENCES colors(id)

parts
    design_id TEXT PRIMARY KEY      – Rebrickable design‑id
    name      TEXT

part_aliases
    alias TEXT PRIMARY KEY          – BrickLink/Instabrick id
    design_id TEXT REFERENCES parts(design_id)

inventory
    id INTEGER PRIMARY KEY
    design_id TEXT  REFERENCES parts(design_id)
    color_id  INTEGER REFERENCES colors(id)
    quantity  INTEGER
    status    TEXT                  – loose / built / wip / in_box / teardown
    drawer    TEXT                  – loose only
    container TEXT                  – loose only
    set_number TEXT                 – built/WIP/In‑Box

Only stdlib; no external deps.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "lego_inventory.db"


# --------------------------------------------------------------------------- helpers
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- schema
def init_db() -> None:
    """(Re)create all tables if they don't already exist."""
    with _connect() as conn:
        c = conn.cursor()
        c.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS colors(
                id   INTEGER PRIMARY KEY,
                name TEXT,
                hex  TEXT,
                r    INTEGER,
                g    INTEGER,
                b    INTEGER
            );

            CREATE TABLE IF NOT EXISTS color_aliases(
                alias_id INTEGER PRIMARY KEY,
                color_id INTEGER REFERENCES colors(id)
            );

            CREATE TABLE IF NOT EXISTS parts(
                design_id TEXT PRIMARY KEY,
                name      TEXT
            );

            CREATE TABLE IF NOT EXISTS part_aliases(
                alias     TEXT PRIMARY KEY,
                design_id TEXT REFERENCES parts(design_id)
            );

            CREATE TABLE IF NOT EXISTS inventory(
                id         INTEGER PRIMARY KEY,
                design_id  TEXT    REFERENCES parts(design_id),
                color_id   INTEGER REFERENCES colors(id),
                quantity   INTEGER,
                status     TEXT,
                drawer     TEXT,
                container  TEXT,
                set_number TEXT
            );

            -- Added sets and set_parts tables and indexes
            CREATE TABLE IF NOT EXISTS sets(
                id               INTEGER PRIMARY KEY,
                set_num          TEXT,     -- e.g. 40571-1
                name             TEXT,
                year             INTEGER,
                theme            TEXT,
                image_url        TEXT,
                rebrickable_url  TEXT,
                status           TEXT,
                added_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS set_parts(
                set_num   TEXT,
                design_id TEXT,
                color_id  INTEGER,
                quantity  INTEGER,
                PRIMARY KEY (set_num, design_id, color_id),
                FOREIGN KEY (design_id) REFERENCES parts(design_id),
                FOREIGN KEY (color_id)  REFERENCES colors(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sets_set_num     ON sets(set_num);
            CREATE INDEX IF NOT EXISTS idx_set_parts_set    ON set_parts(set_num);
            CREATE INDEX IF NOT EXISTS idx_set_parts_part   ON set_parts(design_id, color_id);
            CREATE INDEX IF NOT EXISTS idx_inv_status       ON inventory(status);
            CREATE INDEX IF NOT EXISTS idx_inv_part_color   ON inventory(design_id,color_id);
            CREATE INDEX IF NOT EXISTS idx_color_alias      ON color_aliases(alias_id);
            CREATE INDEX IF NOT EXISTS idx_part_alias       ON part_aliases(alias);
            """
        )
        conn.commit()


# --------------------------------------------------------------------------- color helpers
def insert_color(color_id: int, name: str, hex_code: str) -> None:
    r, g, b = tuple(int(hex_code[i : i + 2], 16) for i in (0, 2, 4))
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO colors(id,name,hex,r,g,b) VALUES (?,?,?,?,?,?)",
            (color_id, name, hex_code.upper(), r, g, b),
        )
        conn.commit()


def add_color_alias(bl_id: int, color_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO color_aliases(alias_id,color_id) VALUES (?,?)",
            (bl_id, color_id),
        )
        conn.commit()


def resolve_color(bl_id: int) -> Optional[int]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT color_id FROM color_aliases WHERE alias_id=?", (bl_id,)
        ).fetchone()
        return row["color_id"] if row else None


# --------------------------------------------------------------------------- part helpers
def insert_part(design_id: str, name: str) -> None:
    """
    Insert a part or update its placeholder name.

    * If the part is new → insert (design_id, name).
    * If the part already exists **and** the stored name is
      'Unknown part' → upgrade it to the supplied name.
    * Otherwise leave the existing (non‑placeholder) name untouched.
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO parts(design_id, name) VALUES (?, ?)
            ON CONFLICT(design_id) DO
              UPDATE SET name = excluded.name
              WHERE parts.name = 'Unknown part'
            """,
            (design_id, name),
        )
        conn.commit()


# List all design_ids whose name is still the placeholder
def unknown_parts() -> List[str]:
    """Return a list of design_ids whose name is still the placeholder."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT design_id FROM parts WHERE name = 'Unknown part'"
        ).fetchall()
    return [r["design_id"] for r in rows]


def add_part_alias(alias: str, design_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO part_aliases(alias,design_id) VALUES (?,?)",
            (alias, design_id),
        )
        conn.commit()


def resolve_part(alias: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT design_id FROM part_aliases WHERE alias=?", (alias,)
        ).fetchone()
        return row["design_id"] if row else None


# --------------------------------------------------------------------------- new helper: get_part
def get_part(design_id: str) -> Optional[Dict]:
    """
    Retrieve a single part row (design_id, name) as a dict, or None
    if the part is not in the table.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT design_id, name FROM parts WHERE design_id = ?",
            (design_id,),
        ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- set_parts
def insert_set_part(set_num: str, design_id: str, color_id: int, quantity: int) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO set_parts (set_num, design_id, color_id, quantity)
            VALUES (?, ?, ?, ?)
            """,
            (set_num, design_id, color_id, quantity),
        )
        conn.commit()


def get_set_parts(set_num: str) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT sp.set_num, sp.design_id, p.name, sp.color_id, c.name AS color_name,
                   sp.quantity
            FROM set_parts sp
            JOIN parts p ON sp.design_id = p.design_id
            JOIN colors c ON sp.color_id = c.id
            WHERE sp.set_num = ?
            ORDER BY p.design_id, sp.color_id
            """,
            (set_num,),
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- inventory
def insert_inventory(
    design_id: str,
    color_id: int,
    quantity: int,
    status: str,
    drawer: Optional[str] = None,
    container: Optional[str] = None,
    set_number: Optional[str] = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO inventory
            (design_id,color_id,quantity,status,drawer,container,set_number)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                design_id,
                color_id,
                quantity,
                status,
                drawer,
                container,
                set_number,
            ),
        )
        conn.commit()


# --------------------------------------------------------------------------- queries
def parts_with_totals() -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.design_id, p.name,
                   SUM(i.quantity) AS total_quantity
            FROM parts p
            LEFT JOIN inventory i ON i.design_id = p.design_id
            GROUP BY p.design_id
            ORDER BY p.design_id
            """
        ).fetchall()
        return [dict(r) for r in rows]


def inventory_by_part(design_id: str) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.name AS color_name, c.hex,
                   i.color_id, i.quantity, i.status,
                   i.drawer, i.container, i.set_number
            FROM inventory i
            JOIN colors c ON c.id = i.color_id
            WHERE i.design_id = ?
            ORDER BY i.status, i.drawer, i.container, i.color_id
            """,
            (design_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def locations_map() -> Dict[Tuple[str, str], List[Dict]]:
    """Return hierarchical mapping for loose parts (drawer → container)."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT i.drawer, i.container,
                   p.design_id, p.name,
                   c.name AS color_name, c.hex,
                   SUM(i.quantity) AS qty
            FROM inventory i
            JOIN parts p  ON p.design_id = i.design_id
            JOIN colors c ON c.id = i.color_id
            WHERE i.status = 'loose'
            GROUP BY i.drawer, i.container, p.design_id, i.color_id
            ORDER BY i.drawer, i.container
            """
        ).fetchall()
    tree: Dict[Tuple[str, str], List[Dict]] = {}
    for r in rows:
        key = (r["drawer"], r["container"])
        tree.setdefault(key, []).append(dict(r))
    return tree


def search_parts(query: str) -> List[Dict]:
    pattern = f"%{query}%"
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.design_id, p.name,
                   SUM(i.quantity) AS total_quantity
            FROM parts p
            LEFT JOIN inventory i ON i.design_id = p.design_id
            WHERE p.design_id LIKE ? OR p.name LIKE ?
            GROUP BY p.design_id
            ORDER BY p.design_id
            """,
            (pattern, pattern),
        ).fetchall()
        return [dict(r) for r in rows]

# --------------------------------------------------------------------------- main
if __name__ == "__main__":
    init_db()
    print("Database schema created.")