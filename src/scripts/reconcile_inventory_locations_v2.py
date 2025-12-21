#!/usr/bin/env python3
"""Script to reconcile inventory locations by rebuilding from scratch.

Rules:
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

from infra.db.inventory_db import _connect
from infra.db.repositories.drawers_repo import DrawersRepo


def get_putaway_bin_id(conn: sqlite3.Connection) -> int | None:
    """Get the putaway bin container_id."""
    repo = DrawersRepo(conn)
    putaway = repo.get_put_away_bin()
    if putaway:
        return putaway.get("container_id")
    return None


def get_required_quantities(conn: sqlite3.Connection) -> tuple[dict, dict]:
    """Get required quantities for Loose Parts and Teardown sets.

    Returns: (loose_parts_map, teardown_map)
    where each map is {(design_id, color_id): quantity}
    """
    loose_parts = {}
    teardown = {}

    # Get all sets with their statuses
    sets = conn.execute("SELECT set_num, status FROM sets").fetchall()

    for set_row in sets:
        if isinstance(set_row, tuple):
            set_num = set_row[0]
            status = (set_row[1] or "").lower()
        else:
            set_num = set_row["set_num"]
            status = (set_row["status"] if "status" in set_row.keys() else "").lower()

        # Get parts for this set
        parts = conn.execute(
            """
            SELECT sp.design_id, sp.color_id, sp.quantity, COALESCE(p.ignore_in_inventory, 0) as ignore
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
                    part_row.get("ignore", 0)
                    if isinstance(part_row, dict)
                    else (part_row["ignore"] if "ignore" in part_row.keys() else 0)
                )

            if ignore == 1:
                continue

            key = (design_id, color_id)

            if status == "loose_parts":
                loose_parts[key] = loose_parts.get(key, 0) + quantity
            elif status == "teardown":
                teardown[key] = teardown.get(key, 0) + quantity

    return loose_parts, teardown


def get_existing_container_assignments(conn: sqlite3.Connection, putaway_bin_id: int) -> dict:
    """Get existing container assignments for parts before deleting.

    Returns: {(design_id, color_id): container_id}
    Only includes assignments that are NOT in putaway bin.
    """
    assignments = {}

    existing = conn.execute(
        """
        SELECT i.design_id, i.color_id, i.container_id
        FROM inventory i
        WHERE i.status = 'loose'
          AND i.container_id IS NOT NULL
          AND i.container_id != ?
        GROUP BY i.design_id, i.color_id, i.container_id
        """,
        (putaway_bin_id,),
    ).fetchall()

    for row in existing:
        if isinstance(row, tuple):
            design_id = row[0]
            color_id = row[1]
            container_id = row[2]
        else:
            design_id = row["design_id"]
            color_id = row["color_id"]
            container_id = row["container_id"]

        key = (design_id, color_id)
        # Use the first container we find for this part+color
        if key not in assignments:
            assignments[key] = container_id

    return assignments


