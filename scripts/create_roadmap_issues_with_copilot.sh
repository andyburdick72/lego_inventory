#!/usr/bin/env bash
set -euo pipefail

# Batch-create the 13 LEGO roadmap issues with labels, milestones,
# and embedded Copilot prompts where appropriate.
#
# Prereqs:
#   - gh auth login
#   - Milestones already created (scripts/seed_milestones.sh)
#   - Project created and workflow pushed (optional; the workflow will auto-add issues)
#
# Notes:
#   - PROJECT is the user Project (v2) title. The add-to-project workflow will also attach new issues automatically.

REPO="andyburdick72/lego_inventory"
PROJECT="LEGO Inventory Management System Roadmap"

ensure_label() {
  local name="$1" color="$2" desc="${3:-}"
  if ! gh label list --repo "$REPO" --json name --jq '.[].name' | grep -qx "$name"; then
    gh label create "$name" --repo "$REPO" --color "$color" ${desc:+--description "$desc"} >/dev/null
  fi
}

echo "Ensuring 'copilot' label exists..."
ensure_label "copilot" "6f42c1" "AI-assisted / multi-file work"

create_issue() {
  local title="$1"; shift
  local out url
  if out="$(gh issue create --repo "$REPO" --title "$title" "$@")"; then
    url="$(echo "$out" | grep -Eo 'https://github\.com/[^[:space:]]+' | tail -n1)"
    if [[ -n "${url:-}" ]]; then
      echo "✅ Created: ${title}  →  ${url}"
    else
      echo "✅ Created: ${title}"
      echo "$out"
    fi
  else
    echo "❌ Failed to create: ${title}" >&2
    echo "$out" >&2
    exit 1
  fi
}

echo "Creating roadmap issues in $REPO ..."

# 1) Route write endpoints (COPILOT)
create_issue "Repository refactor: Route write endpoints" \
  --label "type:feature" --label "area:backend" --label "priority:P1" --label "size:M" --label "copilot" \
  --milestone "Refactor: write endpoints" --project "$PROJECT" \
  --body $'- [ ] Create endpoints: create/rename/move/delete for drawers & containers\n- [ ] Validate input; return correct 2xx/4xx JSON\n- [ ] Wire repository writes; handle DuplicateLabelError\n- [ ] Update client JS to call endpoints\n- [ ] Contract tests added; ./dev.sh smoke passes\n\n💡 Copilot Prompt:\nSearch the repo for existing drawer/container CRUD logic. Create FastAPI routes for create/rename/move/delete, update repository write paths, and adjust contract tests until green.\n\n🔀 Recommended branch: feature/route-write-endpoints'

# 2) Error taxonomy (COPILOT)
create_issue "Repository refactor: Error taxonomy" \
  --label "type:refactor" --label "area:backend" --label "priority:P1" --label "size:M" --label "copilot" \
  --milestone "Refactor: error taxonomy" --project "$PROJECT" \
  --body $'- [ ] Define error classes (app/errors.py) & map to HTTP codes\n- [ ] Central exception handler -> consistent API error schema\n- [ ] Update client toast/messages for common errors\n- [ ] Tests for duplicate, missing, and permission-style cases\n\n💡 Copilot Prompt:\nIntroduce a centralized error taxonomy (custom exceptions + code mapping). Update all raises/handlers in repos/adapters to use the new classes and adjust tests to assert normalized error responses.\n\n🔀 Recommended branch: refactor/error-taxonomy'

# 3) Generic Export (COPILOT)
create_issue "Repository refactor: Generic Export" \
  --label "type:feature" --label "area:backend" --label "priority:P1" --label "size:M" --label "copilot" \
  --milestone "Refactor: generic export" --project "$PROJECT" \
  --body $'- [ ] Server export endpoint (table param)\n- [ ] CSV output; column order preserved; proper escaping/UTF-8\n- [ ] Hook export buttons in UI tables\n- [ ] Tests for sets/drawers/containers export\n\n💡 Copilot Prompt:\nImplement a generic export function for sets, drawers, and containers. Add CSV with proper quoting/utf-8. Wire to the UI export buttons and add tests for each table type.\n\n🔀 Recommended branch: feature/generic-export'

# 4) Test coverage (phase 2a) (NO COPILOT)
create_issue "Repository refactor: Test coverage (phase 2a)" \
  --label "type:test" --label "area:backend" --label "priority:P2" --label "size:M" \
  --milestone "Test coverage phase 2a" --project "$PROJECT" \
  --body $'- [ ] Adapters: coverage ≥ target\n- [ ] Enums: parsing & labels tests\n- [ ] Contract edges around API boundaries\n- [ ] HTML report generated; no flakies\n\n🔀 Recommended branch: test/coverage-phase-2a'

# 5) Hyperlink Drawer / Container columns (NO COPILOT)
create_issue "Hyperlink Drawer / Container columns" \
  --label "type:feature" --label "area:frontend" --label "priority:P2" --label "size:S" \
  --milestone "Hyperlink drawer/container columns" --project "$PROJECT" \
  --body $'- [ ] Render &lt;a&gt; links for drawer & container columns\n- [ ] DataTables sort/search unaffected\n- [ ] Route helpers / URL builders covered by tests\n- [ ] UI test for link generation\n\n🔀 Recommended branch: feature/hyperlink-drawer-container-columns'

