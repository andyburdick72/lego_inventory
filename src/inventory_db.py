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
    part_url  TEXT
    part_img_url TEXT

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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # Apply robust defaults on every connection
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
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
                name      TEXT,
                part_url  TEXT,
                part_img_url TEXT
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

            -- New drawers/containers tables
            CREATE TABLE IF NOT EXISTS drawers(
                id          INTEGER PRIMARY KEY,
                name        TEXT NOT NULL UNIQUE,
                description TEXT,
                kind        TEXT,
                cols        INTEGER,
                rows        INTEGER,
                sort_index  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS containers(
                id          INTEGER PRIMARY KEY,
                drawer_id   INTEGER NOT NULL REFERENCES drawers(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                description TEXT,
                row_index   INTEGER,
                col_index   INTEGER,
                sort_index  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(drawer_id, row_index, col_index)
            );

            CREATE INDEX IF NOT EXISTS idx_containers_drawer ON containers(drawer_id);
            CREATE INDEX IF NOT EXISTS idx_drawers_name      ON drawers(name);

            CREATE INDEX IF NOT EXISTS idx_sets_set_num     ON sets(set_num);
            CREATE INDEX IF NOT EXISTS idx_set_parts_set    ON set_parts(set_num);
            CREATE INDEX IF NOT EXISTS idx_set_parts_part   ON set_parts(design_id, color_id);
            CREATE INDEX IF NOT EXISTS idx_inv_status       ON inventory(status);
            CREATE INDEX IF NOT EXISTS idx_inv_part_color   ON inventory(design_id,color_id);
            CREATE INDEX IF NOT EXISTS idx_color_alias      ON color_aliases(alias_id);
            CREATE INDEX IF NOT EXISTS idx_part_alias       ON part_aliases(alias);
            """
        )
        try:
            conn.execute("ALTER TABLE inventory ADD COLUMN container_id INTEGER REFERENCES containers(id)")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inv_container ON inventory(container_id)")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE parts ADD COLUMN part_url TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE parts ADD COLUMN part_img_url TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()


# --------------------------------------------------------------------------- migration helper (v3)

def migrate_locations_to_containers() -> None:
    """
    One-time backfill to populate drawers/containers and set inventory.container_id
    based on legacy text columns (inventory.drawer, inventory.container).

    Safe to run multiple times.
    """
    with _connect() as conn:
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys=ON;")
        # 1) Seed drawers from distinct legacy drawer names (loose parts only)
        c.execute(
            """
            INSERT OR IGNORE INTO drawers(name)
            SELECT DISTINCT TRIM(drawer) FROM inventory
            WHERE status='loose' AND drawer IS NOT NULL AND TRIM(drawer) <> ''
            """
        )
        # 2) Seed containers under each drawer
        c.execute(
            """
            INSERT OR IGNORE INTO containers(drawer_id, name)
            SELECT d.id, i.container
            FROM inventory i
            JOIN drawers d ON d.name = i.drawer
            WHERE i.status='loose'
              AND i.container IS NOT NULL AND TRIM(i.container) <> ''
            GROUP BY d.id, i.container
            """
        )
        # 3) Point inventory rows at the new containers
        c.execute(
            """
            UPDATE inventory
            SET container_id = (
              SELECT c.id
              FROM containers c
              JOIN drawers d ON d.id = c.drawer_id
              WHERE d.name = inventory.drawer AND c.name = inventory.container
            )
            WHERE status='loose' AND (container_id IS NULL OR container_id = '')
            """
        )
        conn.commit()


# --------------------------------------------------------------------------- drawer/container helpers (CRUD-ish)

def upsert_drawer(
    name: str,
    description: Optional[str] = None,
    kind: Optional[str] = None,
    cols: Optional[int] = None,
    rows: Optional[int] = None,
) -> int:
    """Return the drawer id for `name`, inserting if needed.
    Does not change existing fields on conflict (idempotent).
    """
    name = name.strip()
    with _connect() as conn:
        # Try find existing
        row = conn.execute("SELECT id FROM drawers WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        # Insert new
        cur = conn.execute(
            """
            INSERT INTO drawers(name, description, kind, cols, rows)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, description, kind, cols, rows),
        )
        conn.commit()
        return int(cur.lastrowid)


