# CREATE ISSUE — lego_inventory (personal)

Same hygiene as Cleverlawn (`XOS4Biz` / `cleverlawn-site`): **type + area labels only**; **Priority and Size are Project fields**.

## Account

- Repo: `andyburdick72/lego_inventory`
- `gh auth switch -u andyburdick72` before any issue/project API
- MCP: github-personal (not Clever Lawn)
- Default assignee: `andyburdick72`

## Core Rules

1. Use existing labels only (`type:*`, `area:*`, optional `copilot`).
2. Priority and Size are project fields, never labels.
3. Always add to Project #1 and set Status / Priority / Size.
4. Milestones only for multi-issue epics (e.g. Deploy: bricks.ervinburdick.com).

## Required Workflow

1. Confirm no duplicate: `gh issue list --repo andyburdick72/lego_inventory --state open --limit 100`
2. Create issue with title, body, labels, assignee (and milestone if epic).
3. Add to Project #1 (`gh project item-add 1 --owner andyburdick72 --url …` or GraphQL).
4. Set fields via GraphQL `updateProjectV2ItemFieldValue`:
   - Status = `To Do`
   - Priority = `P1|P2|P3`
   - Size = `S|M|L`
5. Resolve field/option IDs at runtime (do not hardcode across sessions):

```bash
gh api graphql -f query='
query($login:String!,$num:Int!){
  user(login:$login){
    projectV2(number:$num){
      id
      fields(first:40){
        nodes{
          ... on ProjectV2SingleSelectField{
            id name options{id name}
          }
        }
      }
    }
  }
}' -f login=andyburdick72 -F num=1
```

6. Return issue URL + applied metadata.

Or use: `scripts/gh_create_issue.sh "Title" body.md P2 M feature backend`

## Issue Body Template

```markdown
## Summary
<What & why>

## Acceptance Criteria
- [ ] …
- [ ] …

## Notes
Dependencies, branch suggestion, related issues.

Part of #<epic>   # when applicable
```

## Forbidden

- Do NOT create new labels.
- Do NOT use Priority/Size labels (`priority:*`, `size:*`).
- Do NOT skip project assignment or project field updates.
- Do NOT use the `andy-cleverlawn` gh account on this repo.
