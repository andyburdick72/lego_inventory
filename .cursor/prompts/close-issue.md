# CLOSE ISSUE — Commit, Push, and Close (lego_inventory)

Cleanly finish work on a GitHub issue for **`andyburdick72/lego_inventory`**.

## Workflow

1. Confirm issue # and `git status`.
2. Commit with conventional message referencing the issue (`close #N` / `fixes #N`).
3. Push branch (or `main` if Andy is working directly — ask before push when unclear).
4. Optional PR with `Closes #N`.
5. Always post a closing comment: what shipped, deferred items, commit hash.
6. `gh issue close <N> --repo andyburdick72/lego_inventory -r completed`.
7. Set Project #1 **Status** → **Done** (resolve field IDs at runtime).
8. Cleanup merged feature branch when applicable.

## Forbidden

No issue reference on close commits; no skip of closing comment; no force-push; no wrong GitHub account.