def upsert_container(
    drawer_id: int,
    name: str,
    description: Optional[str] = None,
    row_index: Optional[int] = None,
    col_index: Optional[int] = None,
) -> int:
    """Return the container id for (drawer_id, name), inserting if needed.
    Uses name for identity within a drawer (no schema uniqueness required).
    """
    name = name.strip()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM containers WHERE drawer_id = ? AND name = ?",
            (drawer_id, name),
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            """
            INSERT INTO containers(drawer_id, name, description, row_index, col_index)
            VALUES (?, ?, ?, ?, ?)
            """,
            (drawer_id, name, description, row_index, col_index),
        )
        conn.commit()
        return int(cur.lastrowid)


def move_container(container_id: int, new_drawer_id: int) -> None:
    """Move an existing container to a different drawer.
    Keeps name/description/indices; only updates drawer_id.
    """
    with _connect() as conn:
        conn.execute(
            "UPDATE containers SET drawer_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_drawer_id, container_id),
        )
        conn.commit()


def assign_inventory_to_container(inventory_id: int, container_id: int) -> None:
    """Point an inventory row at a container (sets status to 'loose' if not already)."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE inventory
            SET container_id = ?, status = 'loose', drawer = NULL, container = NULL
            WHERE id = ?
            """,
            (container_id, inventory_id),
        )
        conn.commit()


def add_loose_inventory_with_container(
    design_id: str,
    color_id: int,
    quantity: int,
    container_id: int,
) -> int:
    """Insert a loose inventory row tied to a specific container_id. Returns new inventory.id."""
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO inventory(design_id, color_id, quantity, status, container_id)
            VALUES (?, ?, ?, 'loose', ?)
            """,
            (design_id, color_id, quantity, container_id),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_or_create_container_by_names(
    drawer_name: str,
    container_name: str,
    *,
    drawer_description: Optional[str] = None,
    container_description: Optional[str] = None,
) -> int:
    """Convenience: upsert a drawer by name, then upsert a container by name; return container_id."""
    d_id = upsert_drawer(drawer_name, drawer_description)
    c_id = upsert_container(d_id, container_name, container_description)
    return c_id


# --------------------------------------------------------------------------- drawer/container listing helpers (read-only UI)

def list_drawers() -> List[Dict]:
    """Return all drawers with container and piece counts."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT d.id,
                   d.name,
                   d.description,
                   d.kind,
                   d.cols,
                   d.rows,
                   d.sort_index,
                   COUNT(DISTINCT c.id) AS container_count,
                   COALESCE(SUM(i.quantity), 0) AS part_count
            FROM drawers d
            LEFT JOIN containers c ON c.drawer_id = d.id
            LEFT JOIN inventory  i ON i.container_id = c.id AND i.status='loose'
            WHERE d.kind IS NULL OR d.kind NOT IN ('rub_box_legacy','rub_box_nested_error')
            GROUP BY d.id
            ORDER BY d.sort_index, d.name
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_drawer(drawer_id: int) -> Optional[Dict]:
    """Return a single drawer row by id, or None."""
    with _connect() as conn:
        r = conn.execute("SELECT * FROM drawers WHERE id = ?", (drawer_id,)).fetchone()
    return dict(r) if r else None


