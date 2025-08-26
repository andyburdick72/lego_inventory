#!/usr/bin/env bash
set -euo pipefail

REPO="andyburdick72/lego_inventory"

# Uses GitHub CLI auth (gh auth login); no $GITHUB_TOKEN required.
create() {
  local title="$1"
  gh api -X POST "repos/$REPO/milestones" -f title="$title" >/dev/null 2>&1 || true
}

create 'Refactor: write endpoints'
create 'Refactor: error taxonomy'
create 'Refactor: generic export'
create 'Test coverage phase 2a'
create 'Hyperlink drawer/container columns'
create 'Add Rebrickable Themes'
create 'CRUD for set status'
create 'Pick-List Generator'
create 'Part-Out Wizard'
create 'Move / Merge Wizard'
create 'Inventory/Set mismatch dashboard'
create 'Visual Drawer Grid'
create 'Brick Architect categories'

echo "Milestones ensured for $REPO"