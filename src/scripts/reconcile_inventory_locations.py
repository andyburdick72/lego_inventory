#!/usr/bin/env python3
"""Script to reconcile inventory locations according to the rules:

1. Loose inventory (excluding Put Away bin) should match Loose Parts sets
2. Put Away bin should match Teardown sets
3. Sets with other statuses (built, in_box, wip) should NOT be in loose inventory
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.di import (
    _DrawersRepoAdapter,
    _InventoryRepoAdapter,
    _SetPartsRepoAdapter,
    _SetsRepoAdapter,
)
from core.services.location_reconciliation_service import LocationReconciliationService
from infra.db.inventory_db import _connect
from infra.db.repositories.drawers_repo import DrawersRepo
from infra.db.repositories.inventory_repo import InventoryRepo
from infra.db.repositories.sets_repo import SetsRepo as SetsRepoImpl


def get_putaway_bin_id(conn: sqlite3.Connection) -> int | None:
    """Get the putaway bin container_id."""
    repo = DrawersRepo(conn)
    putaway = repo.get_put_away_bin()
    if putaway:
        return putaway.get("container_id")
    return None


def get_all_set_parts_by_status(conn: sqlite3.Connection) -> dict:
    """Get all set parts grouped by set status.

    Returns: {
        'loose_parts': {(design_id, color_id): quantity},
        'teardown': {(design_id, color_id): quantity},
        'other': {(design_id, color_id): quantity}  # built, in_box, wip
    }
    """
    result = {
        "loose_parts": {},
        "teardown": {},
        "other": {},
    }

    # Get all sets with their statuses
    sets = conn.execute(
        """
        SELECT set_num, status FROM sets
        """
    ).fetchall()

    for set_row in sets:
        set_num = set_row[0] if isinstance(set_row, tuple) else set_row["set_num"]
        status = (set_row[1] if isinstance(set_row, tuple) else set_row["status"] or "").lower()

        # Get parts for this set
        parts = conn.execute(
            """
            SELECT sp.design_id, sp.color_id, sp.quantity, p.ignore_in_inventory
            FROM set_parts sp
            LEFT JOIN parts p ON p.design_id = sp.design_id
            WHERE sp.set_num = ?
            """,
            (set_num,),
        ).fetchall()

        for part_row in parts:
            if isinstance(part_row, tuple):
                design_id = part_row[0]
                color_id = part_row[1]
                quantity = part_row[2]
                ignore = part_row[3] if len(part_row) > 3 else 0
            else:
                design_id = part_row["design_id"]
                color_id = part_row["color_id"]
                quantity = part_row["quantity"]
                ignore = (
                    part_row.get("ignore_in_inventory", 0)
                    if isinstance(part_row, dict)
                    else (
                        part_row["ignore_in_inventory"]
                        if "ignore_in_inventory" in part_row.keys()
                        else 0
                    )
                )

            # Skip parts flagged to ignore
            if ignore == 1:
                continue

            key = (design_id, color_id)

            if status == "loose_parts":
                result["loose_parts"][key] = result["loose_parts"].get(key, 0) + quantity
            elif status == "teardown":
                result["teardown"][key] = result["teardown"].get(key, 0) + quantity
            else:
                # built, in_box, wip, etc.
                result["other"][key] = result["other"].get(key, 0) + quantity

    return result


def get_current_inventory_by_location(conn: sqlite3.Connection, putaway_bin_id: int) -> dict:
    """Get current inventory grouped by location.

    Returns: {
        'putaway_bin': {(design_id, color_id): quantity},
        'loose_inventory': {(design_id, color_id): quantity},
        'other_status': {(design_id, color_id): quantity}  # non-loose status
    }
    """
    result = {
        "putaway_bin": {},
        "loose_inventory": {},
        "other_status": {},
    }

    # Get all loose inventory
    inventory = conn.execute(
        """
        SELECT i.design_id, i.color_id, i.quantity, i.container_id, i.status
        FROM inventory i
        WHERE i.status = 'loose'
        """
    ).fetchall()

    for inv_row in inventory:
        design_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["design_id"]
        color_id = inv_row[1] if isinstance(inv_row, tuple) else inv_row["color_id"]
        quantity = inv_row[2] if isinstance(inv_row, tuple) else inv_row["quantity"]
        container_id = inv_row[3] if isinstance(inv_row, tuple) else inv_row["container_id"]

        key = (design_id, color_id)

        if container_id == putaway_bin_id:
            result["putaway_bin"][key] = result["putaway_bin"].get(key, 0) + quantity
        else:
            result["loose_inventory"][key] = result["loose_inventory"].get(key, 0) + quantity

    # Get non-loose inventory (shouldn't exist, but check anyway)
    other_inv = conn.execute(
        """
        SELECT i.design_id, i.color_id, i.quantity
        FROM inventory i
        WHERE i.status != 'loose'
        """
    ).fetchall()

    for inv_row in other_inv:
        design_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["design_id"]
        color_id = inv_row[1] if isinstance(inv_row, tuple) else inv_row["color_id"]
        quantity = inv_row[2] if isinstance(inv_row, tuple) else inv_row["quantity"]
        key = (design_id, color_id)
        result["other_status"][key] = result["other_status"].get(key, 0) + quantity

    return result


def reconcile_inventory(
    conn: sqlite3.Connection, putaway_bin_id: int, dry_run: bool = False
) -> dict:
    """Reconcile inventory to match the rules.

    Returns stats about what was changed.
    """
    stats = {
        "deleted_from_other_sets": 0,
        "moved_to_putaway": 0,
        "moved_from_putaway": 0,
        "created_in_putaway": 0,
        "created_in_loose": 0,
        "updated_quantities": 0,
    }

    # Get required quantities
    required = get_all_set_parts_by_status(conn)

    # Get current inventory
    current = get_current_inventory_by_location(conn, putaway_bin_id)

    # Step 1: Remove inventory for parts that belong to other sets (built, in_box, wip)
    # These should NOT be in loose inventory at all
    for (design_id, color_id), qty in required["other"].items():
        # Find and delete all inventory items for this part+color
        inv_items = conn.execute(
            """
            SELECT i.id, i.quantity, i.container_id
            FROM inventory i
            WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
            """,
            (design_id, color_id),
        ).fetchall()

        for inv_row in inv_items:
            inv_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["id"]
            if not dry_run:
                conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
            stats["deleted_from_other_sets"] += 1

    # Step 2: Ensure Put Away bin matches Teardown sets
    for (design_id, color_id), required_qty in required["teardown"].items():
        current_qty = current["putaway_bin"].get((design_id, color_id), 0)

        if current_qty < required_qty:
            # Need to add/move items to putaway bin
            needed = required_qty - current_qty

            # First, try to move from loose inventory
            loose_items = conn.execute(
                """
                SELECT i.id, i.quantity
                FROM inventory i
                WHERE i.design_id = ? AND i.color_id = ? 
                  AND i.status = 'loose' 
                  AND (i.container_id IS NULL OR i.container_id != ?)
                ORDER BY i.quantity DESC
                """,
                (design_id, color_id, putaway_bin_id),
            ).fetchall()

            for inv_row in loose_items:
                if needed <= 0:
                    break
                inv_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["id"]
                qty = inv_row[1] if isinstance(inv_row, tuple) else inv_row["quantity"]

                if not dry_run:
                    conn.execute(
                        "UPDATE inventory SET container_id = ? WHERE id = ?",
                        (putaway_bin_id, inv_id),
                    )
                stats["moved_to_putaway"] += 1
                needed -= qty

            # If still needed, create new inventory in putaway bin
            if needed > 0:
                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                        VALUES (?, ?, ?, 'loose', ?)
                        """,
                        (design_id, color_id, needed, putaway_bin_id),
                    )
                stats["created_in_putaway"] += 1

        elif current_qty > required_qty:
            # Too many in putaway bin - move excess to loose inventory
            excess = current_qty - required_qty

            putaway_items = conn.execute(
                """
                SELECT i.id, i.quantity
                FROM inventory i
                WHERE i.design_id = ? AND i.color_id = ?
                  AND i.status = 'loose' AND i.container_id = ?
                ORDER BY i.quantity DESC
                """,
                (design_id, color_id, putaway_bin_id),
            ).fetchall()

            for inv_row in putaway_items:
                if excess <= 0:
                    break
                inv_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["id"]
                qty = inv_row[1] if isinstance(inv_row, tuple) else inv_row["quantity"]

                if qty <= excess:
                    # Move entire item
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET container_id = NULL WHERE id = ?",
                            (inv_id,),
                        )
                    stats["moved_from_putaway"] += 1
                    excess -= qty
                else:
                    # Split item - reduce quantity
                    new_qty = qty - excess
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET quantity = ? WHERE id = ?",
                            (new_qty, inv_id),
                        )
                        # Create new item with excess
                        conn.execute(
                            """
                            INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                            VALUES (?, ?, ?, 'loose', NULL)
                            """,
                            (design_id, color_id, excess),
                        )
                    stats["updated_quantities"] += 1
                    excess = 0

    # Step 3: Ensure loose inventory (not in putaway) matches Loose Parts sets
    # Note: A part can be in both Loose Parts AND Teardown sets, so we need to handle that
    # We only want Loose Parts quantity in loose inventory (not in putaway)
    for (design_id, color_id), required_qty in required["loose_parts"].items():
        # Get current quantity in loose inventory (not putaway)
        current_qty = current["loose_inventory"].get((design_id, color_id), 0)

        if current_qty < required_qty:
            # Need to add items to loose inventory
            needed = required_qty - current_qty

            # Try to move from putaway bin first
            putaway_items = conn.execute(
                """
                SELECT i.id, i.quantity
                FROM inventory i
                WHERE i.design_id = ? AND i.color_id = ?
                  AND i.status = 'loose' AND i.container_id = ?
                ORDER BY i.quantity DESC
                """,
                (design_id, color_id, putaway_bin_id),
            ).fetchall()

            for inv_row in putaway_items:
                if needed <= 0:
                    break
                inv_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["id"]
                qty = inv_row[1] if isinstance(inv_row, tuple) else inv_row["quantity"]

                if not dry_run:
                    conn.execute(
                        "UPDATE inventory SET container_id = NULL WHERE id = ?",
                        (inv_id,),
                    )
                stats["moved_from_putaway"] += 1
                needed -= qty

            # If still needed, create new inventory
            if needed > 0:
                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                        VALUES (?, ?, ?, 'loose', NULL)
                        """,
                        (design_id, color_id, needed),
                    )
                stats["created_in_loose"] += 1

        elif current_qty > required_qty:
            # Too many in loose inventory - delete excess
            excess = current_qty - required_qty

            loose_items = conn.execute(
                """
                SELECT i.id, i.quantity
                FROM inventory i
                WHERE i.design_id = ? AND i.color_id = ?
                  AND i.status = 'loose'
                  AND (i.container_id IS NULL OR i.container_id != ?)
                ORDER BY i.quantity DESC
                """,
                (design_id, color_id, putaway_bin_id),
            ).fetchall()

            for inv_row in loose_items:
                if excess <= 0:
                    break
                inv_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["id"]
                qty = inv_row[1] if isinstance(inv_row, tuple) else inv_row["quantity"]

                if qty <= excess:
                    # Delete entire item
                    if not dry_run:
                        conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
                    stats["deleted_from_other_sets"] += 1
                    excess -= qty
                else:
                    # Reduce quantity
                    new_qty = qty - excess
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET quantity = ? WHERE id = ?",
                            (new_qty, inv_id),
                        )
                    stats["updated_quantities"] += 1
                    excess = 0

    # Step 4: Remove any inventory that doesn't belong to Loose Parts or Teardown sets
    # This catches parts that are ONLY in "other" sets or have excess inventory
    all_required_keys = set(required["loose_parts"].keys()) | set(required["teardown"].keys())

    # Get all inventory items
    all_inventory = conn.execute(
        """
        SELECT i.id, i.design_id, i.color_id, i.quantity, i.container_id
        FROM inventory i
        WHERE i.status = 'loose'
        """
    ).fetchall()

    for inv_row in all_inventory:
        inv_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["id"]
        design_id = inv_row[1] if isinstance(inv_row, tuple) else inv_row["design_id"]
        color_id = inv_row[2] if isinstance(inv_row, tuple) else inv_row["color_id"]
        qty = inv_row[3] if isinstance(inv_row, tuple) else inv_row["quantity"]
        container_id = inv_row[4] if isinstance(inv_row, tuple) else inv_row["container_id"]

        key = (design_id, color_id)

        # Check if this part should be in inventory at all
        loose_required = required["loose_parts"].get(key, 0)
        teardown_required = required["teardown"].get(key, 0)

        if key not in all_required_keys:
            # Part doesn't belong to any Loose Parts or Teardown set - delete it
            if not dry_run:
                conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
            stats["deleted_from_other_sets"] += 1
            continue

        # Check if quantity is correct for location
        if container_id == putaway_bin_id:
            # Should match teardown requirement
            if qty > teardown_required:
                # Excess in putaway - this will be handled by step 2, but let's be safe
                excess = qty - teardown_required
                if excess >= qty:
                    # Delete entire item if it's all excess
                    if not dry_run:
                        conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
                    stats["deleted_from_other_sets"] += 1
                else:
                    # Reduce quantity
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET quantity = ? WHERE id = ?",
                            (teardown_required, inv_id),
                        )
                    stats["updated_quantities"] += 1
        else:
            # Should match loose parts requirement
            if qty > loose_required:
                # Excess in loose - delete excess
                excess = qty - loose_required
                if excess >= qty:
                    # Delete entire item
                    if not dry_run:
                        conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
                    stats["deleted_from_other_sets"] += 1
                else:
                    # Reduce quantity
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET quantity = ? WHERE id = ?",
                            (loose_required, inv_id),
                        )
                    stats["updated_quantities"] += 1

    if not dry_run:
        conn.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Reconcile inventory locations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually fix the inventory",
    )
    args = parser.parse_args()

    if not args.fix and not args.dry_run:
        print("❌ ERROR: Must specify either --dry-run or --fix")
        return 1

    with _connect() as conn:
        # Get putaway bin
        putaway_bin_id = get_putaway_bin_id(conn)
        if not putaway_bin_id:
            print("❌ ERROR: Putaway bin not configured!")
            return 1

        print(f"✅ Putaway bin container_id: {putaway_bin_id}\n")

        # Get required quantities
        required = get_all_set_parts_by_status(conn)
        print("📊 Required quantities:")
        print(f"   Loose Parts sets: {len(required['loose_parts'])} part/color combinations")
        print(f"   Teardown sets: {len(required['teardown'])} part/color combinations")
        print(f"   Other sets (built/in_box/wip): {len(required['other'])} part/color combinations")

        # Get current inventory
        current = get_current_inventory_by_location(conn, putaway_bin_id)
        print("\n📦 Current inventory:")
        print(f"   Put Away bin: {len(current['putaway_bin'])} part/color combinations")
        print(f"   Loose inventory: {len(current['loose_inventory'])} part/color combinations")
        print(f"   Other status: {len(current['other_status'])} part/color combinations")

        # Reconcile
        mode = "DRY RUN" if args.dry_run else "FIXING"
        print(f"\n🔧 {mode}...")
        stats = reconcile_inventory(conn, putaway_bin_id, dry_run=args.dry_run)

        print("\n📈 Changes:")
        for key, value in stats.items():
            if value > 0:
                print(f"   {key}: {value}")

        if args.dry_run:
            print("\n💡 Run with --fix to apply these changes")
        else:
            print("\n✅ Inventory reconciled!")

            # Check Location Reconciliation
            sets_impl = SetsRepoImpl(conn)
            inventory_impl = InventoryRepo(conn)
            drawers_impl = DrawersRepo(conn)

            sets = _SetsRepoAdapter(sets_impl)
            set_parts = _SetPartsRepoAdapter(sets_impl)
            inventory = _InventoryRepoAdapter(inventory_impl)
            drawers = _DrawersRepoAdapter(drawers_impl)

            service = LocationReconciliationService(
                sets=sets,
                set_parts=set_parts,
                inventory=inventory,
                drawers=drawers,
            )

            loose_items = service.compute_loose_parts_reconciliation_items()
            teardown_items = service.compute_teardown_reconciliation_items()

            print("\n🔍 Location Reconciliation after fix:")
            print(f"   Loose Parts: {len(loose_items)} items")
            print(f"   Teardown: {len(teardown_items)} items")
            print(f"   Total: {len(loose_items) + len(teardown_items)} items")

            if len(loose_items) == 0 and len(teardown_items) == 0:
                print("   ✅ Perfect! All reconciled!")
            else:
                print("   ⚠️  Still some items to reconcile")

    return 0


if __name__ == "__main__":
    sys.exit(main())
