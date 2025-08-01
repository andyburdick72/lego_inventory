#!/usr/bin/env python3
"""
generate_part_mapping.py

Fetch all sets you own via the Rebrickable API and generate
a CSV mapping BrickLink ID → Rebrickable ID for every part.
"""
from __future__ import annotations
import os
import csv
import sys
from pathlib import Path
from typing import Dict

from utils.common_functions import load_rebrickable_environment
from utils.rebrickable_api import paginate

API_PAGE_SIZE = 500  # adjust as needed

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
        # UserSet entries return a nested "set" object
        set_data = page.get("set", page)
        set_num = set_data.get("set_num")
        if not set_num:
            print(f"Warning: missing set_num in response item: {page}")
            continue
        sets.append(set_num)
    print(f"→ Found {len(sets)} owned sets.")
    return sets

def gather_mappings(sets: list[str]) -> Dict[str, str]:
    """
    Return a mapping: bricklink_id -> rebrickable_part_num
    by iterating over every part in each set.
    """
    mapping: Dict[str, str] = {}
    total = len(sets)
    for i, set_num in enumerate(sets, start=1):
        print(f"[{i}/{total}] Set {set_num}: fetching parts…")
        for item in paginate(f"/sets/{set_num}/parts/", params={"page_size": API_PAGE_SIZE}):
            part = item.get("part", item)
            rb_id = part["part_num"]
            for bl in part.get("external_ids", {}).get("BrickLink", []):
                mapping[str(bl)] = rb_id
    return mapping

def write_csv(mapping: Dict[str, str], out_path: Path) -> None:
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["bricklink_id", "rebrickable_id"])
        for bl_id, rb_id in sorted(
            mapping.items(),
            key=lambda kv: (not kv[0].isdigit(), int(kv[0]) if kv[0].isdigit() else kv[0])
        ):
            writer.writerow([bl_id, rb_id])
    print(f"Wrote {len(mapping)} mappings to {out_path}")

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} path/to/output.csv", file=sys.stderr)
        sys.exit(1)

    out_csv = Path(sys.argv[1])

    # Load .env (gets REBRICKABLE_API_KEY, REBRICKABLE_USER_TOKEN)
    load_rebrickable_environment()
    user_token = get_user_token()

    # Fetch your sets and build the mapping
    sets = fetch_owned_sets(user_token)
    mapping = gather_mappings(sets)
    write_csv(mapping, out_csv)

if __name__ == "__main__":
    main()