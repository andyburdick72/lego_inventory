#!/usr/bin/env python3
"""Script to fix the putaway bin issue and investigate the bug.

This script will:
1. Check current state of putaway bin
2. Check Location Reconciliation items
3. Move items from Location Reconciliation back to putaway bin (if needed)
4. Help identify the bug
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


def get_putaway_bin_id(conn: sqlite3.Connection) -> int | None:
    """Get the putaway bin container_id."""
    repo = DrawersRepo(conn)
    putaway = repo.get_put_away_bin()
    if putaway:
        return putaway.get("container_id")
    return None


def get_items_in_putaway_bin(conn: sqlite3.Connection) -> list[dict]:
    """Get all items currently in the putaway bin."""
    repo = InventoryRepo(conn)
    return repo.get_putaway_bin_parts()


def get_location_reconciliation_items(conn: sqlite3.Connection) -> list[dict]:
    """Get all items from Location Reconciliation (loose-parts)."""
    from infra.db.repositories.sets_repo import SetsRepo as SetsRepoImpl

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
    return service.compute_loose_parts_reconciliation_items()


def move_teardown_items_to_putaway_bin(
    conn: sqlite3.Connection, items: list[dict], putaway_bin_id: int
) -> int:
    """Move teardown items from Location Reconciliation back to putaway bin.

    This will update inventory items to have container_id = putaway_bin_id.
    For teardown items, we need to move them FROM their current locations TO putaway bin.
    """
    moved_count = 0

    for item in items:
        design_id = item["design_id"]
        color_id = item["color_id"]
        required_qty = item["required_quantity"]
        current_total = item.get("current_total", 0)  # Current qty in putaway bin
        delta = item.get("delta", 0)  # Positive delta = need more in putaway bin

        if delta <= 0:
            # Already have enough or too many in putaway bin
            continue

        # Get all inventory items for this part+color that are NOT in putaway bin
        inventory_items = conn.execute(
            """
            SELECT i.id, i.quantity, i.container_id
            FROM inventory i
            WHERE i.design_id = ? AND i.color_id = ? AND i.status = 'loose'
              AND (i.container_id IS NULL OR i.container_id != ?)
            ORDER BY i.quantity DESC
            """,
            (design_id, color_id, putaway_bin_id),
        ).fetchall()

        # Move items to putaway bin until we have enough
        total_to_move = delta
        for inv_row in inventory_items:
            if total_to_move <= 0:
                break

            inv_id = inv_row[0] if isinstance(inv_row, tuple) else inv_row["id"]
            qty = inv_row[1] if isinstance(inv_row, tuple) else inv_row["quantity"]
            current_container_id = (
                inv_row[2] if isinstance(inv_row, tuple) else inv_row["container_id"]
            )

            # Move this inventory item to putaway bin
            conn.execute(
                "UPDATE inventory SET container_id = ? WHERE id = ?",
                (putaway_bin_id, inv_id),
            )
            moved_count += 1
            total_to_move -= qty

    conn.commit()
    return moved_count


def main():
    parser = argparse.ArgumentParser(description="Fix putaway bin issue")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually fix the issue by moving items back to putaway bin",
    )
    args = parser.parse_args()

    with _connect() as conn:
        # Get putaway bin
        putaway_bin_id = get_putaway_bin_id(conn)
        if not putaway_bin_id:
            print("❌ ERROR: Putaway bin not configured!")
            return 1

        print(f"✅ Putaway bin container_id: {putaway_bin_id}")

        # Check current state
        items_in_bin = get_items_in_putaway_bin(conn)
        print(f"\n📦 Items currently in putaway bin: {len(items_in_bin)}")

        if items_in_bin:
            print("   Sample items:")
            for item in items_in_bin[:5]:
                print(
                    f"   - {item.get('part_name')} ({item.get('color_name')}) x{item.get('quantity')}"
                )

        # Check Location Reconciliation - loose-parts
        reconciliation_items = get_location_reconciliation_items(conn)
        print(f"\n🔍 Location Reconciliation items (loose-parts): {len(reconciliation_items)}")

        if reconciliation_items:
            print("   Sample items:")
            for item in reconciliation_items[:5]:
                print(
                    f"   - {item.get('part_name')} ({item.get('color_name')}) "
                    f"Required: {item.get('required_quantity')}, "
                    f"Current: {item.get('current_total')}, "
                    f"Delta: {item.get('delta')}"
                )

        # Check Location Reconciliation - teardown (these should be in putaway bin)
        # Create service to get teardown items
        from infra.db.repositories.sets_repo import SetsRepo as SetsRepoImpl

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
        teardown_items = service.compute_teardown_reconciliation_items()
        print(f"\n🔍 Location Reconciliation items (teardown): {len(teardown_items)}")

        if teardown_items:
            print("   Sample items (these SHOULD be in putaway bin):")
            for item in teardown_items[:5]:
                print(
                    f"   - {item.get('part_name')} ({item.get('color_name')}) "
                    f"Required: {item.get('required_quantity')}, "
                    f"Current in Putaway: {item.get('current_total')}, "
                    f"Delta: {item.get('delta')}"
                )

        # Analyze the issue
        print("\n🔬 Analysis:")
        if len(items_in_bin) == 0 and (len(reconciliation_items) > 0 or len(teardown_items) > 0):
            print("   ⚠️  Putaway bin is empty but Location Reconciliation shows items.")
            print("   This suggests items were moved out of putaway bin incorrectly.")

            if args.fix:
                print("\n🔧 Fixing: Moving teardown items back to putaway bin...")
                if not args.dry_run:
                    # Move teardown items back to putaway bin
                    moved = move_teardown_items_to_putaway_bin(conn, teardown_items, putaway_bin_id)
                    print(f"   ✅ Moved {moved} inventory items to putaway bin")
                else:
                    print("   [DRY RUN] Would move teardown items back to putaway bin")
            else:
                print("   💡 Run with --fix to move teardown items back to putaway bin")
        elif len(items_in_bin) > 0 and len(reconciliation_items) == 0:
            print("   ✅ Putaway bin has items and Location Reconciliation is clean.")
        else:
            print("   ⚠️  Mixed state - needs investigation")

    return 0


if __name__ == "__main__":
    sys.exit(main())
