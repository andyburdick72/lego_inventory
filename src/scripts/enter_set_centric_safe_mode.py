"""
Enter Set-Centric Safe Mode (optional, reversible).

This script:
- Creates a timestamped backup of the SQLite DB
- Deletes ONLY location/loose/storage-related rows (keeps sets/parts metadata intact)

It is intentionally conservative and only touches a small, explicit set of tables
that are known to be location-dependent in this codebase.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.settings import get_settings


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    if not row:
        return 0
    try:
        return int(row["n"])  # sqlite3.Row
    except Exception:
        return int(row[0])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enter set-centric safe mode by backing up the DB and clearing location-dependent rows."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to SQLite DB (defaults to APP_DB_PATH / data/lego_inventory.db).",
    )
    args = parser.parse_args()

    settings = get_settings()
    db_path = Path(args.db_path).expanduser() if args.db_path else settings.db_path
    db_path = db_path.resolve()

    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.safe_mode_backup.{ts}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)

    print(f"✅ Backup created: {backup_path}")

    # Location/loose/storage-related tables in this codebase (see src/infra/db/inventory_db.py).
    tables_to_clear = ["inventory", "containers", "drawers", "audit_log"]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        before = {t: _count(conn, t) for t in tables_to_clear}

        # Delete in FK-safe order.
        conn.execute("BEGIN")
        for t in ["inventory", "containers", "drawers", "audit_log"]:
            if _table_exists(conn, t):
                conn.execute(f"DELETE FROM {t}")
        conn.commit()

        after = {t: _count(conn, t) for t in tables_to_clear}

    print("✅ Cleared location-dependent rows:")
    for t in tables_to_clear:
        print(f"- {t}: {before[t]} -> {after[t]}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


