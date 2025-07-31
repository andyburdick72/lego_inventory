"""
clean_instabrick_inventory.py
-----------------------------

Load and clean an Instabrick XML inventory:
 1. Reconcile placeholder aliases via bulk BrickLink → Rebrickable mapping
 2. Numeric-only alias reconciliation
 3. Name filling for resolved parts
 4. Fallback search for any remaining unknown part codes

Usage:
    python src/clean_instabrick_inventory.py [--mapping path/to/csv]
"""
from __future__ import annotations

import sqlite3
import time
import sys
from pathlib import Path
from typing import List, Dict
import re

from utils.rebrickable_api import bulk_parts_by_bricklink, get_json
from utils.common_functions import load_rebrickable_environment

MAX_BATCH = 50

# --------------------------------------------------------------------------- helpers

def get_placeholders(conn: sqlite3.Connection) -> List[str]:
    """Return BrickLink alias IDs that currently point to themselves."""
    rows = conn.execute(
        "SELECT alias FROM part_aliases WHERE alias = design_id"
    ).fetchall()
    return [row[0] for row in rows]


def _looks_like_bricklink_id(pid: str) -> bool:
    """Return True if *pid* is all-digits or digits + single suffix."""
    return bool(re.fullmatch(r"\d+[a-z]?", pid, re.IGNORECASE))


def reconcile_batch(conn: sqlite3.Connection, aliases: List[str]) -> int:
    """Resolve a batch; return number of aliases fixed via BrickLink API."""
    remote = bulk_parts_by_bricklink(aliases)
    fixed = 0
    for alias, (rb_id, name) in remote.items():
        # ensure canonical part exists
        conn.execute(
            "INSERT OR IGNORE INTO parts(design_id,name) VALUES (?,?)",
            (rb_id, name),
        )
        # insert alias mapping
        conn.execute(
            "INSERT OR IGNORE INTO part_aliases(alias,design_id) VALUES (?,?)",
            (alias, rb_id),
        )
        # move inventory
        conn.execute(
            "UPDATE inventory SET design_id = ? WHERE design_id = ?",
            (rb_id, alias),
        )
        # clean up placeholder
        conn.execute("DELETE FROM parts WHERE design_id = ?", (alias,))
        conn.execute(
            "DELETE FROM part_aliases WHERE alias = ? AND design_id = ?",
            (alias, alias),
        )
        fixed += 1
    conn.commit()
    return fixed


def reconcile_numeric_unknowns(conn: sqlite3.Connection, design_ids: List[str]) -> int:
    """
    Attempt to treat numeric aliases as BrickLink IDs and map them.
    Returns how many aliases were resolved.
    """
    aliases = [pid for pid in design_ids if _looks_like_bricklink_id(pid)]
    total = len(aliases)
    fixed = 0
    for i in range(0, total, MAX_BATCH):
        chunk = aliases[i : i + MAX_BATCH]
        remote = bulk_parts_by_bricklink(chunk)
        for alias, (rb_id, name) in remote.items():
            conn.execute(
                "INSERT OR IGNORE INTO parts(design_id,name) VALUES (?,?)",
                (rb_id, name),
            )
            conn.execute(
                "INSERT OR IGNORE INTO part_aliases(alias,design_id) VALUES (?,?)",
                (alias, rb_id),
            )
            conn.execute(
                "UPDATE inventory SET design_id = ? WHERE design_id = ?",
                (rb_id, alias),
            )
            conn.execute("DELETE FROM parts WHERE design_id = ?", (alias,))
            fixed += 1
        conn.commit()
        print(f"  … numeric pass {min(i + MAX_BATCH, total)}/{total} processed")
    return fixed

# --------------------------------------------------------------------------- name-filling helpers

def get_unknown_design_ids(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT design_id FROM parts WHERE name = 'Unknown part'"
    ).fetchall()
    return [r[0] for r in rows]


def update_names_batch(conn: sqlite3.Connection, mapping: Dict[str, str]) -> int:
    """
    Overwrite Unknown part names using mapping {design_id: proper_name}.
    Returns number of rows changed.
    """
    changed = 0
    for pid, name in mapping.items():
        if not name:
            continue
        cur = conn.execute(
            """
            UPDATE parts
               SET name = ?
             WHERE design_id = ?
               AND name = 'Unknown part'
            """,
            (name, pid),
        )
        changed += cur.rowcount
    conn.commit()
    return changed

# --------------------------------------------------------------------------- main

def main() -> None:
    load_rebrickable_environment()
    db_path = Path(__file__).resolve().parents[1] / "data" / "lego_inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")

        # Phase 1: resolve placeholder aliases
        placeholders = get_placeholders(conn)
        total = len(placeholders)
        if total:
            print(f"Found {total} placeholder aliases…")
            fixed = 0
            for i in range(0, total, MAX_BATCH):
                chunk = placeholders[i : i + MAX_BATCH]
                fixed += reconcile_batch(conn, chunk)
                print(f"  … {min(i+MAX_BATCH,total)}/{total} processed")
            print(f"Reconciliation complete: {fixed}/{total} resolved.")
        else:
            print("No placeholder aliases to reconcile.")

        # Phase 1b: numeric-only reconciliation
        unknown_ids = get_unknown_design_ids(conn)
        num_fixed = reconcile_numeric_unknowns(conn, unknown_ids)
        if num_fixed:
            print(f"Numeric-ID reconciliation fixed {num_fixed} more.")

        # Phase 2: fill in names via bulk_parts_by_bricklink on design_ids
        unknown_ids = get_unknown_design_ids(conn)
        remaining = len(unknown_ids)
        if remaining:
            print(f"Filling names for {remaining} parts still 'Unknown part'…")
            filled = 0
            for i in range(0, remaining, MAX_BATCH):
                batch = unknown_ids[i : i + MAX_BATCH]
                mapping: Dict[str,str] = {}
                remote = bulk_parts_by_bricklink(batch)
                for alias, (rb_id, name) in remote.items():
                    mapping[alias] = name
                filled += update_names_batch(conn, mapping)
                print(f"  … {min(i+MAX_BATCH,remaining)}/{remaining} done")
            print(f"Bulk name fill complete: {filled}/{remaining}.")
        else:
            print("No 'Unknown part' rows remain.")

        # Phase 3: fallback search for any still unknown
        unknown_ids = get_unknown_design_ids(conn)
        total = len(unknown_ids)
        if total:
            print(f"Attempting fallback search for {total} parts…")
            resolved = 0
            for alias in unknown_ids:
                try:
                    data = get_json("/parts/", params={"search": alias})
                except Exception:
                    continue
                for p in data.get("results", []):
                    part_num = p.get("part_num")
                    if not part_num:
                        continue
                    ext_ids = [str(x) for x in p.get("external_ids", {}).get("BrickLink", [])]
                    if alias.lower() in [e.lower() for e in ext_ids] or part_num.lower().startswith(alias.lower()):
                        name = p.get("name", "")
                        # update mapping + inventory
                        conn.execute(
                            "INSERT OR IGNORE INTO parts(design_id,name) VALUES (?,?)",
                            (part_num, name),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO part_aliases(alias,design_id) VALUES (?,?)",
                            (alias, part_num),
                        )
                        conn.execute(
                            "UPDATE inventory SET design_id = ? WHERE design_id = ?",
                            (part_num, alias),
                        )
                        conn.execute("DELETE FROM parts WHERE design_id = ?", (alias,))
                        conn.commit()
                        resolved += 1
                        break
            print(f"Fallback search complete: {resolved}/{total} resolved.")
        else:
            print("All parts now have proper names.")

    print("Done.")

if __name__ == "__main__":
    main()