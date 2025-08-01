#!/usr/bin/env python3
"""
Load BrickLink→Rebrickable mappings from a CSV produced from the Excel sheet.

Usage:
    python3 src/import_part_mapping.py data/bricklink_to_rebrickable.csv
"""
from __future__ import annotations
import csv, sys, sqlite3, pathlib

DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "lego_inventory.db"

def migrate(conn: sqlite3.Connection, bl_id: str, rb_id: str, name: str | None):
    # 1) ensure canonical part row exists (use blank name if unknown)
    conn.execute(
        """
        INSERT INTO parts(design_id, name) VALUES (?, ?)
        ON CONFLICT(design_id) DO UPDATE SET name = excluded.name
        WHERE parts.name = 'Unknown part'
        """,
        (rb_id, name or "Unknown part"),
    )

    # 2) alias row
    conn.execute(
        "INSERT OR IGNORE INTO part_aliases(alias,design_id) VALUES (?,?)",
        (bl_id, rb_id),
    )

    # 3) relink inventory rows still using the BL id
    conn.execute(
        "UPDATE inventory SET design_id = ? WHERE design_id = ?",
        (rb_id, bl_id),
    )

    # 4) remove placeholder part if it was self-aliased
    conn.execute(
        "DELETE FROM parts WHERE design_id = ?",
        (bl_id,),
    )

def main(csv_path: str):
    with sqlite3.connect(DB_PATH) as conn, open(csv_path, newline="", encoding="utf-8-sig") as f:
        conn.execute("PRAGMA journal_mode=WAL;")
        reader = csv.DictReader(f)
        reader.fieldnames = [h.lstrip('\ufeff') for h in reader.fieldnames]
        total = fixed = 0
        for row in reader:
            total += 1
            bl_id, rb_id = row["bricklink_id"].strip(), row["rebrickable_id"].strip()
            name = row.get("name", "").strip() or None
            migrate(conn, bl_id, rb_id, name)
            fixed += 1
        conn.commit()
        print(f"Imported {fixed}/{total} mappings from {csv_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python src/import_mapping.py <mapping.csv>")
    main(sys.argv[1])