# 6) Add Rebrickable Themes (NO COPILOT)
create_issue "Add Rebrickable Themes" \
  --label "type:feature" --label "area:scripts" --label "priority:P2" --label "size:S" \
  --milestone "Add Rebrickable Themes" --project "$PROJECT" \
  --body $'- [ ] Fetch/sync themes from Rebrickable API\n- [ ] Persist to DB; link sets → theme\n- [ ] Display theme in Sets list/detail\n- [ ] Tests for loader & basic UI\n\n🔀 Recommended branch: feature/add-rebrickable-themes'

# 7) Set Status for New Sets + CRUD (COPILOT)
create_issue "Ability to Set Status for New Sets + CRUD for Set Status" \
  --label "type:feature" --label "area:backend" --label "priority:P2" --label "size:M" --label "copilot" \
  --milestone "CRUD for set status" --project "$PROJECT" \
  --body $'- [ ] Add set_status field (enum) to model/DB\n- [ ] CRUD endpoints + validation\n- [ ] Update set loader default (unsorted) & prompt\n- [ ] Frontend control to update status\n- [ ] Tests API + UI\n\n💡 Copilot Prompt:\nAdd a new enum field set_status to the Set model and DB. Update repos and CRUD endpoints, surface in the UI forms, and ensure the loader defaults unsorted. Update tests across API and UI.\n\n🔀 Recommended branch: feature/set-status-crud'

# 8) Pick-List Generator for a Set (COPILOT)
create_issue "Pick-List Generator for a Set" \
  --label "type:feature" --label "area:scripts" --label "priority:P2" --label "size:M" --label "copilot" \
  --milestone "Pick-List Generator" --project "$PROJECT" \
  --body $'- [ ] Generate pick list from set parts vs inventory\n- [ ] Respect color/alias mappings; strip remarks markers\n- [ ] CSV/printable output with Description field\n- [ ] Tests with sample set\n\n💡 Copilot Prompt:\nCreate a pick list generator that compares a target set with on-hand inventory and outputs CSV with part name, color, qty, and location. Use existing mapping/alias logic. Add tests verifying sample output.\n\n🔀 Recommended branch: feature/pick-list-generator'

# 9) Part-Out Wizard for a Set (COPILOT)
create_issue "Part-Out Wizard for a Set" \
  --label "type:feature" --label "area:frontend" --label "area:backend" --label "priority:P2" --label "size:L" --label "copilot" \
  --milestone "Part-Out Wizard" --project "$PROJECT" \
  --body $'- [ ] UI flow to part-out a set into drawers/containers\n- [ ] Pre-validate availability; show deltas\n- [ ] Persist moves; update inventory status\n- [ ] Tests for flow & data integrity\n\n💡 Copilot Prompt:\nCreate a wizard UI to part-out sets into drawers/containers with backend allocation support. Validate missing/extra parts and persist moves. Provide tests for end-to-end flow and data integrity.\n\n🔀 Recommended branch: feature/part-out-wizard'

# 10) Move / Merge Wizard (COPILOT)
create_issue "Move / Merge Wizard" \
  --label "type:feature" --label "area:frontend" --label "area:backend" --label "priority:P2" --label "size:M" --label "copilot" \
  --milestone "Move / Merge Wizard" --project "$PROJECT" \
  --body $'- [ ] Move container to another drawer\n- [ ] Merge containers; dedupe labels & quantities\n- [ ] Handle conflicts & error messaging\n- [ ] Tests for move/merge ops\n\n💡 Copilot Prompt:\nImplement a wizard to move containers between drawers and merge containers. Update repos and routes, handle conflict states with clear messaging, and write tests for merge/dedupe logic.\n\n🔀 Recommended branch: feature/move-merge-wizard'

# 11) Inventory / Set mismatch dashboard (COPILOT)
create_issue "Inventory / Set mismatch dashboard" \
  --label "type:feature" --label "area:frontend" --label "priority:P2" --label "size:M" --label "copilot" \
  --milestone "Inventory/Set mismatch dashboard" --project "$PROJECT" \
  --body $'- [ ] Compute diffs between set parts & on-hand\n- [ ] UI: missing/excess with filters by set\n- [ ] Link to Pick-List & Part-Out actions\n- [ ] Tests for diff logic\n\n💡 Copilot Prompt:\nBuild a dashboard that surfaces diffs between set definitions and inventory (missing/excess), with filters by set. Provide links to pick-list and part-out actions. Add tests for diff logic and UI.\n\n🔀 Recommended branch: feature/inventory-set-mismatch-dashboard'

# 12) Visual Drawer Grid (NO COPILOT)
create_issue "Visual Drawer Grid (per-drawer layout)" \
  --label "type:feature" --label "area:frontend" --label "priority:P3" --label "size:M" \
  --milestone "Visual Drawer Grid" --project "$PROJECT" \
  --body $'- [ ] Grid UI showing container positions in a drawer\n- [ ] Click-through to container detail\n- [ ] Responsive (desktop/tablet/phone)\n- [ ] UI test / snapshot\n\n🔀 Recommended branch: feature/visual-drawer-grid'

# 13) Add Brick Architect part categories (COPILOT)
create_issue "Add Brick Architect part categories" \
  --label "type:feature" --label "area:backend" --label "priority:P3" --label "size:M" --label "copilot" \
  --milestone "Brick Architect categories" --project "$PROJECT" \
  --body $'- [ ] Import mapping part → Brick Architect category\n- [ ] DB changes & backfill\n- [ ] Expose category in UI & filters\n- [ ] Tests for loader & queries\n\n💡 Copilot Prompt:\nImport Brick Architect category mapping, persist in DB, and expose categories in UI filters. Update loaders and queries. Add tests validating category assignment and filtering.\n\n🔀 Recommended branch: feature/brick-architect-categories'

echo "All roadmap issues created in $REPO"
