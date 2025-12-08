#!/usr/bin/env python3
"""
Migration script to set ignore_in_inventory flag for:
1. Sticker sheets (part_category_id = 327)
2. Specific parts: 902221, 902222
3. Parts with "sticker sheet" in name (legacy data)

Run this once to backfill existing data.
"""
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.db.inventory_db import _connect


def main():
    """Set ignore_in_inventory flag for sticker sheets and specific parts."""
    with _connect() as conn:
        cursor = conn.cursor()
        
        # Ensure the column exists (add it if it doesn't)
        try:
            cursor.execute("ALTER TABLE parts ADD COLUMN ignore_in_inventory INTEGER DEFAULT 0")
            print("Added ignore_in_inventory column to parts table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("Column ignore_in_inventory already exists")
            else:
                raise
        
        conn.commit()
        
        # Update parts by category ID (sticker sheets)
        cursor.execute(
            """
            UPDATE parts
            SET ignore_in_inventory = 1
            WHERE part_category_id = 327
              AND COALESCE(ignore_in_inventory, 0) = 0
            """
        )
        category_updated = cursor.rowcount
        print(f"Updated {category_updated} parts with category_id = 327 (sticker sheets)")
        
        # Update specific parts by design_id
        cursor.execute(
            """
            UPDATE parts
            SET ignore_in_inventory = 1
            WHERE design_id IN ('902221', '902222')
              AND COALESCE(ignore_in_inventory, 0) = 0
            """
        )
        specific_updated = cursor.rowcount
        print(f"Updated {specific_updated} specific parts (902221, 902222)")
        
        # Update parts with "sticker sheet" in name (legacy data, case-insensitive)
        cursor.execute(
            """
            UPDATE parts
            SET ignore_in_inventory = 1
            WHERE LOWER(name) LIKE '%sticker sheet%'
              AND COALESCE(ignore_in_inventory, 0) = 0
            """
        )
        name_updated = cursor.rowcount
        print(f"Updated {name_updated} parts with 'sticker sheet' in name (legacy data)")
        
        conn.commit()
        
        # Show summary
        cursor.execute(
            """
            SELECT COUNT(*) as total
            FROM parts
            WHERE ignore_in_inventory = 1
            """
        )
        total = cursor.fetchone()[0]
        print(f"\nTotal parts with ignore_in_inventory = 1: {total}")
        print("\n✅ Migration complete!")


if __name__ == "__main__":
    main()