def rebuild_inventory(conn: sqlite3.Connection, putaway_bin_id: int, dry_run: bool = False) -> dict:
    """Rebuild inventory from scratch based on requirements.

    Preserves existing container assignments when possible.

    Returns stats about what was done.
    """
    stats = {
        "deleted": 0,
        "created_putaway": 0,
        "created_loose": 0,
        "preserved_assignments": 0,
    }

    # Get required quantities
    loose_parts, teardown = get_required_quantities(conn)

    # Get existing container assignments before deleting
    existing_assignments = (
        get_existing_container_assignments(conn, putaway_bin_id) if not dry_run else {}
    )

    # Step 1: Delete ALL existing loose inventory
    if not dry_run:
        deleted = conn.execute("DELETE FROM inventory WHERE status = 'loose'").rowcount
        stats["deleted"] = deleted
        conn.commit()
    else:
        count = conn.execute("SELECT COUNT(*) FROM inventory WHERE status = 'loose'").fetchone()[0]
        stats["deleted"] = count if isinstance(count, int) else count[0]

    # Step 2: Create inventory for Teardown sets in Put Away bin
    for (design_id, color_id), quantity in teardown.items():
        if not dry_run:
            conn.execute(
                """
                INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                VALUES (?, ?, ?, 'loose', ?)
                """,
                (design_id, color_id, quantity, putaway_bin_id),
            )
        stats["created_putaway"] += 1

    # Step 3: Create inventory for Loose Parts sets (not in putaway bin)
    # Use existing container assignments when available
    for (design_id, color_id), quantity in loose_parts.items():
        key = (design_id, color_id)
        container_id = existing_assignments.get(key)

        if not dry_run:
            conn.execute(
                """
                INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                VALUES (?, ?, ?, 'loose', ?)
                """,
                (design_id, color_id, quantity, container_id),
            )

        if container_id:
            stats["preserved_assignments"] += 1

        stats["created_loose"] += 1

    if not dry_run:
        conn.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Rebuild inventory from scratch")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually rebuild the inventory",
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
        loose_parts, teardown = get_required_quantities(conn)
        print("📊 Required quantities:")
        print(f"   Loose Parts sets: {len(loose_parts)} part/color combinations")
        print(f"   Teardown sets: {len(teardown)} part/color combinations")

        # Get current inventory count
        current_count = conn.execute(
            "SELECT COUNT(*) FROM inventory WHERE status = 'loose'"
        ).fetchone()
        current = current_count[0] if isinstance(current_count, tuple) else current_count
        print(f"\n📦 Current loose inventory: {current} items")

        # Rebuild
        mode = "DRY RUN" if args.dry_run else "REBUILDING"
        print(f"\n🔧 {mode}...")
        stats = rebuild_inventory(conn, putaway_bin_id, dry_run=args.dry_run)

        print("\n📈 Changes:")
        print(f"   Deleted: {stats['deleted']} items")
        print(f"   Created in Put Away bin: {stats['created_putaway']} items")
        print(f"   Created in loose inventory: {stats['created_loose']} items")
        print(f"   Preserved container assignments: {stats['preserved_assignments']} items")
        unassigned = stats["created_loose"] - stats["preserved_assignments"]
        if unassigned > 0:
            print(f"   ⚠️  {unassigned} items in loose inventory need container assignment")

        if args.dry_run:
            print("\n💡 Run with --fix to apply these changes")
        else:
            print("\n✅ Inventory rebuilt!")

            # Check Location Reconciliation
            from app.di import (
                _DrawersRepoAdapter,
                _InventoryRepoAdapter,
                _SetPartsRepoAdapter,
                _SetsRepoAdapter,
            )
            from core.services.location_reconciliation_service import LocationReconciliationService
            from infra.db.repositories.inventory_repo import InventoryRepo
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

            loose_items = service.compute_loose_parts_reconciliation_items()
            teardown_items = service.compute_teardown_reconciliation_items()

            print("\n🔍 Location Reconciliation after rebuild:")
            print(f"   Loose Parts: {len(loose_items)} items")
            print(f"   Teardown: {len(teardown_items)} items")
            print(f"   Total: {len(loose_items) + len(teardown_items)} items")

            if len(loose_items) == 0 and len(teardown_items) == 0:
                print("   ✅ Perfect! All reconciled!")
            else:
                print("   ⚠️  Still some items to reconcile")
                if len(loose_items) > 0:
                    print("\n   Sample Loose Parts issues:")
                    for item in loose_items[:3]:
                        print(
                            f"      {item.get('part_name')} ({item.get('color_name')}): "
                            f"Required {item.get('required_quantity')}, "
                            f"Current {item.get('current_total')}, "
                            f"Delta {item.get('delta')}"
                        )
                if len(teardown_items) > 0:
                    print("\n   Sample Teardown issues:")
                    for item in teardown_items[:3]:
                        print(
                            f"      {item.get('part_name')} ({item.get('color_name')}): "
                            f"Required {item.get('required_quantity')}, "
                            f"Current {item.get('current_total')}, "
                            f"Delta {item.get('delta')}"
                        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
