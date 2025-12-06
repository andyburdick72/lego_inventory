#!/usr/bin/env python3
"""Verify part categories are populated in the database."""

import sqlite3
import sys
from pathlib import Path

# Allow running this file directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.settings import get_settings

SETTINGS = get_settings()

def verify():
    """Check if part categories are populated."""
    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()
        
        # Check part_categories table
        c.execute("SELECT COUNT(*) FROM part_categories")
        category_count = c.fetchone()[0]
        print(f"Categories in part_categories table: {category_count}")
        
        if category_count > 0:
            c.execute("SELECT id, name FROM part_categories LIMIT 10")
            print("\nSample categories:")
            for row in c.fetchall():
                print(f"  {row[0]}: {row[1]}")
        
        # Check parts table
        c.execute("SELECT COUNT(*) FROM parts")
        total_parts = c.fetchone()[0]
        print(f"\nTotal parts: {total_parts}")
        
        c.execute("SELECT COUNT(*) FROM parts WHERE part_category_id IS NOT NULL")
        parts_with_category = c.fetchone()[0]
        print(f"Parts with category: {parts_with_category} ({parts_with_category/total_parts*100:.1f}%)")
        
        if parts_with_category > 0:
            c.execute("""
                SELECT p.design_id, p.name, p.part_category_id, pc.name
                FROM parts p
                LEFT JOIN part_categories pc ON pc.id = p.part_category_id
                WHERE p.part_category_id IS NOT NULL
                LIMIT 5
            """)
            print("\nSample parts with categories:")
            for row in c.fetchall():
                print(f"  {row[0]} ({row[1]}): category {row[2]} ({row[3]})")
        
        # Test the repository query
        if parts_with_category > 0:
            c.execute("SELECT design_id FROM parts WHERE part_category_id IS NOT NULL LIMIT 1")
            sample = c.fetchone()
            if sample:
                test_part = sample[0]
                c.execute("""
                    SELECT p.design_id, p.name, p.part_url, p.part_img_url,
                           p.part_category_id,
                           pc.name AS part_category_name
                    FROM parts p
                    LEFT JOIN part_categories pc ON pc.id = p.part_category_id
                    WHERE p.design_id = ?
                """, (test_part,))
                result = c.fetchone()
                if result:
                    print(f"\n=== Repository Query Test ===")
                    print(f"Part: {result[0]} ({result[1]})")
                    print(f"Category ID: {result[4]}")
                    print(f"Category Name: {result[5]}")
        
        print("\n" + "="*50)
        if category_count > 0 and parts_with_category > 0:
            print("✅ Part categories are populated!")
        else:
            print("❌ Part categories are NOT populated.")
            print("   Run: python3 src/scripts/load_my_rebrickable_parts.py --all-sets")

if __name__ == "__main__":
    verify()

