"""
resolve_missing_parts.py
------------------------

Scan placeholder BrickLink part records (inserted when the Instabrick XML
contained an ITEMID Rebrickable does not recognise) and attempt to map
them to canonical Rebrickable design_ids.

A placeholder is detected as an alias row whose alias_id == design_id
(a self‑alias). Those design_ids are not valid Rebrickable IDs; if they
were, the live loader would already have created an alias → design_id
row pointing elsewhere.

Workflow per batch (≤50 aliases to stay under rate‑limit):

1. Query Rebrickable via ``bulk_parts_by_bricklink``.
2. For each mapping returned:
   * ensure the Rebrickable part exists in **parts**,
   * insert (alias → design_id) into **part_aliases**,
   * relink **inventory** rows,
   * delete the placeholder part and its self‑alias.
3. Commit and report progress.

Run::

    python src/resolve_missing_parts.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

import inventory_db as db
from utils.rebrickable_api import (
    bulk_parts_by_bricklink,
    load_rebrickable_environment,
)

MAX_BATCH = 50

# --------------------------------------------------------------------------- helpers
def get_placeholders(conn: sqlite3.Connection) -> List[str]:
    """Return BrickLink alias IDs that currently point to themselves."""
    rows = conn.execute(
        "SELECT alias_id FROM part_aliases WHERE alias_id = design_id"
    ).fetchall()
    return [row[0] for row in rows]


def reconcile_batch(conn: sqlite3.Connection, aliases: List[str]) -> int:
    """Resolve a batch; return how many aliases were fixed."""
    remote = bulk_parts_by_bricklink(aliases)
    fixed = 0

    for alias, (rb_id, name) in remote.items():
        # 1) canonical part
        db.insert_part(rb_id, name)

        # 2) alias row
        db.add_part_alias(alias, rb_id)

        # 3) relink inventory
        conn.execute(
            "UPDATE inventory SET design_id = ? WHERE design_id = ?",
            (rb_id, alias),
        )

        # 4) remove placeholder
        conn.execute("DELETE FROM parts WHERE design_id = ?", (alias,))
        conn.execute(
            "DELETE FROM part_aliases WHERE alias_id = ? AND design_id = ?",
            (alias, alias),
        )

        fixed += 1

    conn.commit()
    return fixed


# --------------------------------------------------------------------------- main
def main() -> None:
    load_rebrickable_environment()  # ensure API key is loaded

    db_path = Path(__file__).resolve().parents[1] / "data" / "lego_inventory.db"
    with sqlite3.connect(db_path) as conn:
        placeholders = get_placeholders(conn)
        total = len(placeholders)

        if not total:
            print("No BrickLink placeholder parts to reconcile — database is already clean.")
            return

        print(f"Found {total} placeholder part IDs to reconcile …")
        fixed = 0
        for i in range(0, total, MAX_BATCH):
            chunk = placeholders[i : i + MAX_BATCH]
            fixed += reconcile_batch(conn, chunk)
            print(f"  … {min(i + MAX_BATCH, total)}/{total} processed")

        print(f"Reconciliation complete: {fixed}/{total} aliases resolved.")


if __name__ == "__main__":
    main()