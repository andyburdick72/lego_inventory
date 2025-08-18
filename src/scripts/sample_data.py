"""
Populate the SQLite database with sample LEGO inventory data.

This script uses the `infra.db.inventory_db` module to insert a handful of
parts and inventory records for testing the web interface.

It writes to the configured SQLite database (see `app.settings`). Depending on
your schema, re-running may produce duplicates for sample parts/inventory.

Usage:

    PYTHONPATH=src python3 -m scripts.sample_data
"""

from __future__ import annotations

from app.settings import get_settings
from infra.db import inventory_db as db

SETTINGS = get_settings()

# Use simple, non-conflicting Rebrickable color IDs for sample data.
# These are inserted if missing so the sample runs against a fresh DB.
RED = 1001
BLUE = 1002
GREEN = 1003
YELLOW = 1004
BLACK = 1005
WHITE = 1006
GRAY = 1007


def _ensure_sample_colors() -> None:
    # insert_color(rb_id: int, name: str, hex_code: str)
    # If your schema enforces uniqueness, these should be idempotent inserts in a fresh DB.
    try:
        db.insert_color(RED, "Red", "FF0000")
        db.insert_color(BLUE, "Blue", "0000FF")
        db.insert_color(GREEN, "Green", "00FF00")
        db.insert_color(YELLOW, "Yellow", "FFFF00")
        db.insert_color(BLACK, "Black", "000000")
        db.insert_color(WHITE, "White", "FFFFFF")
        db.insert_color(GRAY, "Gray", "808080")
    except Exception:
        # If colors already exist (e.g., rerun), ignore duplicate insert errors.
        pass


def main() -> None:
    db.init_db()
    _ensure_sample_colors()

    # Insert parts (design IDs), ignoring return values (insert_part does not need to be captured)
    db.insert_part("3001", "Brick 2 x 4")
    db.insert_part("3002", "Brick 2 x 3")
    db.insert_part("3003", "Brick 2 x 2")
    db.insert_part("3062", "Round Brick 1 x 1")

    # Insert inventory records using explicit color IDs and valid statuses
    db.insert_inventory("3001", RED, 50, "loose", container="A", drawer="1")
    db.insert_inventory("3001", BLUE, 20, "loose", container="A", drawer="2")
    db.insert_inventory("3002", GREEN, 15, "teardown")
    db.insert_inventory("3002", YELLOW, 30, "in_box")
    db.insert_inventory("3003", BLACK, 100, "built")
    db.insert_inventory("3062", WHITE, 10, "wip")  # work-in-progress → wip
    db.insert_inventory("3062", GRAY, 25, "loose", drawer="General")

    print("Sample data inserted.")


if __name__ == "__main__":
    main()
