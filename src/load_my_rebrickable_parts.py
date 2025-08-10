#!/usr/bin/env python3
"""
load_my_rebrickable_parts.py

Fetch all sets you own via the Rebrickable API and populate
the parts and part_aliases tables in the local SQLite database.

CLI flags:
  --only-set-parts           Skip inserting new parts/aliases; update set_parts only.
  --exclude-spares           OPT-OUT: do not include spare/extra parts (default is include).
  --exclude-minifig-parts    OPT-OUT: do not include minifig component parts (default is include).
  --skip-refresh             OPT-OUT: skip deleting existing set_parts for owned sets before reloading (default is refresh).
"""
from __future__ import annotations
import os
import sys
import sqlite3
import time
import requests
import csv
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

def get_api_key() -> str:
    api_key = os.getenv("REBRICKABLE_API_KEY")
    if not api_key:
        print("Error: REBRICKABLE_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)
    return api_key

def fetch_part_detail(design_id: str, api_key: str, *, retries: int = 5) -> tuple[dict | None, int | None, str | None]:
    """Fetch a single part detail from Rebrickable.
    Returns (json_dict_or_none, http_status_or_none, reason_or_none).
    """
    url = f"https://rebrickable.com/api/v3/lego/parts/{design_id}/"
    headers = {"Authorization": f"key {api_key}"}
    backoff = 1.0
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            status = resp.status_code
            if status == 200:
                return resp.json(), status, None
            if status == 404:
                return None, status, "not_found"
            if status in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff = min(backoff * 2, 16.0)
                continue
            # Other non-success
            return None, status, f"http_{status}"
        except requests.RequestException as e:
            # Network error; retry with backoff
            time.sleep(backoff)
            backoff = min(backoff * 2, 16.0)
    return None, None, "network_or_retries_exhausted"

def backfill_all_parts(conn: sqlite3.Connection) -> None:
    """Backfill part_url and part_img_url for any parts missing them."""
    api_key = get_api_key()
    cur = conn.cursor()
    total_missing = cur.execute(
        """
        SELECT COUNT(*) FROM parts
        WHERE part_url IS NULL OR part_img_url IS NULL
        """
    ).fetchone()[0]
    print(f"Backfilling metadata for {total_missing} parts missing URLs/images…")
    checked = updated = skipped = errors = 0

    missing_csv_path = Path("data/missing_part_metadata.csv")
    # Prepare CSV with header
    with open(missing_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["design_id", "reason", "last_status"])

    rows = cur.execute(
        """
        SELECT design_id
        FROM parts
        WHERE part_url IS NULL OR part_img_url IS NULL
        ORDER BY design_id
        """
    ).fetchall()

    for (design_id,) in rows:
        checked += 1
        data, status, reason = fetch_part_detail(design_id, api_key)
        if not data:
            skipped += 1
            # Log stubborn/missing case
            with open(missing_csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([design_id, reason or "no_data", status or "-"])
            time.sleep(0.3)
            continue
        name = data.get("name")
        part_url = data.get("part_url")
        part_img_url = data.get("part_img_url")
        # If API returned 200 but no part_url, use deterministic canonical page URL
        if status == 200 and not part_url:
            part_url = f"https://rebrickable.com/parts/{design_id}/"
        try:
            cur.execute(
                """
                UPDATE parts
                SET name = COALESCE(?, name),
                    part_url = COALESCE(?, part_url),
                    part_img_url = COALESCE(?, part_img_url)
                WHERE design_id = ?
                """,
                (name, part_url, part_img_url, design_id),
            )
            # If the image is still missing after a 200, log that specifically
            if status == 200 and (part_img_url is None):
                with open(missing_csv_path, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([design_id, "no_image_available_200", 200])
            if cur.rowcount == 1:
                updated += 1
            else:
                skipped += 1
        except sqlite3.Error:
            errors += 1
        # Slower pacing to avoid rate limits
        time.sleep(0.3)

    conn.commit()
    print("\n===== Part Metadata Backfill Summary =====")
    print(f"Checked: {checked}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")

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

def gather_and_insert_parts(
    sets: list[str],
    conn: sqlite3.Connection,
    insert_only_set_parts: bool = False,
    include_spares: bool = True,
    include_minifig_parts: bool = True
) -> None:
    """
    Fetch all parts from owned sets and insert them into the parts and part_aliases tables.
    """
    start_ts = time.perf_counter()
    new_parts = 0
    new_aliases = 0
    set_parts_inserted = 0
    set_parts_updated = 0
    set_parts_unchanged = 0
    sets_processed = 0
    seen_parts: set[str] = set()
    seen_aliases: set[str] = set()
    total = len(sets)
    cursor = conn.cursor()

    # Build per-request params based on defaults (include spares + minifig parts)
    base_params = {"page_size": API_PAGE_SIZE}
    if include_minifig_parts:
        # Rebrickable supports including minifig components in set inventories
        base_params["inc_minifig_parts"] = 1
    if include_spares:
        # Some deployments accept this hint; even if ignored, we will merge spares via is_spare below
        base_params["include_spare_parts"] = 1

    for i, set_num in enumerate(sets, start=1):
        print(f"[{i}/{total}] Set {set_num}: fetching parts…")
        sets_processed += 1
        # Aggregate quantities per (part, color), optionally including spare parts
        params = dict(base_params)
        agg: dict[tuple[str, int], int] = {}
        for item in paginate(f"/sets/{set_num}/parts/", params=params):
            part = item.get("part", item)
            rb_id = part["part_num"]
            name = part["name"]
            part_url = part.get("part_url")
            part_img_url = part.get("part_img_url")
            # Deterministic fallback for part_url if missing (safe canonical URL)
            if part_url is None:
                part_url = f"https://rebrickable.com/parts/{rb_id}/"
            # Opportunistically backfill part metadata
            cursor.execute(
                """
                UPDATE parts
                SET name = COALESCE(?, name),
                    part_url = COALESCE(?, part_url),
                    part_img_url = COALESCE(?, part_img_url)
                WHERE design_id = ?
                """,
                (name, part_url, part_img_url, rb_id),
            )
            if not insert_only_set_parts:
                # Ensure the part exists
                if rb_id not in seen_parts:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO parts (design_id, name) VALUES (?, ?)",
                            (rb_id, name),
                        )
                        if cursor.rowcount == 1:
                            new_parts += 1
                            seen_parts.add(rb_id)
                    except sqlite3.IntegrityError as e:
                        print(f"Error inserting part {rb_id}: {e}")
                # Insert BrickLink aliases if present
                for bl in part.get("external_ids", {}).get("BrickLink", []):
                    bl_str = str(bl)
                    if bl_str not in seen_aliases:
                        try:
                            cursor.execute(
                                "INSERT OR IGNORE INTO part_aliases (alias, design_id) VALUES (?, ?)",
                                (bl_str, rb_id),
                            )
                            if cursor.rowcount == 1:
                                new_aliases += 1
                                seen_aliases.add(bl_str)
                        except sqlite3.IntegrityError as e:
                            print(f"Error inserting alias {bl_str} → {rb_id}: {e}")

            color_id = item["color"]["id"]
            qty = int(item["quantity"]) or 0
            # Skip spares unless included
            is_spare = bool(item.get("is_spare"))
            if is_spare and not include_spares:
                continue
            key = (rb_id, color_id)
            agg[key] = agg.get(key, 0) + qty

        # Now write the aggregated quantities to set_parts
        for (rb_id, color_id), quantity in agg.items():
            existing = cursor.execute(
                "SELECT quantity FROM set_parts WHERE set_num = ? AND design_id = ? AND color_id = ?",
                (set_num, rb_id, color_id),
            ).fetchone()
            insert_set_part(set_num, rb_id, color_id, quantity, conn=conn)
            if existing is None:
                set_parts_inserted += 1
            else:
                if existing[0] != quantity:
                    set_parts_updated += 1
                else:
                    set_parts_unchanged += 1
    conn.commit()
    elapsed = time.perf_counter() - start_ts
    print("\n===== Rebrickable Load Summary =====")
    print(f"Sets processed: {sets_processed}")
    if not insert_only_set_parts:
        print(f"New parts inserted: {new_parts:,}")
        print(f"New aliases inserted: {new_aliases:,}")
    else:
        print("(Skipped inserting parts and aliases due to --only-set-parts)")
    print(
        "Set→part mappings: "
        f"{set_parts_inserted:,} inserted, "
        f"{set_parts_updated:,} updated, "
        f"{set_parts_unchanged:,} unchanged"
    )
    print(f"Duration: {elapsed:.2f}s")

def main():
    # Load .env (gets REBRICKABLE_API_KEY, REBRICKABLE_USER_TOKEN)
    load_rebrickable_environment()
    user_token = get_user_token()

    # Open DB connection
    if not DB_PATH.exists():
        print(f"Error: database file {DB_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    # Match inventory_db connection settings to avoid write-locks
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")

    # Flags
    if "--backfill-all-parts" in sys.argv:
        backfill_all_parts(conn)
        conn.close()
        return

    try:
        # Fetch your sets and insert part mappings
        sets = fetch_owned_sets(user_token)
        # Always refresh set_parts for owned sets unless explicitly skipped
        if "--skip-refresh" not in sys.argv:
            with conn:
                conn.executemany(
                    "DELETE FROM set_parts WHERE set_num = ?",
                    [(s,) for s in sets],
                )
            print(f"Cleared set_parts for {len(sets)} owned sets; rebuilding…")

        insert_only_set_parts = "--only-set-parts" in sys.argv
        # Defaults: include both, unless explicitly excluded
        exclude_spares = "--exclude-spares" in sys.argv
        exclude_minifig_parts = "--exclude-minifig-parts" in sys.argv
        include_spares = not exclude_spares
        include_minifig_parts = not exclude_minifig_parts

        gather_and_insert_parts(
            sets,
            conn,
            insert_only_set_parts=insert_only_set_parts,
            include_spares=include_spares,
            include_minifig_parts=include_minifig_parts,
        )
    finally:
        conn.close()

if __name__ == "__main__":
    main()