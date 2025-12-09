#!/usr/bin/env python3
"""Migrate part_aliases table to allow one alias to map to multiple design_ids.

This changes the schema from:
    alias TEXT PRIMARY KEY
    design_id TEXT

To:
    alias TEXT
    design_id TEXT
    PRIMARY KEY (alias, design_id)

This matches the real-world behavior where the same alias (e.g., BrickLink ID "3003")
can map to multiple Rebrickable design_ids (e.g., both 3003 and 6223).
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]  # repo root containing 'src'
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from infra.db.inventory_db import _connect  # noqa: E402
import sqlite3

def migrate():
    """Migrate part_aliases table to support multiple design_ids per alias."""
    print("Migrating part_aliases table schema...")
    
    with _connect() as conn:
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(part_aliases)")
        columns = cursor.fetchall()
        print(f"\nCurrent schema:")
        for col in columns:
            print(f"  {col}")
        
        # Check if migration is needed
        # Look for PRIMARY KEY constraint on alias column
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='part_aliases'")
        create_sql = cursor.fetchone()
        if create_sql:
            sql_str = create_sql[0] if create_sql else ''
            if sql_str and 'PRIMARY KEY (alias, design_id)' in sql_str.upper():
                print("\n✓ Schema already migrated - no action needed")
                return
            if sql_str and ('alias TEXT PRIMARY KEY' in sql_str or 'alias TEXT PRIMARY' in sql_str):
                print("\n⚠ Migration needed - current schema has alias as PRIMARY KEY")
            else:
                if sql_str:
                    print(f"\n⚠ Unexpected schema: {sql_str}")
                print("Proceeding with migration anyway...")
        
        # Get current row count
        cursor.execute("SELECT COUNT(*) FROM part_aliases")
        row_count = cursor.fetchone()[0]
        print(f"\nCurrent row count: {row_count}")
        
        # Check for duplicates (shouldn't exist, but let's verify)
        cursor.execute("""
            SELECT alias, COUNT(*) as cnt
            FROM part_aliases
            GROUP BY alias
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"\n⚠ Found {len(duplicates)} aliases with multiple design_ids:")
            for alias, cnt in duplicates[:10]:  # Show first 10
                cursor.execute("SELECT design_id FROM part_aliases WHERE alias = ?", (alias,))
                design_ids = [row[0] for row in cursor.fetchall()]
                print(f"  {alias}: {design_ids}")
            if len(duplicates) > 10:
                print(f"  ... and {len(duplicates) - 10} more")
        else:
            print("\n✓ No duplicate aliases found (expected before migration)")
        
        # Step 1: Create new table with correct schema
        print("\nStep 1: Creating new table with composite PRIMARY KEY...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS part_aliases_new(
                alias     TEXT NOT NULL,
                design_id TEXT NOT NULL REFERENCES parts(design_id),
                PRIMARY KEY (alias, design_id)
            )
        """)
        
        # Step 2: Copy all data from old table
        print("Step 2: Copying data from old table...")
        cursor.execute("""
            INSERT INTO part_aliases_new (alias, design_id)
            SELECT alias, design_id
            FROM part_aliases
        """)
        copied_count = cursor.rowcount
        print(f"  Copied {copied_count} rows")
        
        # Step 3: Verify data integrity
        cursor.execute("SELECT COUNT(*) FROM part_aliases_new")
        new_count = cursor.fetchone()[0]
        if new_count != row_count:
            raise RuntimeError(f"Row count mismatch: old={row_count}, new={new_count}")
        print(f"  ✓ Verified: {new_count} rows in new table")
        
        # Step 4: Drop old table
        print("Step 3: Dropping old table...")
        cursor.execute("DROP TABLE part_aliases")
        
        # Step 5: Rename new table
        print("Step 4: Renaming new table...")
        cursor.execute("ALTER TABLE part_aliases_new RENAME TO part_aliases")
        
        # Step 6: Recreate index
        print("Step 5: Recreating index...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_alias ON part_aliases(alias)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_alias_design_id ON part_aliases(design_id)")
        
        conn.commit()
        
        print("\n✓ Migration complete!")
        print(f"\nNew schema allows one alias to map to multiple design_ids")
        print(f"Example: Both part 3003 and 6223 can now have alias '3003'")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

