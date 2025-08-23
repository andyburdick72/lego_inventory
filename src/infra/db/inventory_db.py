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

drawers
    id INTEGER PRIMARY KEY
    name TEXT NOT NULL UNIQUE
    description TEXT
    kind TEXT
    cols, rows INTEGER
    sort_index INTEGER
    created_at, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    deleted_at TEXT                – soft delete

containers
    id INTEGER PRIMARY KEY
    drawer_id INTEGER REFERENCES drawers(id) ON DELETE CASCADE
    name TEXT NOT NULL            – “label” in UI
    description TEXT
    row_index, col_index INTEGER
    sort_index INTEGER
    created_at, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    deleted_at TEXT                – soft delete
    UNIQUE(drawer_id, row_index, col_index)
    -- Soft-delete-aware uniqueness for labels:
    -- CREATE UNIQUE INDEX idx_containers_drawer_name_active
    --   ON containers(drawer_id, name) WHERE deleted_at IS NULL;

inventory
    id INTEGER PRIMARY KEY
    design_id TEXT  REFERENCES parts(design_id)
    color_id  INTEGER REFERENCES colors(id)
    quantity  INTEGER
    status    TEXT                  – loose / built / wip / in_box / teardown
    drawer    TEXT                  – loose only (legacy)
    container TEXT                  – loose only (legacy)
    set_number TEXT                 – built/WIP/In‑Box
    container_id INTEGER REFERENCES containers(id)   – canonical pointer

audit_log
    id INTEGER PRIMARY KEY
    entity TEXT, entity_id INTEGER
    action TEXT                    – create/update/soft_delete/restore/merge_move
    before_state TEXT (JSON), after_state TEXT (JSON)
    at TEXT DEFAULT CURRENT_TIMESTAMP
    user TEXT

Only stdlib; no external deps.
"""

from __future__ import annotations

import json
import sqlite3

from app.settings import get_settings
from infra.db.repositories import ColorsRepo, DrawersRepo, InventoryRepo, PartsRepo, SetsRepo


# Helper to safely get lastrowid with static type checkers
def _lastrowid(cur: sqlite3.Cursor) -> int:
    """Return a non-None lastrowid or raise at runtime; helps static type checkers."""
    rid = cur.lastrowid
    if rid is None:
        raise RuntimeError("Expected lastrowid after INSERT.")
    return int(rid)


# Centralized DB path from settings (allows .env overrides)
DB_PATH = get_settings().db_path


# --------------------------------------------------------------------------- helpers
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    # Apply robust defaults on every connection
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# --------------------------------------------------------------------------- internal audit helper + errors


def _audit(
    conn: sqlite3.Connection,
    entity: str,
    entity_id: int,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    user: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log(entity, entity_id, action, before_state, after_state, user)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            entity,
            entity_id,
            action,
            json.dumps(before) if before is not None else None,
            json.dumps(after) if after is not None else None,
            user,
        ),
    )


class InventoryConstraintError(Exception):
    pass


class DuplicateLabelError(Exception):
    pass


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

            CREATE TABLE IF NOT EXISTS drawers(
                id          INTEGER PRIMARY KEY,
                name        TEXT NOT NULL UNIQUE,
                description TEXT,
                kind        TEXT,
                cols        INTEGER,
                rows        INTEGER,
                sort_index  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                deleted_at  TEXT
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
                deleted_at  TEXT,
                UNIQUE(drawer_id, row_index, col_index)
            );

            CREATE TABLE IF NOT EXISTS inventory(
                id         INTEGER PRIMARY KEY,
                design_id  TEXT    REFERENCES parts(design_id),
                color_id   INTEGER REFERENCES colors(id),
                quantity   INTEGER,
                status     TEXT,
                drawer     TEXT,
                container  TEXT,
                set_number TEXT,
                container_id INTEGER REFERENCES containers(id)
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

            CREATE INDEX IF NOT EXISTS idx_containers_drawer ON containers(drawer_id);
            CREATE INDEX IF NOT EXISTS idx_drawers_name      ON drawers(name);

            -- Simple audit log for drawer/container changes
            CREATE TABLE IF NOT EXISTS audit_log (
              id           INTEGER PRIMARY KEY,
              entity       TEXT NOT NULL,   -- 'drawer' | 'container'
              entity_id    INTEGER NOT NULL,
              action       TEXT NOT NULL,   -- 'create' | 'update' | 'soft_delete' | 'restore' | 'merge_move'
              before_state TEXT,            -- JSON
              after_state  TEXT,            -- JSON
              at           TEXT DEFAULT CURRENT_TIMESTAMP,
              user         TEXT
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
        try:
            conn.execute(
                "ALTER TABLE inventory ADD COLUMN container_id INTEGER REFERENCES containers(id)"
            )
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
        try:
            conn.execute("ALTER TABLE drawers ADD COLUMN deleted_at TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE containers ADD COLUMN deleted_at TEXT")
        except sqlite3.OperationalError:
            pass
        # Create soft-delete-aware index and active-only views once columns exist
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_containers_drawer_name_active
              ON containers(drawer_id, name)
              WHERE deleted_at IS NULL
            """
        )
        conn.execute(
            """
            CREATE VIEW IF NOT EXISTS active_drawers AS
              SELECT * FROM drawers WHERE deleted_at IS NULL
            """
        )
        conn.execute(
            """
            CREATE VIEW IF NOT EXISTS active_containers AS
              SELECT * FROM containers WHERE deleted_at IS NULL
            """
        )
        conn.commit()


