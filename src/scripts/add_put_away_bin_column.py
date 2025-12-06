"""Migration script to add is_put_away_bin column to containers table."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import inventory_db
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.db.inventory_db import _connect


def migrate() -> None:
    """Add is_put_away_bin column to containers table if it doesn't exist."""
    with _connect() as conn:
        c = conn.cursor()
        
        # Check if column already exists
        c.execute("PRAGMA table_info(containers)")
        columns = [row[1] for row in c.fetchall()]
        
        if "is_put_away_bin" in columns:
            print("Column is_put_away_bin already exists. Skipping migration.")
            return
        
        # Add the column
        print("Adding is_put_away_bin column to containers table...")
        c.execute(
            """
            ALTER TABLE containers
            ADD COLUMN is_put_away_bin INTEGER DEFAULT 0
            """
        )
        conn.commit()
        
        # Set existing drawer 53, container 278 as put away bin if it exists
        c.execute(
            """
            UPDATE containers
            SET is_put_away_bin = 1
            WHERE drawer_id = 53 AND id = 278 AND deleted_at IS NULL
            """
        )
        conn.commit()
        
        print("Migration completed successfully!")
        print("Note: If drawer 53 / container 278 exists, it has been set as the put away bin.")


if __name__ == "__main__":
    migrate()

