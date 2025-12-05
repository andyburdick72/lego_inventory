#!/usr/bin/env python3
"""
Sanity check and migration script for loose parts and teardown sets.

This script:
1. Checks that quantities in inventory table align with loose_parts set parts
2. Adds all teardown set parts to inventory table in drawer 53
"""

import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Add repo root to path
_ROOT = Path(__file__).resolve().parents[1]  # repo root containing 'src'
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.settings import get_settings  # noqa: E402
from infra.db.inventory_db import _connect  # noqa: E402

SETTINGS = get_settings()


def sync_loose_parts_to_inventory(conn: sqlite3.Connection) -> dict:
    """
    Sync inventory to match loose_parts set_parts quantities.
    Uses set_parts as source of truth.
    Only prompts user if part+color exists in multiple containers.
    """
    print("=" * 60)
    print("SYNC: Loose Parts to Inventory")
    print("=" * 60)

    # Get aggregated quantities from set_parts for loose_parts sets
    # Exclude sticker sheets (parts with "Sticker Sheet" in the name)
    set_parts_query = """
        SELECT 
            sp.design_id,
            sp.color_id,
            SUM(sp.quantity) as set_parts_qty
        FROM set_parts sp
        JOIN sets s ON s.set_num = sp.set_num
        LEFT JOIN parts p ON p.design_id = sp.design_id
        WHERE s.status = 'loose_parts'
          AND (p.name IS NULL OR p.name NOT LIKE '%Sticker Sheet%')
        GROUP BY sp.design_id, sp.color_id
    """

    set_parts_rows = conn.execute(set_parts_query).fetchall()
    set_parts_dict = {
        (row["design_id"], row["color_id"]): row["set_parts_qty"] for row in set_parts_rows
    }

    print(f"\nFound {len(set_parts_dict)} part+color combinations in loose_parts sets")

    # Get current inventory locations for each part+color
    # Exclude drawer 53 / container "All" (teardown storage only)
    inventory_locations_query = """
        SELECT 
            i.design_id,
            i.color_id,
            i.container_id,
            c.name as container_name,
            d.id as drawer_id,
            d.name as drawer_name,
            SUM(i.quantity) as qty_in_container
        FROM inventory i
        LEFT JOIN containers c ON c.id = i.container_id
        LEFT JOIN drawers d ON d.id = c.drawer_id
        WHERE i.status = 'loose'
          AND NOT (d.id = 53 AND c.name = 'All')
        GROUP BY i.design_id, i.color_id, i.container_id, c.name, d.id, d.name
    """

    inventory_locations = conn.execute(inventory_locations_query).fetchall()

    # Group by part+color to see which containers they're in
    part_color_locations = defaultdict(list)
    for row in inventory_locations:
        key = (row["design_id"], row["color_id"])
        part_color_locations[key].append(
            {
                "container_id": row["container_id"],
                "container_name": row["container_name"],
                "drawer_id": row["drawer_id"],
                "drawer_name": row["drawer_name"],
                "quantity": row["qty_in_container"],
            }
        )

    print(f"Found {len(part_color_locations)} part+color combinations currently in inventory")

    # Process each part+color from set_parts
    needs_decision = []
    updates_made = 0
    total_qty_updated = 0

    conn.execute("BEGIN")
    try:
        for (design_id, color_id), target_qty in set_parts_dict.items():
            locations = part_color_locations.get((design_id, color_id), [])
            current_total = sum(loc["quantity"] for loc in locations)

            # If quantities already match, skip
            if current_total == target_qty:
                continue

            # Determine where to put/update this part+color
            if len(locations) == 0:
                # Not in inventory - needs decision on where to put it
                needs_decision.append(
                    {
                        "design_id": design_id,
                        "color_id": color_id,
                        "target_qty": target_qty,
                        "reason": "not_in_inventory",
                    }
                )
            elif len(locations) == 1:
                # In exactly one container - update that container
                loc = locations[0]
                if loc["container_id"]:
                    # Update existing entry in that container
                    conn.execute(
                        """
                        UPDATE inventory
                        SET quantity = ?
                        WHERE design_id = ? 
                          AND color_id = ? 
                          AND container_id = ?
                          AND status = 'loose'
                        """,
                        (target_qty, design_id, color_id, loc["container_id"]),
                    )
                    updates_made += 1
                    total_qty_updated += target_qty
                else:
                    # Has location but no container_id (legacy) - needs decision
                    needs_decision.append(
                        {
                            "design_id": design_id,
                            "color_id": color_id,
                            "target_qty": target_qty,
                            "current_locations": locations,
                            "reason": "legacy_location",
                        }
                    )
            else:
                # In multiple containers - needs decision (unclear where to put it)
                needs_decision.append(
                    {
                        "design_id": design_id,
                        "color_id": color_id,
                        "target_qty": target_qty,
                        "current_locations": locations,
                        "reason": "multiple_containers",
                    }
                )

        conn.commit()

        print(f"\n✅ Auto-updated {updates_made} part+color combinations")
        print(f"   Total quantity updated: {total_qty_updated:,}")
        if needs_decision:
            print(f"\n⚠️  Need decision for {len(needs_decision)} part+color combinations")

        if needs_decision:
            print("\n--- Items needing decision (first 20) ---")
            for item in needs_decision[:20]:
                print(
                    f"  {item['design_id']} / color {item['color_id']}: target={item['target_qty']}, reason={item['reason']}"
                )
                if "current_locations" in item:
                    for loc in item["current_locations"]:
                        drawer = loc["drawer_name"] or f"drawer_{loc['drawer_id']}"
                        container = loc["container_name"] or "unknown"
                        print(f"    - {drawer} / {container}: {loc['quantity']}")
            
            # Export full list to CSV
            export_path = Path(SETTINGS.reports_dir) / "loose_parts_needing_decision.csv"
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "design_id",
                    "color_id",
                    "target_quantity",
                    "reason",
                    "current_locations"
                ])
                
                for item in needs_decision:
                    locations_str = ""
                    if "current_locations" in item:
                        loc_parts = []
                        for loc in item["current_locations"]:
                            drawer = loc["drawer_name"] or f"drawer_{loc['drawer_id']}"
                            container = loc["container_name"] or "unknown"
                            loc_parts.append(f"{drawer} / {container}: {loc['quantity']}")
                        locations_str = " | ".join(loc_parts)
                    
                    writer.writerow([
                        item["design_id"],
                        item["color_id"],
                        item["target_qty"],
                        item["reason"],
                        locations_str
                    ])
            
            print(f"\n📄 Full list exported to: {export_path}")

        return {
            "updates_made": updates_made,
            "needs_decision": needs_decision,
            "total_qty_updated": total_qty_updated,
        }

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error syncing loose parts: {e}")
        raise


