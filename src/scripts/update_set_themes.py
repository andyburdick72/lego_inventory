#!/usr/bin/env python3
"""Update theme information for all existing sets in the database."""

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


def update_all_set_themes():
    """Update theme information for all sets in the database."""
    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()
        
        # Get all unique set numbers
        c.execute("SELECT DISTINCT set_num FROM sets")
        set_nums = [row[0] for row in c.fetchall()]
        
        print(f"Found {len(set_nums)} unique sets to update...")
        
        updated = 0
        errors = 0
        
        for i, set_num in enumerate(set_nums, 1):
            try:
                print(f"[{i}/{len(set_nums)}] Updating {set_num}...", end=" ")
                
                url = f"https://rebrickable.com/api/v3/lego/sets/{set_num}/"
                set_data = get_json(url, params={"key": API_KEY})
                
                theme_id = set_data.get("theme_id")
                
                # Fetch theme name from themes endpoint if we have theme_id
                theme_name = None
                if theme_id is not None:
                    try:
                        theme_url = f"https://rebrickable.com/api/v3/lego/themes/{theme_id}/"
                        theme_data = get_json(theme_url, params={"key": API_KEY})
                        theme_name = theme_data.get("name")
                    except Exception as e:
                        print(f" (error fetching theme: {e})", end="")
                
                if theme_id is not None and theme_name:
                    # Store theme
                    c.execute(
                        """
                        INSERT OR REPLACE INTO themes (id, name)
                        VALUES (?, ?)
                        """,
                        (theme_id, theme_name),
                    )
                    # Update all sets with this set_num
                    c.execute(
                        """
                        UPDATE sets SET theme_id = ? WHERE set_num = ?
                        """,
                        (theme_id, set_num),
                    )
                    conn.commit()
                    print(f"✅ {theme_name}")
                    updated += 1
                else:
                    print("⚠️ No theme data")
            except Exception as e:
                print(f"❌ Error: {e}")
                errors += 1
                continue
        
        print(f"\n===== Summary =====")
        print(f"Updated: {updated}")
        print(f"Errors: {errors}")


if __name__ == "__main__":
    update_all_set_themes()

