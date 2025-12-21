#!/bin/bash
# Setup nightly backup cron job for LEGO inventory database

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"
BACKUP_SCRIPT="$PROJECT_ROOT/src/scripts/backup_database.py"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "   Please run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if backup script exists
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "❌ Backup script not found at $BACKUP_SCRIPT"
    exit 1
fi

# Create cron job entry (runs daily at 2 AM)
CRON_TIME="0 2 * * *"
CRON_COMMAND="cd $PROJECT_ROOT && $VENV_PATH/bin/python $BACKUP_SCRIPT >> $PROJECT_ROOT/data/backups/backup.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$BACKUP_SCRIPT"; then
    echo "⚠️  Backup cron job already exists"
    echo ""
    echo "Current cron jobs:"
    crontab -l 2>/dev/null | grep "$BACKUP_SCRIPT"
    echo ""
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove existing entry
        crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT" | crontab -
    else
        echo "Keeping existing cron job"
        exit 0
    fi
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_TIME $CRON_COMMAND") | crontab -

echo "✅ Nightly backup cron job installed!"
echo ""
echo "Schedule: Daily at 2:00 AM"
echo "Script: $BACKUP_SCRIPT"
echo "Backup location: $PROJECT_ROOT/data/backups/"
echo ""
echo "To view cron jobs: crontab -l"
echo "To remove this cron job: crontab -e (then delete the line)"
echo ""
echo "To test the backup manually:"
echo "  cd $PROJECT_ROOT && source .venv/bin/activate && python src/scripts/backup_database.py"