def check_loose_parts_alignment(conn: sqlite3.Connection) -> dict:
    """
    Check if loose_parts set_parts quantities match inventory quantities.
    Returns a dict with mismatch details.
    """
    print("=" * 60)
    print("SANITY CHECK: Loose Parts Alignment")
    print("=" * 60)

    # Get aggregated quantities from set_parts for loose_parts sets
    set_parts_query = """
        SELECT 
            sp.design_id,
            sp.color_id,
            SUM(sp.quantity) as set_parts_qty
        FROM set_parts sp
        JOIN sets s ON s.set_num = sp.set_num
        WHERE s.status = 'loose_parts'
        GROUP BY sp.design_id, sp.color_id
    """

    set_parts_rows = conn.execute(set_parts_query).fetchall()
    set_parts_dict = {
        (row["design_id"], row["color_id"]): row["set_parts_qty"] for row in set_parts_rows
    }

    # Get aggregated quantities from inventory
    inventory_query = """
        SELECT 
            i.design_id,
            i.color_id,
            SUM(i.quantity) as inventory_qty
        FROM inventory i
        WHERE i.status = 'loose'
        GROUP BY i.design_id, i.color_id
    """

    inventory_rows = conn.execute(inventory_query).fetchall()
    inventory_dict = {
        (row["design_id"], row["color_id"]): row["inventory_qty"] for row in inventory_rows
    }

    # Find mismatches
    all_keys = set(set_parts_dict.keys()) | set(inventory_dict.keys())
    mismatches = []
    missing_in_inventory = []
    extra_in_inventory = []

    for key in all_keys:
        set_qty = set_parts_dict.get(key, 0)
        inv_qty = inventory_dict.get(key, 0)

        if set_qty != inv_qty:
            if key not in inventory_dict:
                missing_in_inventory.append((key[0], key[1], set_qty, 0))
            elif key not in set_parts_dict:
                extra_in_inventory.append((key[0], key[1], 0, inv_qty))
            else:
                mismatches.append((key[0], key[1], set_qty, inv_qty))

    # Print summary
    print(f"\nTotal part+color combinations in loose_parts sets: {len(set_parts_dict)}")
    print(f"Total part+color combinations in inventory: {len(inventory_dict)}")
    print(f"\nMismatches (different quantities): {len(mismatches)}")
    print(f"Missing in inventory: {len(missing_in_inventory)}")
    print(f"Extra in inventory (not in loose_parts sets): {len(extra_in_inventory)}")

    if mismatches:
        print("\n--- Mismatches (first 10) ---")
        for design_id, color_id, set_qty, inv_qty in mismatches[:10]:
            print(f"  {design_id} / color {color_id}: set_parts={set_qty}, inventory={inv_qty}")

    if missing_in_inventory:
        print("\n--- Missing in inventory (first 10) ---")
        for design_id, color_id, set_qty, inv_qty in missing_in_inventory[:10]:
            print(f"  {design_id} / color {color_id}: set_parts={set_qty}, inventory={inv_qty}")

    if extra_in_inventory:
        print("\n--- Extra in inventory (not in loose_parts sets, first 10) ---")
        for design_id, color_id, set_qty, inv_qty in extra_in_inventory[:10]:
            print(f"  {design_id} / color {color_id}: set_parts={set_qty}, inventory={inv_qty}")

    return {
        "mismatches": mismatches,
        "missing_in_inventory": missing_in_inventory,
        "extra_in_inventory": extra_in_inventory,
        "total_mismatches": len(mismatches) + len(missing_in_inventory) + len(extra_in_inventory),
    }


