#!/usr/bin/env python3
"""Load part categories from Rebrickable API and update parts table."""

import sqlite3
import sys
from pathlib import Path

# Allow running this file directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.settings import get_settings
from integrations.rebrickable_api import get_json, paginate

SETTINGS = get_settings()
API_KEY = SETTINGS.rebrickable_api_key

if not API_KEY:
    print("Error: APP_REBRICKABLE_API_KEY not set in data/.env or environment.", file=sys.stderr)
    sys.exit(1)


def load_part_categories():
    """Load part categories from Rebrickable and update parts table."""
    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()
        
        # Get all unique design_ids from parts table
        c.execute("SELECT DISTINCT design_id FROM parts")
        design_ids = [row[0] for row in c.fetchall()]
        
        print(f"Found {len(design_ids)} parts to process...")
        
        # Cache for category names
        category_names: dict[int, str] = {}
        updated = 0
        errors = 0
        
        for i, design_id in enumerate(design_ids, 1):
            try:
                if i % 100 == 0:
                    print(f"[{i}/{len(design_ids)}] Processing...")
                
                # Fetch part details from Rebrickable
                part_url = f"https://rebrickable.com/api/v3/lego/parts/{design_id}/"
                part_data = get_json(part_url, params={"key": API_KEY})
                
                # Try different ways to get category_id
                part_category_id = part_data.get("part_category_id")
                if part_category_id is None:
                    # Sometimes it's nested in part_category object
                    part_category = part_data.get("part_category")
                    if isinstance(part_category, dict):
                        part_category_id = part_category.get("id")
                
                # Debug: print first few parts to see what we're getting
                if i <= 3:
                    print(f"  Debug: Part {design_id} - category_id: {part_category_id}, keys: {list(part_data.keys())[:10]}")
                
                if part_category_id is not None:
                    # Fetch category name if not cached
                    if part_category_id not in category_names:
                        try:
                            category_url = f"https://rebrickable.com/api/v3/lego/part_categories/{part_category_id}/"
                            category_data = get_json(category_url, params={"key": API_KEY})
                            category_name = category_data.get("name")
                            if category_name:
                                category_names[part_category_id] = category_name
                                # Insert or update category
                                c.execute(
                                    """
                                    INSERT OR REPLACE INTO part_categories (id, name)
                                    VALUES (?, ?)
                                    """,
                                    (part_category_id, category_name),
                                )
                        except Exception as e:
                            print(f"  ⚠️ Warning: Could not fetch category {part_category_id} for part {design_id}: {e}")
                            # Still update the part with category_id even if we can't get the name
                    
                    # Update part with category_id (even if we don't have the name yet)
                    c.execute(
                        """
                        UPDATE parts
                        SET part_category_id = ?
                        WHERE design_id = ?
                        """,
                        (part_category_id, design_id),
                    )
                    if c.rowcount > 0:
                        updated += 1
                    
            except Exception as e:
                errors += 1
                if errors <= 10:  # Only print first 10 errors
                    print(f"  ❌ Error processing part {design_id}: {e}")
                continue
        
        conn.commit()
        print(f"\n===== Summary =====")
        print(f"Parts updated: {updated}")
        print(f"Categories loaded: {len(category_names)}")
        print(f"Errors: {errors}")


if __name__ == "__main__":
    load_part_categories()

