#!/usr/bin/env python3
"""
Clean up parts that don't belong to any sets.

This script identifies and removes parts that:
- Are not in any sets (not in set_parts table)

General rule: If a part is in inventory but not in set_parts, it's considered
leftover from old imports and can be cleaned up. The default behavior is to
delete all orphaned parts, including those with inventory records.

Use --exclude-inventory to only delete parts without inventory records.
"""

import sqlite3
import sys
from pathlib import Path

# Allow running this file directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.settings import get_settings

SETTINGS = get_settings()


def get_orphaned_parts(exclude_with_inventory: bool = False) -> list[dict]:
    """Get parts that don't belong to any sets.
    
    Args:
        exclude_with_inventory: If True, exclude parts that have inventory records.
                                If False (default), include all orphaned parts.
    
    Returns:
        List of dicts with design_id, name, inventory_count, alias_count
    """
    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        if exclude_with_inventory:
            # Only get parts with no inventory
            query = """
                SELECT 
                    p.design_id,
                    p.name,
                    0 as inventory_count,
                    COUNT(DISTINCT pa.alias) as alias_count
                FROM parts p
                LEFT JOIN part_aliases pa ON pa.design_id = p.design_id
                WHERE p.design_id NOT IN (SELECT DISTINCT design_id FROM set_parts)
                  AND p.design_id NOT IN (SELECT DISTINCT design_id FROM inventory WHERE design_id IS NOT NULL)
                GROUP BY p.design_id, p.name
                ORDER BY p.design_id
            """
        else:
            # Get all parts not in sets, regardless of inventory (default behavior)
            query = """
                SELECT 
                    p.design_id,
                    p.name,
                    COUNT(DISTINCT i.id) as inventory_count,
                    COUNT(DISTINCT pa.alias) as alias_count
                FROM parts p
                LEFT JOIN inventory i ON i.design_id = p.design_id
                LEFT JOIN part_aliases pa ON pa.design_id = p.design_id
                WHERE p.design_id NOT IN (SELECT DISTINCT design_id FROM set_parts)
                GROUP BY p.design_id, p.name
                ORDER BY inventory_count DESC, p.design_id
            """
        
        c.execute(query)
        return [dict(row) for row in c.fetchall()]


