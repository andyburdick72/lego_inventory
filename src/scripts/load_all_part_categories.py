#!/usr/bin/env python3
"""Efficiently load part categories for all parts in the parts table (including loose inventory)."""

import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def load_all_part_categories():
    """Load part categories for all unique parts in set_parts."""
    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()
        
        # Get all unique design_ids from parts table that don't have categories yet
        # This includes parts from sets AND loose inventory
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
        
        # Cache for category names (shared across threads)
        category_name_cache: dict[int, str] = {}
        updated = 0
        errors = 0
        start_time = time.time()
        
        def fetch_part_category(design_id: str) -> tuple[str, int | None, Exception | None]:
            """Fetch category for a single part. Returns (design_id, category_id, error)."""
            try:
                part_url = f"https://rebrickable.com/api/v3/lego/parts/{design_id}/"
                part_data = get_json(part_url, params={"key": API_KEY})
                part_category_id = part_data.get("part_category_id")
                return (design_id, part_category_id, None)
            except Exception as e:
                return (design_id, None, e)
        
        def fetch_category_name(category_id: int) -> tuple[int, str | None, Exception | None]:
            """Fetch category name. Returns (category_id, name, error)."""
            try:
                category_url = f"https://rebrickable.com/api/v3/lego/part_categories/{category_id}/"
                category_data = get_json(category_url, params={"key": API_KEY})
                category_name = category_data.get("name")
                return (category_id, category_name, None)
            except Exception as e:
                return (category_id, None, e)
        
        # Process parts in parallel (5 concurrent requests)
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all part fetch tasks
            future_to_part = {executor.submit(fetch_part_category, design_id): design_id 
                             for design_id in design_ids}
            
            part_categories: dict[str, int] = {}  # design_id -> category_id
            category_ids_to_fetch: set[int] = set()
            
            completed = 0
            for future in as_completed(future_to_part):
                completed += 1
                design_id, category_id, error = future.result()
                
                if error:
                    errors += 1
                    if errors <= 10:
                        print(f"  ❌ Error fetching part {design_id}: {error}")
                    continue
                
                if category_id is not None:
                    part_categories[design_id] = category_id
                    category_ids_to_fetch.add(category_id)
                
                # Progress update
                if completed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (len(design_ids) - completed) / rate if rate > 0 else 0
                    print(f"[{completed}/{len(design_ids)}] Fetched parts... ({rate:.1f} parts/sec, ~{remaining:.0f}s remaining)")
        
        print(f"\nFetching category names for {len(category_ids_to_fetch)} unique categories...")
        
        # Fetch category names in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_category = {executor.submit(fetch_category_name, cat_id): cat_id 
                                 for cat_id in category_ids_to_fetch}
            
            for future in as_completed(future_to_category):
                category_id, category_name, error = future.result()
                
                if error:
                    if len(category_name_cache) < 5:
                        print(f"  ⚠️ Warning: Could not fetch category {category_id}: {error}")
                    continue
                
                if category_name:
                    category_name_cache[category_id] = category_name
                    # Insert or update category
                    c.execute(
                        """
                        INSERT OR REPLACE INTO part_categories (id, name)
                        VALUES (?, ?)
                        """,
                        (category_id, category_name),
                    )
        
        # Update parts table with categories
        print(f"\nUpdating parts table with categories...")
        for design_id, category_id in part_categories.items():
            c.execute(
                """
                UPDATE parts
                SET part_category_id = ?
                WHERE design_id = ? AND part_category_id IS NULL
                """,
                (category_id, design_id),
            )
            if c.rowcount > 0:
                updated += 1
        
        conn.commit()
        elapsed = time.time() - start_time
        print(f"\n===== Summary =====")
        print(f"Parts updated: {updated}")
        print(f"Categories loaded: {len(category_name_cache)}")
        print(f"Errors: {errors}")
        print(f"Duration: {elapsed:.1f}s ({len(design_ids)/elapsed:.1f} parts/sec)")


if __name__ == "__main__":
    load_all_part_categories()

