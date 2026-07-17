#!/usr/bin/env bash
set -euo pipefail

REPO="andyburdick72/lego_inventory"

# Uses GitHub CLI auth (gh auth login); no $GITHUB_TOKEN required.
# Prefer epic-style milestones that group multiple issues. One-issue-per-
# milestone "phases" were removed — use Project #1 Status/Priority/Size instead.
create() {
  local title="$1"
  local desc="${2:-}"
  if [ -n "$desc" ]; then
    gh api -X POST "repos/$REPO/milestones" -f title="$title" -f description="$desc" >/dev/null 2>&1 || true
  else
    gh api -X POST "repos/$REPO/milestones" -f title="$title" >/dev/null 2>&1 || true
  fi
}

create 'Deploy: bricks.ervinburdick.com' \
  "Refactor to Next.js + Supabase and deploy Ervin-Burdick's Bricks to Render at bricks.ervinburdick.com"

echo "Milestones ensured for $REPO"