def delete_parts(design_ids: list[str], dry_run: bool = True) -> dict:
    """Delete parts and their related data.
    
    Args:
        design_ids: List of part design IDs to delete
        dry_run: If True, don't actually delete, just report what would be deleted
    
    Returns:
        Dict with counts of what was/would be deleted
    """
    if not design_ids:
        return {
            'parts': 0,
            'inventory': 0,
            'aliases': 0,
        }
    
    with sqlite3.connect(str(SETTINGS.db_path)) as conn:
        c = conn.cursor()
        
        # Get counts before deletion
        placeholders = ','.join('?' * len(design_ids))
        
        inventory_count = c.execute(
            f"SELECT COUNT(*) FROM inventory WHERE design_id IN ({placeholders})",
            design_ids
        ).fetchone()[0]
        
        alias_count = c.execute(
            f"SELECT COUNT(*) FROM part_aliases WHERE design_id IN ({placeholders})",
            design_ids
        ).fetchone()[0]
        
        if dry_run:
            return {
                'parts': len(design_ids),
                'inventory': inventory_count,
                'aliases': alias_count,
            }
        
        # Actually delete
        # Note: Foreign key constraints should handle cascading, but we'll be explicit
        
        # Delete inventory records
        if inventory_count > 0:
            c.execute(
                f"DELETE FROM inventory WHERE design_id IN ({placeholders})",
                design_ids
            )
        
        # Delete aliases
        if alias_count > 0:
            c.execute(
                f"DELETE FROM part_aliases WHERE design_id IN ({placeholders})",
                design_ids
            )
        
        # Delete parts
        c.execute(
            f"DELETE FROM parts WHERE design_id IN ({placeholders})",
            design_ids
        )
        
        conn.commit()
        
        return {
            'parts': len(design_ids),
            'inventory': inventory_count,
            'aliases': alias_count,
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clean up parts that don't belong to any sets"
    )
    parser.add_argument(
        '--exclude-inventory',
        action='store_true',
        help='Exclude parts that have inventory records (default: delete all orphaned parts, including those with inventory)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Dry run mode - show what would be deleted without actually deleting (default: True)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform the deletion (overrides --dry-run)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts (use with caution)'
    )
    parser.add_argument(
        '--part',
        action='append',
        help='Only process specific part ID(s) (can be used multiple times)'
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    # Get orphaned parts
    orphaned = get_orphaned_parts(exclude_with_inventory=args.exclude_inventory)
    
    if args.part:
        # Filter to only specified parts
        orphaned = [p for p in orphaned if p['design_id'] in args.part]
        if not orphaned:
            print(f"No orphaned parts found matching: {', '.join(args.part)}")
            return
    
    if not orphaned:
        print("No orphaned parts found.")
        return
    
    # Separate parts with and without inventory
    parts_with_inventory = [p for p in orphaned if p['inventory_count'] > 0]
    parts_without_inventory = [p for p in orphaned if p['inventory_count'] == 0]
    
    print(f"\n{'='*80}")
    print(f"Orphaned Parts Analysis")
    print(f"{'='*80}")
    print(f"Total orphaned parts: {len(orphaned)}")
    print(f"  - With inventory: {len(parts_with_inventory)}")
    print(f"  - Without inventory: {len(parts_without_inventory)}")
    
    if parts_with_inventory:
        print(f"\n⚠️  PARTS WITH INVENTORY (handle carefully):")
        for p in parts_with_inventory:
            print(f"  {p['design_id']:20} | {p['name'][:50]:50} | Inventory: {p['inventory_count']}, Aliases: {p['alias_count']}")
    
    if parts_without_inventory:
        print(f"\n✓ Parts without inventory (safe to delete):")
        for p in parts_without_inventory:
            print(f"  {p['design_id']:20} | {p['name'][:50]:50} | Aliases: {p['alias_count']}")
    
    # Determine what to delete
    if args.exclude_inventory:
        # Only delete parts without inventory
        parts_to_delete = parts_without_inventory
        if parts_with_inventory:
            print(f"\n⚠️  Skipping {len(parts_with_inventory)} parts with inventory (use without --exclude-inventory to include them)")
    else:
        # Default: delete all orphaned parts, including those with inventory
        if parts_with_inventory:
            print(f"\n⚠️  WARNING: There are {len(parts_with_inventory)} parts with inventory.")
            print("   These will be deleted along with their inventory records!")
            print("   (General rule: parts in inventory but not in set_parts are considered leftover)")
            if dry_run:
                print("   (This is a dry run - nothing will actually be deleted)")
            elif not args.force:
                response = input("\n   Are you sure you want to delete parts with inventory? (yes/no): ")
                if response.lower() != 'yes':
                    print("   Cancelled.")
                    return
        parts_to_delete = orphaned
    
    if not parts_to_delete:
        print("\nNo parts to delete.")
        return
    
    # Show what will be deleted
    design_ids = [p['design_id'] for p in parts_to_delete]
    stats = delete_parts(design_ids, dry_run=dry_run)
    
    print(f"\n{'='*80}")
    if dry_run:
        print("DRY RUN - No changes made")
    else:
        print("DELETION COMPLETE")
    print(f"{'='*80}")
    print(f"Parts deleted: {stats['parts']}")
    print(f"Inventory records deleted: {stats['inventory']}")
    print(f"Aliases deleted: {stats['aliases']}")
    
    if dry_run:
        print(f"\nTo actually perform the deletion, run with --execute flag")


if __name__ == "__main__":
    main()

