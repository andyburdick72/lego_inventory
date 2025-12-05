# Feature Analysis and Priority Recommendations (Updated)

**Generated**: Based on actual GitHub issues from `andyburdick72/lego_inventory`

---

## ✅ Completed Issues (Closed)

1. **#1 - Route write endpoints** (P1) ✅
2. **#2 - Error taxonomy** (P1) ✅
3. **#3 - Generic Export** (P1) ✅
4. **#4 - Test coverage (phase 2a)** (P2) ✅
5. **#5 - Hyperlink Drawer/Container columns** (P2) ✅
6. **#12 - Visual Drawer Grid** (P3) ✅

**Great progress!** All P1 foundation items are complete, plus several P2 features.

---

## 📋 Open Issues (10 Total)

### Priority 2 (P2) - Feature Enhancements (7 issues)

#### #6 - Add Rebrickable Themes
- **Labels**: `type:feature`, `area:scripts`, `size:S`, `priority:P2`
- **Milestone**: Add Rebrickable Themes
- **Status**: Open
- **Tasks**:
  - [ ] Fetch/sync themes from Rebrickable API
  - [ ] Persist to DB; link sets → theme
  - [ ] Display theme in Sets list/detail
  - [ ] Tests for loader & basic UI
- **Branch**: `feature/add-rebrickable-themes`
- **Effort**: Small
- **Value**: Medium - Better set organization and filtering

#### #7 - Ability to Set Status for New Sets + CRUD for Set Status
- **Labels**: `type:feature`, `area:backend`, `size:M`, `priority:P2`, `copilot`
- **Milestone**: CRUD for set status
- **Status**: Open
- **Tasks**:
  - [ ] Add set_status field (enum) to model/DB
  - [ ] CRUD endpoints + validation
  - [ ] Update set loader default (unsorted) & prompt
  - [ ] Frontend control to update status
  - [ ] Tests API + UI
- **Branch**: `feature/set-status-crud`
- **Effort**: Medium
- **Value**: High - Core functionality for set management
- **Note**: Status update endpoint exists (`PATCH /sets/{set_number}/status`), but may need creation-time status support

#### #8 - Pick-List Generator for a Set
- **Labels**: `type:feature`, `area:scripts`, `size:M`, `priority:P2`, `copilot`
- **Milestone**: Pick-List Generator
- **Status**: Open
- **Tasks**:
  - [ ] Generate pick list from set parts vs inventory
  - [ ] Respect color/alias mappings; strip remarks markers
  - [ ] CSV/printable output with Description field
  - [ ] Tests with sample set
- **Branch**: `feature/pick-list-generator`
- **Effort**: Medium
- **Value**: **Very High** - Enables building sets from inventory
- **Copilot Prompt**: Create a pick list generator that compares a target set with on-hand inventory and outputs CSV with part name, color, qty, and location. Use existing mapping/alias logic. Add tests verifying sample output.

#### #9 - Part-Out Wizard for a Set
- **Labels**: `type:feature`, `area:backend`, `area:frontend`, `size:L`, `priority:P2`, `copilot`
- **Milestone**: Part-Out Wizard
- **Status**: Open
- **Tasks**:
  - [ ] UI flow to part-out a set into drawers/containers
  - [ ] Pre-validate availability; show deltas
  - [ ] Persist moves; update inventory status
  - [ ] Tests for flow & data integrity
- **Branch**: `feature/part-out-wizard`
- **Effort**: Large
- **Value**: **Very High** - Common workflow for breaking down sets
- **Copilot Prompt**: Create a wizard UI to part-out sets into drawers/containers with backend allocation support. Validate missing/extra parts and persist moves. Provide tests for end-to-end flow and data integrity.
- **Note**: Example implementation exists in `docs/teardown-feature-example.md`

#### #10 - Move / Merge Wizard
- **Labels**: `type:feature`, `area:backend`, `area:frontend`, `size:M`, `priority:P2`, `copilot`
- **Milestone**: Move / Merge Wizard
- **Status**: Open
- **Tasks**:
  - [ ] Move container to another drawer
  - [ ] Merge containers; dedupe labels & quantities
  - [ ] Handle conflicts & error messaging
  - [ ] Tests for move/merge ops
- **Branch**: `feature/move-merge-wizard`
- **Effort**: Medium
- **Value**: High - Better inventory organization
- **Copilot Prompt**: Implement a wizard to move containers between drawers and merge containers. Update repos and routes, handle conflict states with clear messaging, and write tests for merge/dedupe logic.

#### #11 - Inventory / Set mismatch dashboard
- **Labels**: `type:feature`, `area:frontend`, `size:M`, `priority:P2`, `copilot`
- **Milestone**: Inventory/Set mismatch dashboard
- **Status**: Open
- **Tasks**:
  - [ ] Compute diffs between set parts & on-hand
  - [ ] UI: missing/excess with filters by set
  - [ ] Link to Pick-List & Part-Out actions
  - [ ] Tests for diff logic
