"""Migration script to add part_category_id column to parts table."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import inventory_db
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.db.inventory_db import _connect


def migrate() -> None:
    """Add part_category_id column to parts table."""
    with _connect() as conn:
        c = conn.cursor()
        
        # Check if part_category_id column exists
        c.execute("PRAGMA table_info(parts)")
        columns = [row[1] for row in c.fetchall()]
        
        if "part_category_id" not in columns:
            print("Adding part_category_id column to parts table...")
            c.execute(
                """
                ALTER TABLE parts
                ADD COLUMN part_category_id INTEGER
                """
            )
            print("Migration completed successfully!")
        else:
            print("part_category_id column already exists in parts table.")


if __name__ == "__main__":
    migrate()

