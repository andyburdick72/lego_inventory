# CLOSE ISSUE — lego_inventory

Finish work on a GitHub issue: commit, push, PR as needed, comment, close, Project #1 Status → Done, branch cleanup.

**Default repo:** `andyburdick72/lego_inventory`  
**Account:** `gh auth switch -u andyburdick72`

## Workflow

1. **Context** — Issue # from user, branch name, or recent work. `git status`.
2. **Commit** — Stage only relevant files. Conventional message with issue reference:
   ```
   <type>(<scope>): close #<N> - <summary>

   - Bullet changes
   - Deferrals / blockers
   ```
   Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
3. **Push** — `git push origin <branch>` (ask before push if not already approved this session).
4. **PR** — If using PR flow: `gh pr create --repo andyburdick72/lego_inventory` with `Closes #N` in body. Solo work may commit/push `main` when Andy prefers that.
5. **Closing comment** — Always add a detailed comment (scope, what was done, deferred items, commit hash).
6. **Close issue** — `gh issue close <N> --repo andyburdick72/lego_inventory -r completed` when appropriate.
7. **Project status** — Set **Status** to **Done** on Project #1 (`gh project item-edit` / GraphQL after resolving IDs). Skip if token lacks `project` scope.
8. **Branch cleanup** — After merge: checkout main, pull, delete branch locally and on origin when safe.

## Forbidden

- No commit without issue reference when closing an issue.
- No skipping the audit-trail comment.
- No force-push without explicit user request.
- No deleting branches with unmerged work without confirmation.
- No `andy-cleverlawn` account on this repo.

## Detail

**`.cursor/prompts/close-issue.md`**
