#!/usr/bin/env python3
"""Load part categories from set_parts data (faster than fetching each part individually)."""

import sqlite3
import sys
from pathlib import Path

# Allow running this file directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.settings import get_settings
from integrations.rebrickable_api import get_json

SETTINGS = get_settings()
API_KEY = SETTINGS.rebrickable_api_key

if not API_KEY:
    print("Error: APP_REBRICKABLE_API_KEY not set in data/.env or environment.", file=sys.stderr)
    sys.exit(1)


def load_part_categories_from_sets():
    """Load part categories from set_parts data."""
    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()
        
        # Get unique part_category_ids from set_parts (if they exist)
        # Actually, since we removed part_category_id from set_parts, we need to fetch from sets
        # Let's get unique design_ids that need categories
        c.execute("""
            SELECT DISTINCT p.design_id
            FROM parts p
            WHERE p.part_category_id IS NULL
        """)
        design_ids = [row[0] for row in c.fetchall()]
        
        print(f"Found {len(design_ids)} parts without categories...")
        
        if len(design_ids) == 0:
            print("All parts already have categories!")
            return
        
        # Get a sample of sets to fetch parts from
        c.execute("SELECT DISTINCT set_num FROM set_parts LIMIT 10")
        sample_sets = [row[0] for row in c.fetchall()]
        
        print(f"Fetching categories from {len(sample_sets)} sample sets...")
        
        # Cache for category names
        category_names: dict[int, str] = {}
        part_categories: dict[str, int] = {}  # design_id -> category_id
        updated = 0
        
        # Fetch parts from sample sets to get categories
        for set_num in sample_sets:
            try:
                url = f"https://rebrickable.com/api/v3/lego/sets/{set_num}/parts/"
                data = get_json(url, params={"key": API_KEY, "page_size": 100})
                
                for item in data.get("results", []):
                    part = item.get("part", {})
                    design_id = part.get("part_num")
                    category_id = part.get("part_category_id")
                    
                    if design_id and category_id:
                        part_categories[design_id] = category_id
                        
                        # Fetch category name if not cached
                        if category_id not in category_names:
                            try:
                                category_url = f"https://rebrickable.com/api/v3/lego/part_categories/{category_id}/"
                                category_data = get_json(category_url, params={"key": API_KEY})
                                category_name = category_data.get("name")
                                if category_name:
                                    category_names[category_id] = category_name
                                    c.execute(
                                        """
                                        INSERT OR REPLACE INTO part_categories (id, name)
                                        VALUES (?, ?)
                                        """,
                                        (category_id, category_name),
                                    )
                            except Exception as e:
                                print(f"  ⚠️ Warning: Could not fetch category {category_id}: {e}")
            except Exception as e:
                print(f"  ⚠️ Warning: Could not fetch set {set_num}: {e}")
                continue
        
        print(f"\nFound {len(part_categories)} parts with categories from sample sets...")
        print("Updating parts table...")
        
        # Update parts table with categories
        for design_id, category_id in part_categories.items():
            c.execute(
                """
                UPDATE parts
                SET part_category_id = ?
                WHERE design_id = ?
                """,
                (category_id, design_id),
            )
            if c.rowcount > 0:
                updated += 1
        
        conn.commit()
        print(f"\n===== Summary =====")
        print(f"Parts updated: {updated}")
        print(f"Categories loaded: {len(category_names)}")
        print(f"\nNote: This only processed a sample of sets. Run load_my_rebrickable_parts.py")
        print("to get categories for all parts from all your sets.")


if __name__ == "__main__":
    load_part_categories_from_sets()

