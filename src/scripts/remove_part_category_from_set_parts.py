"""Migration script to remove part_category_id column from set_parts table."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import inventory_db
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.db.inventory_db import _connect


def migrate() -> None:
    """Remove part_category_id column from set_parts table."""
    with _connect() as conn:
        c = conn.cursor()
        
        # Check if part_category_id column exists
        c.execute("PRAGMA table_info(set_parts)")
        columns = [row[1] for row in c.fetchall()]
        
        if "part_category_id" in columns:
            print("Removing part_category_id column from set_parts table...")
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            c.execute("""
                CREATE TABLE IF NOT EXISTS set_parts_new(
                    set_num   TEXT,
                    design_id TEXT,
                    color_id  INTEGER,
                    quantity  INTEGER,
                    PRIMARY KEY (set_num, design_id, color_id),
                    FOREIGN KEY (design_id) REFERENCES parts(design_id),
                    FOREIGN KEY (color_id)  REFERENCES colors(id)
                )
            """)
            
            # Copy data (excluding part_category_id)
            c.execute("""
                INSERT INTO set_parts_new (set_num, design_id, color_id, quantity)
                SELECT set_num, design_id, color_id, quantity
                FROM set_parts
            """)
            
            # Drop old table and rename new one
            c.execute("DROP TABLE set_parts")
            c.execute("ALTER TABLE set_parts_new RENAME TO set_parts")
            
            # Recreate indexes
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_set_parts_set_num ON set_parts(set_num)
            """)
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_set_parts_design_id ON set_parts(design_id)
            """)
            
            conn.commit()
            print("Migration completed successfully!")
        else:
            print("part_category_id column does not exist in set_parts table.")


if __name__ == "__main__":
    migrate()

