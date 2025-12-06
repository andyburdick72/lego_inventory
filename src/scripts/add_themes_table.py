"""Migration script to add themes table and update sets table to use theme_id."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import inventory_db
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.db.inventory_db import _connect


def migrate() -> None:
    """Add themes table and migrate sets.theme to sets.theme_id."""
    with _connect() as conn:
        c = conn.cursor()
        
        # Check if themes table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='themes'")
        if not c.fetchone():
            print("Creating themes table...")
            c.execute(
                """
                CREATE TABLE themes(
                    id   INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
                """
            )
        else:
            print("themes table already exists.")
        
        # Check if theme_id column exists in sets
        c.execute("PRAGMA table_info(sets)")
        columns = [row[1] for row in c.fetchall()]
        
        if "theme_id" not in columns:
            print("Adding theme_id column to sets table...")
            c.execute(
                """
                ALTER TABLE sets
                ADD COLUMN theme_id INTEGER
                """
            )
            
            # Try to migrate existing theme data if it's numeric
            print("Attempting to migrate existing theme data...")
            c.execute(
                """
                UPDATE sets
                SET theme_id = CAST(theme AS INTEGER)
                WHERE theme IS NOT NULL AND theme != '' AND theme GLOB '[0-9]*'
                """
            )
            migrated = c.rowcount
            print(f"Migrated {migrated} sets with numeric theme values to theme_id.")
            print("Note: Foreign key constraint will be enforced on new inserts.")
        else:
            print("theme_id column already exists in sets table.")
        
        conn.commit()
        print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()

