# REVIEW ROADMAP — lego_inventory

Validate **`andyburdick72/lego_inventory`**: **`type:*`** + **`area:*`** labels, epic **milestones**, and Project **#1** fields (**Status**, **Priority** P1–P3, **Size** S–L). **Do not** use `priority:*` / `size:*` **issue** labels.

**Account:** `gh auth switch -u andyburdick72` (never andy-cleverlawn).

## Fetch

```bash
gh issue list --repo andyburdick72/lego_inventory --state open --limit 100
gh label list --repo andyburdick72/lego_inventory
gh api repos/andyburdick72/lego_inventory/milestones --jq '.[] | "\(.title)\t\(.state)"'
```

## Checks

- Each issue: **`type:*`** and **`area:*`** for normal work.
- Compare labels to `gh label list` — flag unknown names; **do not invent labels**.
- Flag deprecated **`priority:*`** / **`size:*`** issue labels — remove after values live on the **project item**.
- Flag missing epic **milestones** only when the issue is clearly part of a multi-issue epic (e.g. *Deploy: bricks.ervinburdick.com*). Single-issue work may be unmilestoned.
- Flag issues not on Project #1; flag board items with empty Priority or Size.

## Project field IDs

**Do not hardcode** node IDs. Use:

```bash
gh project list --owner andyburdick72
gh project field-list 1 --owner andyburdick72 --format json
```

Needs `project` / `read:project` scopes on the personal token.

## Fixes

Provide `gh issue edit --repo andyburdick72/lego_inventory …` / GraphQL project field updates only when the user asks. **Do not** apply edits without confirmation.

## Detail

Full playbook: **`.cursor/prompts/review-roadmap.md`**.
