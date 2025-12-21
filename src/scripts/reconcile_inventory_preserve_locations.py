#!/usr/bin/env python3
"""Script to reconcile inventory while preserving existing container assignments.

This script updates quantities and locations to match requirements, but preserves
existing container assignments when possible.
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
                ignore = part_row.get("ignore", 0) if isinstance(part_row, dict) else (part_row["ignore"] if "ignore" in part_row.keys() else 0)
            
            if ignore == 1:
                continue
            
            key = (design_id, color_id)
            
            if status == "loose_parts":
                loose_parts[key] = loose_parts.get(key, 0) + quantity
            elif status == "teardown":
                teardown[key] = teardown.get(key, 0) + quantity
    
    return loose_parts, teardown


def get_existing_inventory(conn: sqlite3.Connection, putaway_bin_id: int) -> dict:
    """Get existing inventory grouped by part+color and location.
    
    Returns: {
        'putaway': {(design_id, color_id): [(inventory_id, quantity, container_id), ...]},
        'loose': {(design_id, color_id): [(inventory_id, quantity, container_id), ...]},
    }
    """
    result = {
        'putaway': {},
        'loose': {},
    }
    
    inventory = conn.execute(
        """
        SELECT i.id, i.design_id, i.color_id, i.quantity, i.container_id
        FROM inventory i
        WHERE i.status = 'loose'
        """
    ).fetchall()
    
    for inv_row in inventory:
        if isinstance(inv_row, tuple):
            inv_id = inv_row[0]
            design_id = inv_row[1]
            color_id = inv_row[2]
            quantity = inv_row[3]
            container_id = inv_row[4]
        else:
            inv_id = inv_row["id"]
            design_id = inv_row["design_id"]
            color_id = inv_row["color_id"]
            quantity = inv_row["quantity"]
            container_id = inv_row["container_id"]
        
        key = (design_id, color_id)
        location = 'putaway' if container_id == putaway_bin_id else 'loose'
        
        if key not in result[location]:
            result[location][key] = []
        result[location][key].append((inv_id, quantity, container_id))
    
    return result


def reconcile_preserving_locations(conn: sqlite3.Connection, putaway_bin_id: int, dry_run: bool = False) -> dict:
    """Reconcile inventory while preserving existing container assignments.
    
    Returns stats about what was changed.
    """
    stats = {
        'deleted': 0,
        'updated_quantities': 0,
        'moved_to_putaway': 0,
        'moved_from_putaway': 0,
        'created_in_putaway': 0,
        'created_in_loose': 0,
        'preserved_assignments': 0,
    }
    
    # Get required quantities
    loose_parts, teardown = get_required_quantities(conn)
    
    # Get existing inventory
    existing = get_existing_inventory(conn, putaway_bin_id)
    
    # Step 1: Handle Teardown sets - ensure they're in Put Away bin
    for (design_id, color_id), required_qty in teardown.items():
        key = (design_id, color_id)
        
        # Get current quantity in putaway
        putaway_items = existing['putaway'].get(key, [])
        current_putaway_qty = sum(qty for _, qty, _ in putaway_items)
        
        # Get current quantity in loose (should be moved to putaway)
        loose_items = existing['loose'].get(key, [])
        current_loose_qty = sum(qty for _, qty, _ in loose_items)
        
        total_current = current_putaway_qty + current_loose_qty
        
        if total_current < required_qty:
            # Need more - move from loose first, then create new
            needed = required_qty - total_current
            
            # Move loose items to putaway
            for inv_id, qty, _ in loose_items:
                if needed <= 0:
                    break
                if not dry_run:
                    conn.execute(
                        "UPDATE inventory SET container_id = ? WHERE id = ?",
                        (putaway_bin_id, inv_id),
                    )
                stats['moved_to_putaway'] += 1
                needed -= qty
            
            # Create new items in putaway if still needed
            if needed > 0:
                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                        VALUES (?, ?, ?, 'loose', ?)
                        """,
                        (design_id, color_id, needed, putaway_bin_id),
                    )
                stats['created_in_putaway'] += 1
        
        elif total_current > required_qty:
            # Too many - reduce quantities, starting with loose items
            excess = total_current - required_qty
            
            # Delete or reduce loose items first
            for inv_id, qty, container_id in loose_items:
                if excess <= 0:
                    break
                if qty <= excess:
                    if not dry_run:
                        conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
                    stats['deleted'] += 1
                    excess -= qty
                else:
                    new_qty = qty - excess
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET quantity = ? WHERE id = ?",
                            (new_qty, inv_id),
                        )
                    stats['updated_quantities'] += 1
                    excess = 0
            
            # Then reduce putaway items
            for inv_id, qty, _ in putaway_items:
                if excess <= 0:
                    break
                if qty <= excess:
                    if not dry_run:
                        conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
                    stats['deleted'] += 1
                    excess -= qty
                else:
                    new_qty = qty - excess
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET quantity = ? WHERE id = ?",
                            (new_qty, inv_id),
                        )
                    stats['updated_quantities'] += 1
                    excess = 0
        
        else:
            # Quantity matches - just ensure location is correct
            # Move any loose items to putaway
            for inv_id, qty, _ in loose_items:
                if not dry_run:
                    conn.execute(
                        "UPDATE inventory SET container_id = ? WHERE id = ?",
                        (putaway_bin_id, inv_id),
                    )
                stats['moved_to_putaway'] += 1
    
    # Step 2: Handle Loose Parts sets - preserve container assignments
    for (design_id, color_id), required_qty in loose_parts.items():
        key = (design_id, color_id)
        
        # Skip if this is also a teardown part (already handled)
        if key in teardown:
            # This part is in both - we need to ensure loose parts quantity is in loose inventory
            # (teardown quantity should already be in putaway from step 1)
            teardown_qty = teardown[key]
            required_loose_qty = required_qty  # This is the loose parts requirement
            
            # Get current loose inventory (excluding putaway)
            loose_items = existing['loose'].get(key, [])
            current_loose_qty = sum(qty for _, qty, _ in loose_items)
            
            if current_loose_qty < required_loose_qty:
                # Need more in loose - create new (can't move from putaway since that's for teardown)
                needed = required_loose_qty - current_loose_qty
                # Try to preserve existing container assignment
                container_id = loose_items[0][2] if loose_items else None
                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                        VALUES (?, ?, ?, 'loose', ?)
                        """,
                        (design_id, color_id, needed, container_id),
                    )
                if container_id:
                    stats['preserved_assignments'] += 1
                stats['created_in_loose'] += 1
            elif current_loose_qty > required_loose_qty:
                # Too many - reduce quantities
                excess = current_loose_qty - required_loose_qty
                for inv_id, qty, _ in loose_items:
                    if excess <= 0:
                        break
                    if qty <= excess:
                        if not dry_run:
                            conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
                        stats['deleted'] += 1
                        excess -= qty
                    else:
                        new_qty = qty - excess
                        if not dry_run:
                            conn.execute(
                                "UPDATE inventory SET quantity = ? WHERE id = ?",
                                (new_qty, inv_id),
                            )
                        stats['updated_quantities'] += 1
                        excess = 0
            continue
        
        # Get current quantity in loose inventory (not putaway)
        loose_items = existing['loose'].get(key, [])
        current_loose_qty = sum(qty for _, qty, _ in loose_items)
        
        # Get current quantity in putaway (should be moved out)
        putaway_items = existing['putaway'].get(key, [])
        current_putaway_qty = sum(qty for _, qty, _ in putaway_items)
        
        if current_loose_qty < required_qty:
            # Need more - try to move from putaway first, preserving container assignments
            needed = required_qty - current_loose_qty
            
            # Move putaway items to loose, preserving their original container if possible
            # Actually, if they're in putaway, they shouldn't have a container assignment
            # So we'll move them and they'll be unassigned
            for inv_id, qty, _ in putaway_items:
                if needed <= 0:
                    break
                if not dry_run:
                    conn.execute(
                        "UPDATE inventory SET container_id = NULL WHERE id = ?",
                        (inv_id,),
                    )
                stats['moved_from_putaway'] += 1
                needed -= qty
            
            # Create new items, preserving existing container assignment if available
            if needed > 0:
                container_id = loose_items[0][2] if loose_items else None
                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO inventory (design_id, color_id, quantity, status, container_id)
                        VALUES (?, ?, ?, 'loose', ?)
                        """,
                        (design_id, color_id, needed, container_id),
                    )
                if container_id:
                    stats['preserved_assignments'] += 1
                stats['created_in_loose'] += 1
        
        elif current_loose_qty > required_qty:
            # Too many - reduce quantities, preserving container assignments
            excess = current_loose_qty - required_qty
            for inv_id, qty, container_id in loose_items:
                if excess <= 0:
                    break
                if qty <= excess:
                    if not dry_run:
                        conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
                    stats['deleted'] += 1
                    excess -= qty
                else:
                    new_qty = qty - excess
                    if not dry_run:
                        conn.execute(
                            "UPDATE inventory SET quantity = ? WHERE id = ?",
                            (new_qty, inv_id),
                        )
                    stats['updated_quantities'] += 1
                    if container_id:
                        stats['preserved_assignments'] += 1
                    excess = 0
        
        # Ensure no items are in putaway for loose parts
        for inv_id, qty, _ in putaway_items:
            if not dry_run:
                # Move to loose, but preserve any existing container assignment from loose items
                container_id = loose_items[0][2] if loose_items else None
                conn.execute(
                    "UPDATE inventory SET container_id = ? WHERE id = ?",
                    (container_id, inv_id),
                )
            stats['moved_from_putaway'] += 1
    
    # Step 3: Delete inventory for parts that don't belong to Loose Parts or Teardown sets
    all_required_keys = set(loose_parts.keys()) | set(teardown.keys())
    
    all_inventory = conn.execute(
        """
        SELECT i.id, i.design_id, i.color_id
        FROM inventory i
        WHERE i.status = 'loose'
        """
    ).fetchall()
    
    for inv_row in all_inventory:
        if isinstance(inv_row, tuple):
            inv_id = inv_row[0]
            design_id = inv_row[1]
            color_id = inv_row[2]
        else:
            inv_id = inv_row["id"]
            design_id = inv_row["design_id"]
            color_id = inv_row["color_id"]
        
        key = (design_id, color_id)
        if key not in all_required_keys:
            if not dry_run:
                conn.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
            stats['deleted'] += 1
    
    if not dry_run:
        conn.commit()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Reconcile inventory preserving locations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually reconcile the inventory",
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
        
        # Reconcile
        mode = "DRY RUN" if args.dry_run else "RECONCILING"
        print(f"\n🔧 {mode}...")
        stats = reconcile_preserving_locations(conn, putaway_bin_id, dry_run=args.dry_run)
        
        print("\n📈 Changes:")
        for key, value in stats.items():
            if value > 0:
                print(f"   {key}: {value}")
        
        if args.dry_run:
            print("\n💡 Run with --fix to apply these changes")
        else:
            print("\n✅ Inventory reconciled!")
            
            # Check how many items are unassigned
            unassigned = conn.execute(
                """
                SELECT COUNT(*) FROM inventory
                WHERE status = 'loose' AND container_id IS NULL
                """
            ).fetchone()[0]
            unassigned_count = unassigned if isinstance(unassigned, int) else unassigned[0]
            
            if unassigned_count > 0:
                print(f"\n⚠️  {unassigned_count} items in loose inventory need container assignment")
                print("   Use the Putaway Wizard to assign them to containers")
            else:
                print("\n✅ All items have container assignments!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

