# Putaway Wizard Improvements

## Summary

Fixed critical issues with the Putaway Wizard and added automatic set status updates.

## Changes Made

### 1. Fixed Auto-Assignment Bug ✅

**Problem**: The Putaway Wizard was automatically assigning ALL parts to their suggested locations when parts loaded, causing all parts to be moved when the user only wanted to move a few.

**Solution**: Modified `frontend/components/putaway/putaway-wizard.tsx` to initialize all assignments with `container_id: null`. Users must now explicitly assign each part they want to move.

**File**: `frontend/components/putaway/putaway-wizard.tsx` (lines 75-94)

### 2. Added Automatic Set Status Updates ✅

**New Behavior**:
- **Part-out entry point**: When parting out a set, if 95%+ of parts are assigned, the set status is automatically updated to `loose_parts`
- **Putaway bin entry point**: When ALL items are moved out of the Putaway Bin, all sets with status `teardown` are automatically updated to `loose_parts`
- **Partial putaway**: When only some items are moved from Putaway Bin, temporary mismatches in Location Reconciliation are expected and OK

**Files Modified**:
- `src/core/dtos.py`: Added `entry_point` and `set_number` to `BatchAssignmentRequestDTO`
- `src/app/api/v1/putaway.py`: Added set status update logic after batch assignment
- `frontend/lib/hooks/use-putaway.ts`: Updated request interface
- `frontend/components/putaway/putaway-wizard.tsx`: Sends entry point and set number

### 3. Database Backup System ✅

**Created**:
- `src/scripts/backup_database.py`: Backup script that creates timestamped backups and cleans up old ones (keeps 30 days by default)
- `scripts/setup_nightly_backup.sh`: Setup script for cron job

**Backup Location**: `data/backups/`

**To Set Up Nightly Backups**:
```bash
./scripts/setup_nightly_backup.sh
```

This will create a cron job that runs daily at 2:00 AM.

**To Test Backup Manually**:
```bash
source .venv/bin/activate
python src/scripts/backup_database.py
```

### 4. Cleaned Up Duplicate Database Files ✅

Removed empty `inventory.db` and `lego_inventory.db` files from the repo root. These were empty placeholder files and are already ignored by `.gitignore`.

## Important Notes

### Location Reconciliation Mismatches

When using the Putaway Wizard to move **some** (but not all) items from the Putaway Bin:
- This creates a temporary mismatch between Teardown sets and items in the Putaway Bin
- Location Reconciliation will show these items as needing updates
- This is **expected behavior** and will resolve when:
  - All items from that set are moved out of Putaway Bin, OR
  - The set status is manually changed to `loose_parts`

### Set Status Update Logic

- **Part-out**: Only updates if 95%+ of parts are assigned (allows for small discrepancies)
- **Putaway Bin**: Only updates all Teardown sets if the bin is completely empty
- **Partial operations**: No automatic status updates (user must manually update set status if needed)

## Testing

To verify the fixes work correctly:

1. **Test Part-out**:
   - Open Putaway Wizard
   - Select "Part-Out Set"
   - Choose a set
   - Assign all parts
   - Confirm
   - Verify set status changed to `loose_parts`

2. **Test Putaway Bin (Full)**:
   - Put all items from Putaway Bin into containers
   - Verify all Teardown sets changed to `loose_parts`

3. **Test Putaway Bin (Partial)**:
   - Put only some items from Putaway Bin into containers
   - Verify Location Reconciliation shows expected mismatches
   - Verify Teardown sets remain as `teardown`