- **Branch**: `feature/inventory-set-mismatch-dashboard`
- **Effort**: Medium
- **Value**: **Very High** - Helps identify missing/excess parts
- **Copilot Prompt**: Build a dashboard that surfaces diffs between set definitions and inventory (missing/excess), with filters by set. Provide links to pick-list and part-out actions. Add tests for diff logic and UI.

#### #14 - Add 'Sync with Rebrickable' button on Sets page
- **Labels**: `type:feature`, `area:frontend`, `size:M`, `priority:P2`
- **Milestone**: None
- **Status**: Open
- **Details**:
  - Add button labeled "Sync with Rebrickable" to Sets page
  - Call backend endpoint `POST /sync/rebrickable`
  - Backend runs `load_my_rebrickable_sets` → updates `sets`
  - Backend runs `load_my_rebrickable_parts` → updates `set_parts`
  - Show toast notification on success/failure
  - Contract test to confirm new sets appear
  - Stretch: Add progress indicator
- **Branch**: `feature/sync-rebrickable`
- **Effort**: Medium
- **Value**: High - Makes data sync accessible from UI

### Priority 3 (P3) - Nice to Have (3 issues)

#### #13 - Add Brick Architect part categories
- **Labels**: `type:feature`, `area:backend`, `size:M`, `priority:P3`, `copilot`
- **Milestone**: Brick Architect categories
- **Status**: Open
- **Tasks**:
  - [ ] Import mapping part → Brick Architect category
  - [ ] DB changes & backfill
  - [ ] Expose category in UI & filters
  - [ ] Tests for loader & queries
- **Branch**: `feature/brick-architect-categories`
- **Effort**: Medium
- **Value**: Medium - Better part organization
- **Copilot Prompt**: Import Brick Architect category mapping, persist in DB, and expose categories in UI filters. Update loaders and queries. Add tests validating category assignment and filtering.

#### #15 - Standardize image handling (parts, sets, placeholders)
- **Labels**: `type:refactor`, `area:frontend`, `size:M`, `priority:P3`
- **Milestone**: None
- **Status**: Open
- **Effort**: Medium
- **Value**: Low-Medium - Code quality improvement
- **Note**: Body content appears to be a file reference (may need clarification)

#### #16 - Hierarchical storage rules for part locations
- **Labels**: `type:refactor`, `area:backend`, `size:M`, `priority:P3`
- **Milestone**: None
- **Status**: Open
- **Effort**: Medium
- **Value**: Low-Medium - Code quality improvement
- **Note**: Body content appears to be a file reference (may need clarification)

---

## 🎯 Recommended Priority Order

### Phase 1: High-Value Workflows (Weeks 1-4)
**Focus**: Features that provide immediate, high user value

1. **#8 - Pick-List Generator** (P2, Medium effort)
   - **Why**: Enables building sets from inventory - core use case
   - **Dependencies**: None
   - **Value**: ⭐⭐⭐⭐⭐ Very High
   - **Effort**: Medium

2. **#11 - Inventory/Set Mismatch Dashboard** (P2, Medium effort)
   - **Why**: Helps identify missing/excess parts - high diagnostic value
   - **Dependencies**: None (but complements Pick-List Generator)
   - **Value**: ⭐⭐⭐⭐⭐ Very High
   - **Effort**: Medium

3. **#9 - Part-Out Wizard** (P2, Large effort)
   - **Why**: Common workflow for breaking down sets
   - **Dependencies**: None (but benefits from error handling)
   - **Value**: ⭐⭐⭐⭐⭐ Very High
   - **Effort**: Large
   - **Note**: Consider breaking into smaller increments

### Phase 2: Core Functionality & UX (Weeks 5-6)
**Focus**: Complete core features and improve usability

4. **#7 - Set Status CRUD** (P2, Medium effort)
   - **Why**: Core functionality - may be partially done, needs completion
   - **Dependencies**: None
   - **Value**: ⭐⭐⭐⭐ High
   - **Effort**: Medium (may be less if partially implemented)

5. **#14 - Sync with Rebrickable Button** (P2, Medium effort)
   - **Why**: Makes data sync accessible from UI
   - **Dependencies**: None (scripts already exist)
   - **Value**: ⭐⭐⭐⭐ High
   - **Effort**: Medium

6. **#10 - Move/Merge Wizard** (P2, Medium effort)
   - **Why**: Better inventory organization
   - **Dependencies**: None
   - **Value**: ⭐⭐⭐⭐ High
   - **Effort**: Medium

### Phase 3: Enhancements (Weeks 7-8)
**Focus**: Nice-to-have features that improve organization

7. **#6 - Add Rebrickable Themes** (P2, Small effort)
   - **Why**: Quick win - better set organization
   - **Dependencies**: None
   - **Value**: ⭐⭐⭐ Medium
   - **Effort**: Small