def list_containers_for_drawer(drawer_id: int) -> List[Dict]:
    """Return containers for a drawer with counts and optional positions."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id,
                   c.name,
                   c.description,
                   c.row_index,
                   c.col_index,
                   c.sort_index,
                   COALESCE(SUM(i.quantity), 0) AS part_count,
                   COUNT(DISTINCT i.design_id || ':' || i.color_id) AS unique_parts
            FROM containers c
            LEFT JOIN inventory i ON i.container_id = c.id AND i.status='loose'
            WHERE c.drawer_id = ?
            GROUP BY c.id
            ORDER BY c.row_index, c.col_index, c.sort_index, c.name
            """,
            (drawer_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_container(container_id: int) -> Optional[Dict]:
    """Return a single container row with its drawer name, or None."""
    with _connect() as conn:
        r = conn.execute(
            """
            SELECT c.*, d.name AS drawer_name
            FROM containers c
            JOIN drawers d ON d.id = c.drawer_id
            WHERE c.id = ?
            """,
            (container_id,),
        ).fetchone()
    return dict(r) if r else None


def list_parts_in_container(container_id: int) -> List[Dict]:
    """List aggregated parts (by design_id + color) within a container."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.design_id,
                   p.name AS part_name,
                   col.id   AS color_id,
                   col.name AS color_name,
                   col.hex,
                   SUM(i.quantity) AS qty
            FROM inventory i
            JOIN parts  p   ON p.design_id = i.design_id
            JOIN colors col ON col.id      = i.color_id
            WHERE i.container_id = ? AND i.status='loose'
            GROUP BY p.design_id, col.id
            ORDER BY p.design_id, col.id
            """,
            (container_id,),
        ).fetchall()
    return [dict(r) for r in rows]

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
            "SELECT design_id, name, part_url, part_img_url FROM parts WHERE design_id = ?",
            (design_id,),
        ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- set_parts
def insert_set_part(set_num: str, design_id: str, color_id: int, quantity: int, conn: Optional[sqlite3.Connection] = None) -> None:
    if conn is None:
        with _connect() as local_conn:
            local_conn.execute(
                """
                INSERT OR REPLACE INTO set_parts (set_num, design_id, color_id, quantity)
                VALUES (?, ?, ?, ?)
                """,
                (set_num, design_id, color_id, quantity),
            )
            local_conn.commit()
    else:
        conn.execute(
            """
            INSERT OR REPLACE INTO set_parts (set_num, design_id, color_id, quantity)
            VALUES (?, ?, ?, ?)
            """,
            (set_num, design_id, color_id, quantity),
        )

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

def sets_for_part(design_id: str) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.set_num,
                   s.name        AS set_name,
                   s.year        AS year,
                   c.id          AS color_id,
                   c.name        AS color_name,
                   c.hex         AS hex,
                   sp.quantity   AS quantity
            FROM set_parts sp
            JOIN sets  s ON s.set_num = sp.set_num
            JOIN colors c ON c.id     = sp.color_id
            WHERE sp.design_id = ?
            ORDER BY s.year, s.set_num, c.id
            """,
            (design_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- sets helpers

def get_set(set_num: str) -> Optional[Dict]:
    """Return a single set row by set_num or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT set_num, name, year, theme, image_url, rebrickable_url, status, added_at
            FROM sets
            WHERE set_num = ?
            """,
            (set_num,),
        ).fetchone()
    return dict(row) if row else None


def get_parts_for_set(set_num: str) -> List[Dict]:
    """Return the list of parts for a set with color, qty, and Rebrickable URLs.
    Falls back to canonical URL/placeholder image when metadata is missing.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT sp.design_id,
                   p.name,
                   sp.color_id,
                   c.name AS color_name,
                   c.hex  AS hex,
                   sp.quantity,
                   p.part_url,
                   p.part_img_url
            FROM set_parts sp
            JOIN parts  p ON p.design_id = sp.design_id
            JOIN colors c ON c.id        = sp.color_id
            WHERE sp.set_num = ?
            ORDER BY sp.design_id, sp.color_id
            """,
            (set_num,),
        ).fetchall()

    out: List[Dict] = []
    for r in rows:
        d = dict(r)
        d["hex"] = r["hex"]
        if not d.get("part_url"):
            d["part_url"] = f"https://rebrickable.com/parts/{d['design_id']}/"
        if not d.get("part_img_url"):
            d["part_img_url"] = "https://rebrickable.com/static/img/nil.png"
        out.append(d)
    return out


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
    if status != 'loose':
        # Inventory table is now for loose parts only; ignore non-loose inserts
        return
    with _connect() as conn:
        # Prefer relational container_id when we have both drawer/container text present
        # This keeps legacy callers working while transitioning to the new model.
        container_id: Optional[int] = None
        if drawer and container:
            # resolve or create
            row = conn.execute("SELECT id FROM drawers WHERE name = ?", (drawer.strip(),)).fetchone()
            if row:
                d_id = row["id"]
            else:
                d_id = conn.execute(
                    "INSERT INTO drawers(name) VALUES (?)",
                    (drawer.strip(),),
                ).lastrowid
            row = conn.execute(
                "SELECT id FROM containers WHERE drawer_id = ? AND name = ?",
                (d_id, container.strip()),
            ).fetchone()
            if row:
                container_id = row["id"]
            else:
                container_id = conn.execute(
                    "INSERT INTO containers(drawer_id, name) VALUES (?, ?)",
                    (d_id, container.strip()),
                ).lastrowid

        conn.execute(
            """
            INSERT INTO inventory
            (design_id,color_id,quantity,status,drawer,container,set_number,container_id)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                design_id,
                color_id,
                quantity,
                status,
                drawer,
                container,
                None,  # set_number not used for loose-only inventory
                container_id,
            ),
        )
        conn.commit()