# === Drawer/Container CRUD helpers (DB-only layer) ===


def create_drawer(conn, name, description=None, kind=None, cols=None, rows=None, sort_index=0):
    cur = conn.execute(
        """
        INSERT INTO drawers (name, description, kind, cols, rows, sort_index)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, description, kind, cols, rows, sort_index),
    )
    did = _lastrowid(cur)
    after = conn.execute("SELECT * FROM drawers WHERE id=?", (did,)).fetchone()
    _audit(conn, "drawer", did, "create", None, dict(after))
    conn.commit()
    return did


def update_drawer(conn, drawer_id, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    values.append(drawer_id)
    before = conn.execute("SELECT * FROM drawers WHERE id=?", (drawer_id,)).fetchone()
    conn.execute(
        f"UPDATE drawers SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values
    )
    after = conn.execute("SELECT * FROM drawers WHERE id=?", (drawer_id,)).fetchone()
    _audit(
        conn,
        "drawer",
        drawer_id,
        "update",
        dict(before) if before else None,
        dict(after) if after else None,
    )
    conn.commit()


def soft_delete_drawer(conn, drawer_id):
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM containers WHERE drawer_id=? AND deleted_at IS NULL",
        (drawer_id,),
    ).fetchone()
    if row and row["c"] > 0:
        raise InventoryConstraintError("Drawer has active containers; move or delete them first.")
    before = conn.execute("SELECT * FROM drawers WHERE id=?", (drawer_id,)).fetchone()
    conn.execute(
        "UPDATE drawers SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (drawer_id,),
    )
    after = conn.execute("SELECT * FROM drawers WHERE id=?", (drawer_id,)).fetchone()
    _audit(
        conn,
        "drawer",
        drawer_id,
        "soft_delete",
        dict(before) if before else None,
        dict(after) if after else None,
    )
    conn.commit()


def restore_drawer(conn, drawer_id):
    before = conn.execute("SELECT * FROM drawers WHERE id=?", (drawer_id,)).fetchone()
    conn.execute("UPDATE drawers SET deleted_at = NULL WHERE id = ?", (drawer_id,))
    after = conn.execute("SELECT * FROM drawers WHERE id=?", (drawer_id,)).fetchone()
    _audit(
        conn,
        "drawer",
        drawer_id,
        "restore",
        dict(before) if before else None,
        dict(after) if after else None,
    )
    conn.commit()


def _container_duplicate_exists(
    conn: sqlite3.Connection, drawer_id: int, name: str, exclude_id: int | None = None
) -> bool:
    rows = conn.execute(
        "SELECT id FROM containers WHERE drawer_id=? AND name=? AND deleted_at IS NULL",
        (drawer_id, name.strip()),
    ).fetchall()
    return any(r["id"] != exclude_id for r in rows)


def create_container(
    conn, drawer_id, name, description=None, row_index=None, col_index=None, sort_index=0
):
    name = name.strip()
    if _container_duplicate_exists(conn, drawer_id, name):
        raise DuplicateLabelError("Duplicate label in this drawer")
    cur = conn.execute(
        """
        INSERT INTO containers (drawer_id, name, description, row_index, col_index, sort_index)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (drawer_id, name, description, row_index, col_index, sort_index),
    )
    cid = _lastrowid(cur)
    after = conn.execute("SELECT * FROM containers WHERE id=?", (cid,)).fetchone()
    _audit(conn, "container", cid, "create", None, dict(after))
    conn.commit()
    return cid