8. **#13 - Brick Architect Categories** (P3, Medium effort)
   - **Why**: Better part organization and filtering
   - **Dependencies**: None
   - **Value**: ⭐⭐⭐ Medium
   - **Effort**: Medium

### Phase 4: Code Quality (Weeks 9+)
**Focus**: Refactoring and technical debt

9. **#15 - Standardize image handling** (P3, Medium effort)
   - **Why**: Code quality improvement
   - **Dependencies**: None
   - **Value**: ⭐⭐ Low-Medium
   - **Effort**: Medium
   - **Note**: May need clarification on requirements

10. **#16 - Hierarchical storage rules** (P3, Medium effort)
    - **Why**: Code quality improvement
    - **Dependencies**: None
    - **Value**: ⭐⭐ Low-Medium
    - **Effort**: Medium
    - **Note**: May need clarification on requirements

---

## 💡 Suggested Additional Features

Based on the current state and open issues, here are additional features that would complement the roadmap:

### High Priority Additions

1. **Set Building Assistant** (builds on #8 Pick-List Generator)
   - **Why**: Enhanced workflow for building sets from inventory
   - **Features**:
     - Show which parts are available vs needed
     - Suggest alternative colors if exact match unavailable
     - Track build progress
   - **Impact**: Very High
   - **Effort**: Large

2. **Advanced Search/Filtering**
   - **Why**: Current tables have basic search, but could benefit from:
     - Multi-field filtering (part name + color + location)
     - Saved filter presets
     - Full-text search across part names/descriptions
   - **Impact**: High
   - **Effort**: Medium

3. **Bulk Operations**
   - **Why**: Common operations that would benefit from bulk actions:
     - Bulk move parts between containers
     - Bulk update set statuses
     - Bulk delete/archive
   - **Impact**: High
   - **Effort**: Medium

### Medium Priority Additions

4. **Inventory History/Audit Trail**
   - **Why**: Track changes over time (audit_log table exists but may need enhancement)
   - **Impact**: Medium-High
   - **Effort**: Medium

5. **Import Improvements**
   - **Why**: Current import is script-based, could add:
     - Web UI for XML import
     - Import progress tracking
     - Import validation and preview before commit
   - **Impact**: Medium
   - **Effort**: Medium

6. **Analytics Dashboard**
   - **Why**: Provide insights:
     - Most common parts/colors
     - Set completion statistics
     - Inventory growth over time
   - **Impact**: Medium
   - **Effort**: Medium

---

## 📊 Summary Statistics

- **Total Open Issues**: 10
- **P2 Issues**: 7 (High priority features)
- **P3 Issues**: 3 (Nice to have)
- **Completed Issues**: 6 (All P1 items done! ✅)

### By Area
- **Backend**: 4 issues (#7, #9, #10, #13, #16)
- **Frontend**: 4 issues (#9, #10, #11, #14, #15)
- **Scripts**: 2 issues (#6, #8)
- **Refactor**: 2 issues (#15, #16)

### By Size
- **Small**: 1 issue (#6)
- **Medium**: 8 issues (#7, #8, #10, #11, #13, #14, #15, #16)
- **Large**: 1 issue (#9)

---

## 🚀 Immediate Next Steps

### This Sprint (Recommended)
1. **#8 - Pick-List Generator** - High value, medium effort, enables core use case
2. **#11 - Inventory/Set Mismatch Dashboard** - High value, complements pick-list
3. **#6 - Add Rebrickable Themes** - Quick win, small effort

### Next Sprint
4. **#7 - Set Status CRUD** - Complete core functionality
5. **#14 - Sync with Rebrickable Button** - Improve UX for data sync
6. **#10 - Move/Merge Wizard** - Better organization

### Future
7. **#9 - Part-Out Wizard** - Large effort, consider breaking into phases
8. **#13 - Brick Architect Categories** - Nice to have
9. **#15, #16** - Code quality improvements (may need clarification)

---

## ❓ Questions to Consider

1. **What's your primary use case?**
   - Building sets from inventory? → Prioritize #8, #11
   - Organizing existing inventory? → Prioritize #10, #6
   - Breaking down sets? → Prioritize #9

2. **How often do you sync with Rebrickable?**
   - Frequently? → Prioritize #14
   - Rarely? → Lower priority

3. **Do issues #15 and #16 need clarification?**
   - The body content appears to reference temporary files
   - May need to update issue descriptions

4. **Should #9 (Part-Out Wizard) be broken into phases?**
   - Large effort - consider MVP first, then enhancements

---

## 📝 Notes

- All P1 foundation work is complete! 🎉
- Most remaining work is P2 feature enhancements
- Several issues have Copilot prompts ready to use
- Consider creating new issues for suggested additional features if they align with your goals

