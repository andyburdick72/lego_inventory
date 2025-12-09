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

import argparse
import csv
import sqlite3
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[1]  # repo root containing 'src'
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.settings import get_settings  # noqa: E402
from integrations.rebrickable_api import paginate, get_json  # noqa: E402
from infra.db.inventory_db import _connect, insert_set_part  # noqa: E402

# Centralized settings (cached by get_settings via lru_cache)
SETTINGS = get_settings()

API_PAGE_SIZE = 500  # adjust as needed


def get_user_token() -> str:
    token = SETTINGS.rebrickable_user_token
    if not token:
        print(
            "Error: APP_REBRICKABLE_USER_TOKEN not set in data/.env or environment.",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def get_api_key() -> str:
    api_key = SETTINGS.rebrickable_api_key
    if not api_key:
        print(
            "Error: APP_REBRICKABLE_API_KEY not set in data/.env or environment.", file=sys.stderr
        )
        sys.exit(1)
    return api_key


def fetch_part_detail(
    design_id: str, api_key: str, *, retries: int = 5
) -> tuple[dict | None, int | None, str | None]:
    """Fetch a single part detail from Rebrickable.
    Returns (json_dict_or_none, http_status_or_none, reason_or_none).
    """
    url = f"https://rebrickable.com/api/v3/lego/parts/{design_id}/"
    headers = {"Authorization": f"key {api_key}"}
    backoff = 1.0
    for _attempt in range(retries):
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
        except requests.RequestException:
            # Network error; retry with backoff
            time.sleep(backoff)
            backoff = min(backoff * 2, 16.0)
    return None, None, "network_or_retries_exhausted"


def backfill_all_parts(conn: sqlite3.Connection) -> None:
    """Backfill part_url and part_img_url for any parts missing them.
    Also captures and stores alternate Rebrickable part IDs from external_ids."""
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
    new_aliases = 0

    missing_csv_path = Path(SETTINGS.reports_dir) / "missing_part_metadata.csv"
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
            
            # Capture alternate Rebrickable part IDs from external_ids
            # Only capture LEGO and BrickLink aliases, and skip self-referential aliases
            external_ids = data.get("external_ids", {})
            
            # Capture BrickLink IDs - these are commonly used in container names
            # Only store if different from design_id (skip self-referential aliases)
            bricklink_ids = external_ids.get("BrickLink", [])
            for bl_id in bricklink_ids:
                bl_id_str = str(bl_id)
                # Only store if it's different from the design_id and looks like a valid part ID
                if bl_id_str != design_id and len(bl_id_str) >= 2:
                    try:
                        cur.execute(
                            "INSERT OR IGNORE INTO part_aliases (alias, design_id) VALUES (?, ?)",
                            (bl_id_str, design_id),
                        )
                        if cur.rowcount == 1:
                            new_aliases += 1
                    except sqlite3.Error:
                        pass  # Ignore errors (might be duplicate)
            
            # LEGO part numbers are alternate Rebrickable IDs (list, not dict)
            # Only store if different from design_id (skip self-referential aliases)
            lego_ids = external_ids.get("LEGO", [])
            for alt_id in lego_ids:
                alt_id_str = str(alt_id)
                # Only store if it's different from the design_id and looks like a valid part ID
                if alt_id_str != design_id and len(alt_id_str) >= 2:
                    try:
                        cur.execute(
                            "INSERT OR IGNORE INTO part_aliases (alias, design_id) VALUES (?, ?)",
                            (alt_id_str, design_id),
                        )
                        if cur.rowcount == 1:
                            new_aliases += 1
                    except sqlite3.Error:
                        pass  # Ignore errors (might be duplicate)
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
    if new_aliases > 0:
        print(f"New alternate part IDs stored: {new_aliases}")


def backfill_alternate_ids(conn: sqlite3.Connection) -> None:
    """Backfill alternate Rebrickable part IDs for all parts.
    Fetches part details and stores alternate IDs from external_ids.LEGO.ext_ids."""
    api_key = get_api_key()
    cur = conn.cursor()
    total_parts = cur.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    print(f"Backfilling alternate part IDs for {total_parts} parts…")
    checked = new_aliases = skipped = errors = 0

    rows = cur.execute(
        """
        SELECT design_id
        FROM parts
        ORDER BY design_id
        """
    ).fetchall()

    for (design_id,) in rows:
        checked += 1
        if checked % 100 == 0:
            print(f"Progress: {checked}/{total_parts} ({checked*100//total_parts}%)")
        
        data, status, reason = fetch_part_detail(design_id, api_key)
        if not data:
            skipped += 1
            time.sleep(0.3)
            continue
        
        # Capture alternate Rebrickable part IDs from external_ids
        external_ids = data.get("external_ids", {})
        
        # Capture BrickLink IDs - these are commonly used in container names
        # Only store if different from design_id (skip self-referential aliases)
        bricklink_ids = external_ids.get("BrickLink", [])
        for bl_id in bricklink_ids:
            bl_id_str = str(bl_id)
            # Only store if it's different from the design_id and looks like a valid part ID
            if bl_id_str != design_id and len(bl_id_str) >= 2:
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO part_aliases (alias, design_id) VALUES (?, ?)",
                        (bl_id_str, design_id),
                    )
                    if cur.rowcount == 1:
                        new_aliases += 1
                except sqlite3.Error:
                    pass  # Ignore errors (might be duplicate)
        
        # LEGO part numbers are alternate Rebrickable IDs (list, not dict)
        # Only store if different from design_id (skip self-referential aliases)
        lego_ids = external_ids.get("LEGO", [])
        for alt_id in lego_ids:
            alt_id_str = str(alt_id)
            # Only store if it's different from the design_id and looks like a valid part ID
            if alt_id_str != design_id and len(alt_id_str) >= 2:
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO part_aliases (alias, design_id) VALUES (?, ?)",
                        (alt_id_str, design_id),
                    )
                    if cur.rowcount == 1:
                        new_aliases += 1
                except sqlite3.Error:
                    pass  # Ignore errors (might be duplicate)
        
        # Slower pacing to avoid rate limits
        time.sleep(0.3)

    conn.commit()
    print("\n===== Alternate Part IDs Backfill Summary =====")
    print(f"Checked: {checked}")
    print(f"New alternate IDs stored: {new_aliases}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")