def add_teardown_parts_to_inventory(conn: sqlite3.Connection, drawer_id: int = 53) -> dict:
    """
    Sync teardown set parts to inventory table in the specified drawer.
    Sets quantities to match set_parts (does not add to existing).
    Returns a dict with summary statistics.
    """
    print("\n" + "=" * 60)
    print("SYNC: Teardown Parts to Inventory")
    print("=" * 60)

    # Get drawer 53's "All" container (or create it if needed)
    container_row = conn.execute(
        "SELECT id FROM containers WHERE drawer_id = ? AND name = 'All' AND deleted_at IS NULL",
        (drawer_id,),
    ).fetchone()

    if not container_row:
        # Create "All" container in drawer 53
        cursor = conn.cursor()
        cursor.execute("INSERT INTO containers (drawer_id, name) VALUES (?, 'All')", (drawer_id,))
        container_id = cursor.lastrowid
        print(f"Created container 'All' in drawer {drawer_id} (ID: {container_id})")
    else:
        container_id = container_row["id"] if isinstance(container_row, dict) else container_row[0]
        print(f"Using existing container 'All' in drawer {drawer_id} (ID: {container_id})")

    # Get all teardown set parts
    teardown_parts = conn.execute(
        """
        SELECT 
            sp.set_num,
            sp.design_id,
            sp.color_id,
            sp.quantity
        FROM set_parts sp
        JOIN sets s ON s.set_num = sp.set_num
        WHERE s.status = 'teardown'
        ORDER BY sp.set_num, sp.design_id, sp.color_id
        """
    ).fetchall()

    print(f"\nFound {len(teardown_parts)} part+color entries in teardown sets")

    # Check for existing inventory entries that might conflict
    # We'll aggregate by design_id + color_id and add/update accordingly
    parts_to_add = defaultdict(int)
    for row in teardown_parts:
        key = (row["design_id"], row["color_id"])
        parts_to_add[key] += row["quantity"]

    print(f"Aggregated to {len(parts_to_add)} unique part+color combinations")

    # Add/update inventory entries to match set_parts quantities
    added_count = 0
    updated_count = 0
    unchanged_count = 0
    total_quantity_set = 0

    conn.execute("BEGIN")
    try:
        for (design_id, color_id), target_quantity in parts_to_add.items():
            # Check if this exact part+color already exists in this container
            existing = conn.execute(
                """
                SELECT id, quantity
                FROM inventory
                WHERE design_id = ? 
                  AND color_id = ? 
                  AND container_id = ?
                  AND status = 'loose'
                """,
                (design_id, color_id, container_id),
            ).fetchone()

            if existing:
                # Update existing entry to match target quantity
                existing_id = existing["id"] if isinstance(existing, dict) else existing[0]
                existing_qty = existing["quantity"] if isinstance(existing, dict) else existing[1]

                if existing_qty != target_quantity:
                    conn.execute(
                        "UPDATE inventory SET quantity = ? WHERE id = ?",
                        (target_quantity, existing_id),
                    )
                    updated_count += 1
                    total_quantity_set += target_quantity
                else:
                    unchanged_count += 1
            else:
                # Insert new entry
                conn.execute(
                    """
                    INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                    VALUES (?, ?, ?, 'loose', ?)
                    """,
                    (design_id, color_id, target_quantity, container_id),
                )
                added_count += 1
                total_quantity_set += target_quantity

        conn.commit()
        print("\n✅ Successfully synced teardown parts to inventory:")
        print(f"   - New entries: {added_count}")
        print(f"   - Updated entries: {updated_count}")
        print(f"   - Unchanged entries: {unchanged_count}")
        print(f"   - Total quantity set: {total_quantity_set:,}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error adding teardown parts: {e}")
        raise

    return {
        "added_count": added_count,
        "updated_count": updated_count,
        "unchanged_count": unchanged_count,
        "total_quantity_set": total_quantity_set,
    }


