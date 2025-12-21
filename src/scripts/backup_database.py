#!/usr/bin/env python3
"""Nightly backup script for the LEGO inventory database.

This script creates timestamped backups of the database in a backups directory.
Old backups are automatically cleaned up (keeps last 30 days).
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.settings import get_settings


def backup_database(backup_dir: Path | None = None, keep_days: int = 30) -> Path:
    """Create a backup of the database.

    Args:
        backup_dir: Directory to store backups. Defaults to data/backups/
        keep_days: Number of days of backups to keep (default: 30)

    Returns:
        Path to the created backup file
    """
    settings = get_settings()
    db_path = Path(settings.db_path)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    # Determine backup directory
    if backup_dir is None:
        backup_dir = db_path.parent / "backups"
    else:
        backup_dir = Path(backup_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"lego_inventory_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    # Copy database file
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Verify backup
    if backup_path.exists() and backup_path.stat().st_size > 0:
        print(f"✅ Backup created successfully ({backup_path.stat().st_size:,} bytes)")
    else:
        raise RuntimeError("Backup failed - file is missing or empty")

    # Clean up old backups
    cleanup_old_backups(backup_dir, keep_days)

    return backup_path


def cleanup_old_backups(backup_dir: Path, keep_days: int) -> None:
    """Remove backup files older than keep_days.

    Args:
        backup_dir: Directory containing backups
        keep_days: Number of days to keep
    """
    cutoff_date = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)

    deleted_count = 0
    for backup_file in backup_dir.glob("lego_inventory_*.db"):
        if backup_file.stat().st_mtime < cutoff_date:
            backup_file.unlink()
            deleted_count += 1

    if deleted_count > 0:
        print(f"🧹 Cleaned up {deleted_count} old backup(s)")


def main():
    parser = argparse.ArgumentParser(description="Backup the LEGO inventory database")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Directory to store backups (default: data/backups/)",
    )
    parser.add_argument(
        "--keep-days",
        type=int,
        default=30,
        help="Number of days of backups to keep (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without creating backup",
    )
    args = parser.parse_args()

    try:
        if args.dry_run:
            settings = get_settings()
            db_path = Path(settings.db_path)
            backup_dir = args.backup_dir or (db_path.parent / "backups")
            print(f"Would backup: {db_path}")
            print(f"To directory: {backup_dir}")
            print(f"Would keep backups for {args.keep_days} days")
        else:
            backup_path = backup_database(args.backup_dir, args.keep_days)
            print(f"\n✅ Backup complete: {backup_path}")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
