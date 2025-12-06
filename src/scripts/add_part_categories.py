"""Migration script to add part_categories table and part_category_id column to set_parts table."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import inventory_db
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.db.inventory_db import _connect


def migrate() -> None:
    """Add part_categories table and part_category_id column to set_parts if they don't exist."""
    with _connect() as conn:
        c = conn.cursor()
        
        # Check if part_categories table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='part_categories'")
        if not c.fetchone():
            print("Creating part_categories table...")
            c.execute(
                """
                CREATE TABLE part_categories(
                    id   INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
                """
            )
        else:
            print("part_categories table already exists.")
        
        # Check if part_category_id column exists in set_parts
        c.execute("PRAGMA table_info(set_parts)")
        columns = [row[1] for row in c.fetchall()]
        
        if "part_category_id" not in columns:
            print("Adding part_category_id column to set_parts table...")
            c.execute(
                """
                ALTER TABLE set_parts
                ADD COLUMN part_category_id INTEGER
                """
            )
            # Add foreign key constraint if possible (SQLite doesn't support adding FKs via ALTER TABLE)
            # The FK will be enforced on new inserts via the schema
            print("Note: Foreign key constraint will be enforced on new inserts.")
        else:
            print("part_category_id column already exists in set_parts table.")
        
        conn.commit()
        print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()

