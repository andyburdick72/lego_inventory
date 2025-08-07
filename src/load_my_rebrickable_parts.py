#!/usr/bin/env python3
"""
load_my_rebrickable_parts.py

Fetch all sets you own via the Rebrickable API and populate
the parts and part_aliases tables in the local SQLite database.
"""
from __future__ import annotations
import os
import sys
import sqlite3
from pathlib import Path
from utils.common_functions import load_rebrickable_environment
from utils.rebrickable_api import paginate
from inventory_db import insert_set_part

API_PAGE_SIZE = 500  # adjust as needed
DB_PATH = Path("data/lego_inventory.db")

def get_user_token() -> str:
    token = os.getenv("REBRICKABLE_USER_TOKEN")
    if not token:
        print("Error: REBRICKABLE_USER_TOKEN not set in environment.", file=sys.stderr)
        sys.exit(1)
    return token

def fetch_owned_sets(user_token: str) -> list[str]:
    """Return a list of all set numbers owned by this user token."""
    print(f"Fetching owned sets for user token '{user_token}'…")
    sets: list[str] = []
    for page in paginate(f"https://rebrickable.com/api/v3/users/{user_token}/sets/", params={"page_size": API_PAGE_SIZE}):
        set_data = page.get("set", page)
        set_num = set_data.get("set_num")
        if not set_num:
            print(f"Warning: missing set_num in response item: {page}")
            continue
        sets.append(set_num)
    print(f"→ Found {len(sets)} owned sets.")
    return sets

def gather_and_insert_parts(sets: list[str], conn: sqlite3.Connection, insert_only_set_parts: bool = False) -> None:
    """
    Fetch all parts from owned sets and insert them into the parts and part_aliases tables.
    """
    seen_parts: set[str] = set()
    seen_aliases: set[str] = set()
    total = len(sets)
    cursor = conn.cursor()

    for i, set_num in enumerate(sets, start=1):
        print(f"[{i}/{total}] Set {set_num}: fetching parts…")
        for item in paginate(f"/sets/{set_num}/parts/", params={"page_size": API_PAGE_SIZE}):
            part = item.get("part", item)
            rb_id = part["part_num"]
            name = part["name"]
            if not insert_only_set_parts and rb_id not in seen_parts:
                try:
                    cursor.execute("INSERT OR IGNORE INTO parts (design_id, name) VALUES (?, ?)", (rb_id, name))
                    seen_parts.add(rb_id)
                except sqlite3.IntegrityError as e:
                    print(f"Error inserting part {rb_id}: {e}")

            if not insert_only_set_parts:
                for bl in part.get("external_ids", {}).get("BrickLink", []):
                    bl_str = str(bl)
                    if bl_str not in seen_aliases:
                        try:
                            cursor.execute("INSERT OR IGNORE INTO part_aliases (alias, design_id) VALUES (?, ?)", (bl_str, rb_id))
                            seen_aliases.add(bl_str)
                        except sqlite3.IntegrityError as e:
                            print(f"Error inserting alias {bl_str} → {rb_id}: {e}")

            color_id = item["color"]["id"]
            quantity = item["quantity"]
            insert_set_part(set_num, rb_id, color_id, quantity)
    conn.commit()
    print(f"→ Inserted {len(seen_parts)} parts and {len(seen_aliases)} aliases.")

def main():
    # Load .env (gets REBRICKABLE_API_KEY, REBRICKABLE_USER_TOKEN)
    load_rebrickable_environment()
    user_token = get_user_token()

    # Open DB connection
    if not DB_PATH.exists():
        print(f"Error: database file {DB_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        # Fetch your sets and insert part mappings
        sets = fetch_owned_sets(user_token)
        insert_only_set_parts = "--only-set-parts" in sys.argv
        gather_and_insert_parts(sets, conn, insert_only_set_parts=insert_only_set_parts)
    finally:
        conn.close()

if __name__ == "__main__":
    main()