def main():
    """Main entry point."""
    if not Path(SETTINGS.db_path).exists():
        print(f"Error: database file {SETTINGS.db_path} not found.", file=sys.stderr)
        sys.exit(1)

    with _connect() as conn:
        conn.row_factory = sqlite3.Row

        # Step 1: Sync loose parts to inventory (using set_parts as source of truth)
        print("Step 1: Syncing loose parts to inventory...")
        sync_results = sync_loose_parts_to_inventory(conn)

        if sync_results["needs_decision"]:
            print(f"\n⚠️  {len(sync_results['needs_decision'])} items need manual decision")
            print("These will be skipped for now. You can handle them manually.")
        else:
            print("\n✅ All loose parts synced successfully!")

        # Step 2: Add teardown parts
        print("\n" + "=" * 60)
        print("Step 2: Adding teardown parts to inventory...")
        migration_results = add_teardown_parts_to_inventory(conn, drawer_id=53)

        print("\n" + ("=" * 60))
        print("SUMMARY")
        print("=" * 60)
        print(f"Loose parts auto-updated: {sync_results['updates_made']}")
        if sync_results["needs_decision"]:
            print(f"Loose parts needing decision: {len(sync_results['needs_decision'])}")
        print(
            f"Teardown parts synced: {migration_results['added_count']} new, {migration_results['updated_count']} updated, {migration_results['unchanged_count']} unchanged"
        )
        print(f"Total quantity set (teardown): {migration_results['total_quantity_set']:,}")


if __name__ == "__main__":
    main()