def fetch_owned_sets(user_token: str) -> list[str]:
    """Return a list of all set numbers owned by this user token."""
    print("Fetching owned sets…")
    sets: list[str] = []
    for page in paginate(
        f"https://rebrickable.com/api/v3/users/{user_token}/sets/",
        params={"page_size": API_PAGE_SIZE},
    ):
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
    include_minifig_parts: bool = True,
    skip_refresh: bool = False,
) -> None:
    """
    Fetch all parts from owned sets and insert them into the parts and part_aliases tables.
    If skip_refresh is False, deletes existing set_parts for each set before inserting new ones.
    """
    # Shared cache for category names across all sets
    category_name_cache: dict[int, str] = {}
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
        try:
            print(f"[{i}/{total}] Set {set_num}: fetching parts…")
            
            # Delete existing parts for this set BEFORE fetching new ones (safer - only delete what we're about to replace)
            # Note: We delete first, then insert. If insertion fails, we'll have lost data for this set,
            # but that's better than losing all sets. The connection auto-commits each statement.
            if not skip_refresh:
                cursor.execute("DELETE FROM set_parts WHERE set_num = ?", (set_num,))
                conn.commit()  # Commit deletion immediately
            
            # Aggregate quantities per (part, color), optionally including spare parts
            params = dict(base_params)
            agg: dict[tuple[str, int], int] = {}
            seen_part_ids: set[str] = set()  # Track which parts we've seen in this set
            for item in paginate(f"/sets/{set_num}/parts/", params=params):
                part = item.get("part", item)
                rb_id = part["part_num"]
                name = part["name"]
                part_url = part.get("part_url")
                part_img_url = part.get("part_img_url")
                part_category_id = part.get("part_category_id")
                
                # Check if part already exists in database to preserve manual overrides
                existing_part = cursor.execute(
                    "SELECT ignore_in_inventory FROM parts WHERE design_id = ?",
                    (rb_id,)
                ).fetchone()
                
                # Determine if part should be ignored in inventory
                # Priority: preserve existing manual override, then apply default rules
                if existing_part and existing_part[0] == 1:
                    # Part already marked to ignore - preserve this (user may have manually set it)
                    ignore_in_inventory = 1
                else:
                    # Apply default rules for new parts or parts not yet marked
                    ignore_in_inventory = 0
                    if part_category_id == 327:  # Sticker sheet category
                        ignore_in_inventory = 1
                    elif rb_id in ("902221", "902222"):  # Specific parts to ignore
                        ignore_in_inventory = 1
                
                # Track unique parts for category fetching
                if rb_id not in seen_part_ids:
                    seen_part_ids.add(rb_id)
                
                # Deterministic fallback for part_url if missing (safe canonical URL)
                if part_url is None:
                    part_url = f"https://rebrickable.com/parts/{rb_id}/"
                # Opportunistically backfill part metadata
                # Only update ignore_in_inventory if it changed (to avoid unnecessary updates)
                cursor.execute(
                    """
                    UPDATE parts
                    SET name = COALESCE(?, name),
                        part_url = COALESCE(?, part_url),
                        part_img_url = COALESCE(?, part_img_url),
                        ignore_in_inventory = ?
                    WHERE design_id = ?
                    """,
                    (name, part_url, part_img_url, ignore_in_inventory, rb_id),
                )
                if not insert_only_set_parts:
                    # Ensure the part exists
                    if rb_id not in seen_parts:
                        try:
                            cursor.execute(
                                "INSERT OR IGNORE INTO parts (design_id, name, ignore_in_inventory) VALUES (?, ?, ?)",
                                (rb_id, name, ignore_in_inventory),
                            )
                            if cursor.rowcount == 1:
                                new_parts += 1
                                seen_parts.add(rb_id)
                        except sqlite3.IntegrityError as e:
                            print(f"Error inserting part {rb_id}: {e}")
                    # Insert BrickLink aliases if present
                    # Only store if different from design_id (skip self-referential aliases)
                    external_ids = part.get("external_ids", {})
                    for bl in external_ids.get("BrickLink", []):
                        bl_str = str(bl)
                        # Only store if it's different from the design_id and looks like a valid part ID
                        if bl_str != rb_id and len(bl_str) >= 2 and bl_str not in seen_aliases:
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
                    
                    # Insert alternate Rebrickable part IDs from LEGO external_ids
                    # These are alternate part numbers that refer to the same physical part
                    # Only store if different from design_id (skip self-referential aliases)
                    # LEGO is a list, not a dict with ext_ids
                    lego_ids = external_ids.get("LEGO", [])
                    for alt_id in lego_ids:
                        alt_id_str = str(alt_id)
                        # Only store if it's different from the design_id and looks like a valid part ID
                        if alt_id_str != rb_id and len(alt_id_str) >= 2 and alt_id_str not in seen_aliases:
                            try:
                                cursor.execute(
                                    "INSERT OR IGNORE INTO part_aliases (alias, design_id) VALUES (?, ?)",
                                    (alt_id_str, rb_id),
                                )
                                if cursor.rowcount == 1:
                                    new_aliases += 1
                                    seen_aliases.add(alt_id_str)
                            except sqlite3.IntegrityError as e:
                                print(f"Error inserting alternate ID {alt_id_str} → {rb_id}: {e}")

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
            
            # Note: Category fetching is now done separately via load_all_part_categories.py
            # This avoids making individual API calls for each part during set processing,
            # which was causing the script to be very slow
            
            # Commit after inserting all parts for this set
            conn.commit()
            sets_processed += 1
            print(f"✅ Completed set {set_num}")
        except Exception as e:
            # If a set fails, we've already committed the deletion, so we can't rollback
            # But at least we only lost data for this one set, not all sets
            import traceback
            print(f"❌ Error processing set {set_num}: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            print(f"   Continuing with remaining sets...")
            # Try to commit any partial work (though this set's parts are lost)
            try:
                conn.commit()
            except Exception:
                pass
            continue
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
    parser = argparse.ArgumentParser(
        description="Load your owned sets' parts from Rebrickable into the local database."
    )
    parser.add_argument(
        "--only-set-parts",
        action="store_true",
        help="Skip inserting new parts/aliases; update set_parts only.",
    )
    parser.add_argument(
        "--exclude-spares", action="store_true", help="Do not include spare/extra parts."
    )
    parser.add_argument(
        "--exclude-minifig-parts",
        action="store_true",
        help="Do not include minifig component parts.",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Skip deleting existing set_parts for owned sets before reloading.",
    )
    parser.add_argument(
        "--all-sets",
        action="store_true",
        help="Load parts for all sets, even if they already have parts in the database. By default, only processes sets that don't have parts yet.",
    )
    parser.add_argument(
        "--backfill-all-parts",
        action="store_true",
        help="Backfill part URLs/images for parts missing metadata and exit.",
    )
    parser.add_argument(
        "--backfill-alternate-ids",
        action="store_true",
        help="Backfill alternate Rebrickable part IDs for all parts and exit.",
    )
    args = parser.parse_args()

    user_token = get_user_token()

    # Open DB connection
    if not Path(SETTINGS.db_path).exists():
        print(f"Error: database file {SETTINGS.db_path} not found.", file=sys.stderr)
        sys.exit(1)

    with _connect() as conn:
        # Flags
        if args.backfill_all_parts:
            backfill_all_parts(conn)
            return
        
        if args.backfill_alternate_ids:
            backfill_alternate_ids(conn)
            return

        # Fetch your sets and insert part mappings
        all_sets = fetch_owned_sets(user_token)
        
        # Filter to only new sets (sets without parts) unless --all-sets is specified
        if not args.all_sets:
            cursor = conn.cursor()
            sets_with_parts = {
                row[0]
                for row in cursor.execute(
                    "SELECT DISTINCT set_num FROM set_parts"
                ).fetchall()
            }
            sets = [s for s in all_sets if s not in sets_with_parts]
            print(f"Found {len(sets)} new sets (out of {len(all_sets)} total) that need parts loaded.")
        else:
            sets = all_sets
            print(f"Processing all {len(sets)} sets.")
        
        if not sets:
            print("No sets to process.")
            return
        
        insert_only_set_parts = args.only_set_parts
        include_spares = not args.exclude_spares
        include_minifig_parts = not args.exclude_minifig_parts

        # Process sets - deletion happens per-set before insertion to minimize data loss risk
        gather_and_insert_parts(
            sets,
            conn,
            insert_only_set_parts=insert_only_set_parts,
            include_spares=include_spares,
            include_minifig_parts=include_minifig_parts,
            skip_refresh=args.skip_refresh,
        )


if __name__ == "__main__":
    main()
