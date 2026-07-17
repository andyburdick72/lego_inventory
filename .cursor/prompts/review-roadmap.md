# REVIEW ROADMAP — GitHub Issue Validation (lego_inventory)

Validate **milestones**, issue **labels** (`type:*`, `area:*`), and **LEGO Inventory Management System Roadmap** project fields (**Status**, **Priority** P1–P3, **Size** S–L). **Priority and Size must live on the project, not as issue labels.**

Default repo: **`andyburdick72/lego_inventory`**. Account: **`andyburdick72`**.

## Core responsibilities

1. **Fetch current state**
   - Issues: `gh issue list --repo andyburdick72/lego_inventory --state open --limit 100`
   - Labels: `gh label list --repo andyburdick72/lego_inventory`
   - Milestones: `gh api repos/andyburdick72/lego_inventory/milestones --jq '.[] | "\(.title)\t\(.state)"'`
   - Project: `gh project field-list 1 --owner andyburdick72 --format json`

2. **Validate each issue**
   - At least one **`type:*`** and one **`area:*`** for normal work.
   - Flag unknown labels vs `gh label list`.
   - Flag **`priority:*` / `size:*` issue labels** (deprecated) — migrate to project fields then remove.
   - Milestone: only required for multi-issue epics (e.g. *Deploy: bricks.ervinburdick.com*).
   - Project #1: every open issue should be on the board with Status + Priority + Size set.
   - Assignee: open work should usually be `andyburdick72`.

3. **Report** — summary counts + per-issue findings table + suggested `gh` commands (do not run without approval).

## Forbidden

- Invent labels; assume milestones without fetching; modify issues without explicit user request; use andy-cleverlawn account.