def update_container(conn, container_id, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    values.append(container_id)
    before = conn.execute("SELECT * FROM containers WHERE id=?", (container_id,)).fetchone()
    if before is None:
        return
    # Determine target drawer/name for uniqueness check
    new_drawer = (
        fields.get("drawer_id", before["drawer_id"])
        if isinstance(before, sqlite3.Row)
        else fields.get("drawer_id")
    )
    new_name = (
        fields.get("name", before["name"])
        if isinstance(before, sqlite3.Row)
        else fields.get("name")
    )
    if isinstance(new_name, str):
        new_name = new_name.strip()
    if new_drawer is not None and new_name is not None:
        if _container_duplicate_exists(
            conn, int(new_drawer), str(new_name), exclude_id=container_id
        ):
            raise DuplicateLabelError("Duplicate label in this drawer")
    conn.execute(
        f"UPDATE containers SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values
    )
    after = conn.execute("SELECT * FROM containers WHERE id=?", (container_id,)).fetchone()
    _audit(conn, "container", container_id, "update", dict(before), dict(after) if after else None)
    conn.commit()


def soft_delete_container(conn, container_id):
    cnt = conn.execute(
        "SELECT COUNT(*) AS c FROM inventory WHERE container_id=?", (container_id,)
    ).fetchone()["c"]
    if cnt and cnt > 0:
        raise InventoryConstraintError("Container has inventory; merge/move required.")
    before = conn.execute("SELECT * FROM containers WHERE id=?", (container_id,)).fetchone()
    conn.execute(
        "UPDATE containers SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (container_id,),
    )
    after = conn.execute("SELECT * FROM containers WHERE id=?", (container_id,)).fetchone()
    _audit(
        conn,
        "container",
        container_id,
        "soft_delete",
        dict(before) if before else None,
        dict(after) if after else None,
    )
    conn.commit()


def restore_container(conn, container_id):
    before = conn.execute("SELECT * FROM containers WHERE id=?", (container_id,)).fetchone()
    conn.execute("UPDATE containers SET deleted_at = NULL WHERE id = ?", (container_id,))
    after = conn.execute("SELECT * FROM containers WHERE id=?", (container_id,)).fetchone()
    _audit(
        conn,
        "container",
        container_id,
        "restore",
        dict(before) if before else None,
        dict(after) if after else None,
    )
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
    description: str | None = None,
    kind: str | None = None,
    cols: int | None = None,
    rows: int | None = None,
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
        return _lastrowid(cur)


def upsert_container(
    drawer_id: int,
    name: str,
    description: str | None = None,
    row_index: int | None = None,
    col_index: int | None = None,
) -> int:
    """Return the container id for (drawer_id, name), inserting if needed.
    Uses name for identity within a drawer (soft-delete-aware unique index enforces this).
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
        return _lastrowid(cur)


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
        return _lastrowid(cur)


def get_or_create_container_by_names(
    drawer_name: str,
    container_name: str,
    *,
    drawer_description: str | None = None,
    container_description: str | None = None,
) -> int:
    """Convenience: upsert a drawer by name, then upsert a container by name; return container_id."""
    d_id = upsert_drawer(drawer_name, drawer_description)
    c_id = upsert_container(d_id, container_name, container_description)
    return c_id


# --------------------------------------------------------------------------- drawer/container listing helpers (read-only UI)


def list_drawers() -> list[dict]:
    """Return all drawers with container and piece counts."""
    with _connect() as conn:
        repo = DrawersRepo(conn)
        rows = repo.list_drawers_with_counts()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def get_drawer(drawer_id: int) -> dict | None:
    """Return a single drawer row by id, or None."""
    with _connect() as conn:
        repo = DrawersRepo(conn)
        r = repo.get_drawer_active(drawer_id)
    return dict(r) if (r is not None and not isinstance(r, dict)) else r


def list_containers_for_drawer(drawer_id: int) -> list[dict]:
    """Return containers for a drawer with counts and optional positions."""
    with _connect() as conn:
        repo = DrawersRepo(conn)
        rows = repo.list_containers_with_counts(drawer_id)
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def get_container(container_id: int) -> dict | None:
    """Return a single container row with its drawer name, or None."""
    with _connect() as conn:
        repo = DrawersRepo(conn)
        r = repo.get_container_with_drawer(container_id)
    return dict(r) if (r is not None and not isinstance(r, dict)) else r


def list_parts_in_container(container_id: int) -> list[dict]:
    """List aggregated parts (by design_id + color) within a container."""
    with _connect() as conn:
        repo = DrawersRepo(conn)
        rows = repo.list_aggregated_parts_in_container(container_id)
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


# --------------------------------------------------------------------------- inventory (read-only repo delegations)
def iter_loose_parts(filters: dict | None = None):
    """Yield loose parts honoring optional filters. See InventoryRepo.iter_loose_parts for supported keys."""
    with _connect() as conn:
        repo = InventoryRepo(conn)
        for r in repo.iter_loose_parts(filters or {}):
            yield dict(r) if not isinstance(r, dict) else r


def storage_location_counts(filters: dict | None = None) -> list[dict]:
    """Aggregate loose inventory by drawer/container."""
    with _connect() as conn:
        repo = InventoryRepo(conn)
        rows = repo.storage_location_counts(filters or {})
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


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


def resolve_color(bl_id: int) -> int | None:
    with _connect() as conn:
        repo = ColorsRepo(conn)
        return repo.resolve_color_alias(bl_id)


# --------------------------------------------------------------------------- part helpers


def fetch_part_name(design_id: str) -> str | None:
    with _connect() as conn:
        repo = PartsRepo(conn)
        name = repo.fetch_part_name(design_id)
    return name


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


def unknown_parts() -> list[str]:
    with _connect() as conn:
        repo = PartsRepo(conn)
        rows = repo.unknown_parts()
    return [(r["design_id"] if not isinstance(r, dict) else r["design_id"]) for r in rows]


def add_part_alias(alias: str, design_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO part_aliases(alias,design_id) VALUES (?,?)",
            (alias, design_id),
        )
        conn.commit()


def resolve_part(alias: str) -> str | None:
    with _connect() as conn:
        repo = PartsRepo(conn)
        row = repo.resolve_part_alias(alias)
    if not row:
        return None
    if isinstance(row, dict):
        return row.get("design_id")
    return row["design_id"]


def get_part(design_id: str) -> dict | None:
    with _connect() as conn:
        repo = PartsRepo(conn)
        row = repo.get_part(design_id)
    return dict(row) if (row is not None and not isinstance(row, dict)) else row


# --------------------------------------------------------------------------- set_parts
def insert_set_part(
    set_num: str,
    design_id: str,
    color_id: int,
    quantity: int,
    conn: sqlite3.Connection | None = None,
) -> None:
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


def get_set_parts(set_num: str) -> list[dict]:
    with _connect() as conn:
        repo = SetsRepo(conn)
        rows = repo.get_set_parts_basic(set_num)
    # Preserve legacy shape: only include the original keys (set_num, design_id, name, color_id, color_name, quantity)
    out: list[dict] = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else dict(r)
        out.append(
            {
                "set_num": d.get("set_num"),
                "design_id": d.get("design_id"),
                "name": d.get("name"),
                "color_id": d.get("color_id"),
                "color_name": d.get("color_name"),
                "quantity": d.get("quantity"),
            }
        )
    return out


def sets_for_part(design_id: str) -> list[dict]:
    with _connect() as conn:
        repo = SetsRepo(conn)
        rows = repo.sets_for_part_with_colors(design_id)
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


# --------------------------------------------------------------------------- sets helpers


def get_set(set_num: str) -> dict | None:
    """Return a single set row by set_num or None if not found."""
    with _connect() as conn:
        repo = SetsRepo(conn)
        row = repo.get_set_by_num(set_num)
    return dict(row) if (row is not None and not isinstance(row, dict)) else row


def get_parts_for_set(set_num: str) -> list[dict]:
    """Return the list of parts for a set with color, qty, and Rebrickable URLs.
    Falls back to canonical URL/placeholder image when metadata is missing.
    """
    with _connect() as conn:
        repo = SetsRepo(conn)
        rows = repo.list_parts_for_set(set_num)

    out: list[dict] = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else dict(r)
        # ensure hex is present explicitly (your code uses it in the dict)
        d["hex"] = d.get("hex")
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
    drawer: str | None = None,
    container: str | None = None,
    set_number: str | None = None,
) -> None:
    if status != "loose":
        # Inventory table is now for loose parts only; ignore non-loose inserts
        return
    with _connect() as conn:
        # Prefer relational container_id when we have both drawer/container text present
        # This keeps legacy callers working while transitioning to the new model.
        container_id: int | None = None
        if drawer and container:
            # resolve or create
            row = conn.execute(
                "SELECT id FROM drawers WHERE name = ?", (drawer.strip(),)
            ).fetchone()
            if row:
                d_id = row["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO drawers(name) VALUES (?)",
                    (drawer.strip(),),
                )
                d_id = _lastrowid(cur)
            row = conn.execute(
                "SELECT id FROM containers WHERE drawer_id = ? AND name = ?",
                (d_id, container.strip()),
            ).fetchone()
            if row:
                container_id = row["id"]
            else:
                cur2 = conn.execute(
                    "INSERT INTO containers(drawer_id, name) VALUES (?, ?)",
                    (d_id, container.strip()),
                )
                container_id = _lastrowid(cur2)

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


def loose_inventory_for_part(design_id: str) -> list[dict]:
    with _connect() as conn:
        repo = InventoryRepo(conn)
        rows = repo.loose_inventory_for_part(design_id)
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


# --------------------------------------------------------------------------- queries
def parts_with_totals() -> list[dict]:
    with _connect() as conn:
        repo = InventoryRepo(conn)
        rows = repo.parts_with_totals()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def inventory_by_part(design_id: str) -> list[dict]:
    with _connect() as conn:
        repo = InventoryRepo(conn)
        rows = repo.inventory_by_part(design_id)
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def locations_map() -> dict[tuple[str, str], list[dict]]:
    with _connect() as conn:
        repo = InventoryRepo(conn)
        new_rows = repo.locations_rows_new()
        legacy_rows = repo.locations_rows_legacy()

    rows = list(new_rows) + list(legacy_rows)
    tree: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r["drawer"], r["container"])  # type: ignore[index]
        tree.setdefault(key, []).append(dict(r) if not isinstance(r, dict) else dict(r))
    return tree


def search_parts(query: str) -> list[dict]:
    with _connect() as conn:
        repo = InventoryRepo(conn)
        rows = repo.search_parts(query)
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def totals() -> dict[str, int]:
    """Return total counts: loose_total, set_total, overall_total."""
    with _connect() as conn:
        inv_repo = InventoryRepo(conn)
        set_repo = SetsRepo(conn)
        loose_total = inv_repo.loose_total()
        set_total = set_repo.set_total_for_statuses(["built", "wip", "in_box", "teardown"])
    return {
        "loose_total": loose_total,
        "set_total": set_total,
        "overall_total": loose_total + set_total,
    }


# --------------------------------------------------------------------------- main
import sys  # noqa: E402


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
                    new_drawer_id = _lastrowid(cur)
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
                    all_container_id = _lastrowid(cur2)
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
                all_id = _lastrowid(cur)
            cont_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM containers WHERE drawer_id = ?",
                    (nid,),
                ).fetchall()
            ]
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
                        all_id = _lastrowid(cur)

                    # Move all inventory from ALL containers in the source drawer to target 'All'
                    cont_ids = [
                        r["id"]
                        for r in conn.execute(
                            "SELECT id FROM containers WHERE drawer_id = ?",
                            (src_drawer_id,),
                        ).fetchall()
                    ]
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
                    print(
                        f"Merged: '{src_name}' → existing '{target_name}' (moved inventory, marked source hidden)"
                    )
                else:
                    print(f"Would merge: '{src_name}' → existing '{target_name}'")
                continue

            # RENAME path
            if apply_changes:
                conn.execute(
                    "UPDATE drawers SET name = ? WHERE id = ?", (target_name, src_drawer_id)
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