def loose_inventory_for_part(design_id: str) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.name AS color_name, c.hex,
                   i.color_id, i.quantity,
                   i.drawer, i.container
            FROM inventory i
            JOIN colors c ON c.id = i.color_id
            WHERE i.design_id = ? AND i.status = 'loose'
            ORDER BY i.drawer, i.container, i.color_id
            """,
            (design_id,),
        ).fetchall()
    return [dict(r) for r in rows]


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
    with _connect() as conn:
        # New-path rows: inventory linked to containers/drawers
        new_rows = conn.execute(
            """
            SELECT d.name AS drawer, c.name AS container,
                   p.design_id, p.name,
                   col.name AS color_name, col.hex,
                   SUM(i.quantity) AS qty
            FROM inventory i
            JOIN containers c ON c.id = i.container_id
            JOIN drawers    d ON d.id = c.drawer_id
            JOIN parts      p ON p.design_id = i.design_id
            JOIN colors     col ON col.id = i.color_id
            WHERE i.status = 'loose' AND i.container_id IS NOT NULL
            GROUP BY d.name, c.name, p.design_id, i.color_id
            """
        ).fetchall()

        # Legacy-path rows: no container_id yet, use text columns
        legacy_rows = conn.execute(
            """
            SELECT i.drawer AS drawer, i.container AS container,
                   p.design_id, p.name,
                   col.name AS color_name, col.hex,
                   SUM(i.quantity) AS qty
            FROM inventory i
            JOIN parts  p  ON p.design_id = i.design_id
            JOIN colors col ON col.id     = i.color_id
            WHERE i.status = 'loose' AND i.container_id IS NULL
            GROUP BY i.drawer, i.container, p.design_id, i.color_id
            """
        ).fetchall()

    rows = list(new_rows) + list(legacy_rows)
    tree: Dict[Tuple[str, str], List[Dict]] = {}
    for r in rows:
        key = (r["drawer"], r["container"])  # type: ignore[index]
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

def totals() -> Dict[str, int]:
    """Return total counts: loose_total, set_total, overall_total."""
    with _connect() as conn:
        loose_row = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) AS q FROM inventory WHERE status='loose'"
        ).fetchone()
        set_row = conn.execute(
            """
            SELECT COALESCE(SUM(sp.quantity), 0) AS q
            FROM set_parts sp
            JOIN sets s ON s.set_num = sp.set_num
            WHERE s.status IN ('built','wip','in_box','teardown')
            """
        ).fetchone()
    loose_total = loose_row["q"] if loose_row else 0
    set_total = set_row["q"] if set_row else 0
    return {"loose_total": loose_total, "set_total": set_total, "overall_total": loose_total + set_total}

# --------------------------------------------------------------------------- main
import sys

# --------------------------------------------------------------------------- collapse Really Useful Boxes
def collapse_really_useful_boxes(apply_changes=False):
    """
    For each 'Really Useful Box' drawer (kind != 'rub_box_legacy'), create a new drawer per container,
    with a single container 'All' in each, and move all inventory to the new container if apply_changes.
    """
    with _connect() as conn:
        # 1. Find all relevant drawers
        drawers = conn.execute(
            "SELECT id, name, kind FROM drawers WHERE name LIKE 'Really Useful Box %' AND kind IS NULL"
        ).fetchall()
        if not drawers:
            print("No 'Really Useful Box' drawers found (excluding legacy).")
            return
        for drawer in drawers:
            drawer_id = drawer["id"]
            drawer_name = drawer["name"]
            print(f"\nDrawer: {drawer_name} (id={drawer_id})")
            containers = conn.execute(
                "SELECT id, name FROM containers WHERE drawer_id = ? ORDER BY id",
                (drawer_id,),
            ).fetchall()
            if not containers:
                print("  No containers found.")
                continue
            for idx, container in enumerate(containers, 1):
                container_id = container["id"]
                container_name = container["name"]
                new_drawer_name = f"{drawer_name} #{idx} - {container_name}"
                # Create or get the new drawer
                new_drawer_row = conn.execute(
                    "SELECT id FROM drawers WHERE name = ?",
                    (new_drawer_name,),
                ).fetchone()
                if new_drawer_row:
                    new_drawer_id = new_drawer_row["id"]
                else:
                    cur = conn.execute(
                        "INSERT INTO drawers(name, kind) VALUES (?, ?)",
                        (new_drawer_name, "rub_box_split"),
                    )
                    new_drawer_id = cur.lastrowid
                # Create or get the "All" container in new drawer
                all_container_row = conn.execute(
                    "SELECT id FROM containers WHERE drawer_id = ? AND name = ?",
                    (new_drawer_id, "All"),
                ).fetchone()
                if all_container_row:
                    all_container_id = all_container_row["id"]
                else:
                    cur2 = conn.execute(
                        "INSERT INTO containers(drawer_id, name) VALUES (?, ?)",
                        (new_drawer_id, "All"),
                    )
                    all_container_id = cur2.lastrowid
                # Count inventory for this container
                inv_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM inventory WHERE container_id = ?",
                    (container_id,),
                ).fetchone()["c"]
                plan_msg = f"  Container '{container_name}' (id={container_id}): {inv_count} items → '{new_drawer_name}' / 'All'"
                if apply_changes:
                    # Update inventory to new container
                    conn.execute(
                        "UPDATE inventory SET container_id = ? WHERE container_id = ?",
                        (all_container_id, container_id),
                    )
                    print(plan_msg + " [UPDATED]")
                else:
                    print(plan_msg)
            if apply_changes:
                # Mark original drawer as legacy
                conn.execute(
                    "UPDATE drawers SET kind = 'rub_box_legacy' WHERE id = ?",
                    (drawer_id,),
                )
        if apply_changes:
            conn.commit()
            print("\nAll changes applied.")
        else:
            print("\nDry run complete. Re-run with 'apply' to make changes.")

def repair_really_useful_boxes():
    """
    Repair accidental nested split drawers created by re-running the collapse.
    Looks for drawers with kind='rub_box_split' whose name ends with " #<n> - All".
    Moves all their inventory into the corresponding first-level split drawer's
    'All' container and marks the nested drawer as kind='rub_box_nested_error'.
    Safe to run multiple times.
    """
    import re
    pattern = re.compile(r"^(.*) #\d+ - All$")
    with _connect() as conn:
        nested = conn.execute(
            "SELECT id, name FROM drawers WHERE kind = 'rub_box_split' AND name LIKE '% #%' || ' - All'"
        ).fetchall()
        if not nested:
            print("No nested RUB split drawers found.")
            return
        for row in nested:
            nid, nname = row["id"], row["name"]
            m = pattern.match(nname)
            if not m:
                print(f"Skipping unmatched name: {nname}")
                continue
            base_name = m.group(1)
            base = conn.execute(
                "SELECT id FROM drawers WHERE name = ? AND kind = 'rub_box_split'",
                (base_name,),
            ).fetchone()
            if not base:
                print(f"Base split drawer not found for nested '{nname}' → '{base_name}'")
                continue
            base_id = base["id"]
            all_row = conn.execute(
                "SELECT id FROM containers WHERE drawer_id = ? AND name = 'All'",
                (base_id,),
            ).fetchone()
            if all_row:
                all_id = all_row["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO containers(drawer_id, name) VALUES (?, 'All')",
                    (base_id,),
                )
                all_id = cur.lastrowid
            cont_ids = [r["id"] for r in conn.execute(
                "SELECT id FROM containers WHERE drawer_id = ?",
                (nid,),
            ).fetchall()]
            if cont_ids:
                placeholders = ",".join(["?"] * len(cont_ids))
                conn.execute(
                    f"UPDATE inventory SET container_id = ? WHERE container_id IN ({placeholders})",
                    (all_id, *cont_ids),
                )
            conn.execute(
                "UPDATE drawers SET kind = 'rub_box_nested_error' WHERE id = ?",
                (nid,),
            )
        conn.commit()
        print("Repair complete.")            


# --------------------------------------------------------------------------- normalize RUB box names
def normalize_rub_box_names(apply_changes=False):
    """
    Normalize names of rub_box_split drawers that ended with ' #<n> - All'.
    - If the normalized target name is free: rename the drawer.
    - If the target name already exists: MERGE by moving inventory to the target
      drawer's 'All' container and mark the source as 'rub_box_nested_error'.
    """
    import re
    pattern = re.compile(r"^(.*) #\d+ - All$")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name FROM drawers WHERE kind = 'rub_box_split' AND name LIKE '% #%' || ' - All'"
        ).fetchall()
        if not rows:
            print("No RUB box names needing normalization found.")
            return

        for row in rows:
            src_drawer_id, src_name = row["id"], row["name"]
            m = pattern.match(src_name)
            if not m:
                # shouldn't happen, but be safe
                continue
            target_name = m.group(1)

            # Is there already a drawer with the target name?
            existing = conn.execute(
                "SELECT id FROM drawers WHERE name = ?",
                (target_name,),
            ).fetchone()

            if existing:
                # MERGE path
                target_drawer_id = existing["id"]
                if apply_changes:
                    # Ensure 'All' exists in target
                    all_row = conn.execute(
                        "SELECT id FROM containers WHERE drawer_id = ? AND name = 'All'",
                        (target_drawer_id,),
                    ).fetchone()
                    if all_row:
                        all_id = all_row["id"]
                    else:
                        cur = conn.execute(
                            "INSERT INTO containers(drawer_id, name) VALUES (?, 'All')",
                            (target_drawer_id,),
                        )
                        all_id = cur.lastrowid

                    # Move all inventory from ALL containers in the source drawer to target 'All'
                    cont_ids = [r["id"] for r in conn.execute(
                        "SELECT id FROM containers WHERE drawer_id = ?",
                        (src_drawer_id,),
                    ).fetchall()]
                    if cont_ids:
                        placeholders = ",".join(["?"] * len(cont_ids))
                        conn.execute(
                            f"UPDATE inventory SET container_id = ? WHERE container_id IN ({placeholders})",
                            (all_id, *cont_ids),
                        )

                    # Mark the source drawer so it hides
                    conn.execute(
                        "UPDATE drawers SET kind = 'rub_box_nested_error' WHERE id = ?",
                        (src_drawer_id,),
                    )
                    print(f"Merged: '{src_name}' → existing '{target_name}' (moved inventory, marked source hidden)")
                else:
                    print(f"Would merge: '{src_name}' → existing '{target_name}'")
                continue

            # RENAME path
            if apply_changes:
                conn.execute(
                    "UPDATE drawers SET name = ? WHERE id = ?",
                    (target_name, src_drawer_id)
                )
                print(f"Renamed: '{src_name}' → '{target_name}'")
            else:
                print(f"Would rename: '{src_name}' → '{target_name}'")

        if apply_changes:
            conn.commit()
            print("Normalization complete.")

if __name__ == "__main__":
    if "--collapse-rub" in sys.argv:
        apply = "apply" in sys.argv
        collapse_really_useful_boxes(apply_changes=apply)
        sys.exit(0)
    if "--repair-rub" in sys.argv:
        repair_really_useful_boxes()
        sys.exit(0)
    if "--normalize-rub-names" in sys.argv:
        apply_flag = len(sys.argv) > 2 and sys.argv[2] == "apply"
        normalize_rub_box_names(apply_changes=apply_flag)
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        init_db()
        migrate_locations_to_containers()
        print("Database schema created and backfill complete.")
    else:
        init_db()
        print("Database schema created.")