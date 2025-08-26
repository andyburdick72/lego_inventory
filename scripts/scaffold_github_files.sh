#!/usr/bin/env bash
set -euo pipefail

# Scaffold GitHub Issue templates (with checklists), PR template,
# and the workflow that auto-adds new Issues to the Project board.
#
# Prereqs: gh (logged in), jq
# The workflow expects repo variable LEGO_PROJECT_ID to be set.

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }
}

need jq

mkdir -p .github/ISSUE_TEMPLATE .github/workflows scripts

# ------------------------
# Issue Templates
# ------------------------
cat > .github/ISSUE_TEMPLATE/feature.yml <<"YAML"
name: Feature
description: New capability or enhancement
title: "[Feature]: "
labels: ["type:feature"]
body:
  - type: input
    id: summary
    attributes:
      label: Summary
      placeholder: One-line what & why
    validations:
      required: true

  - type: textarea
    id: context
    attributes:
      label: Context / Links
      description: Relevant code, screenshots, URLs, related issues
      placeholder: |
        - Code refs:
        - Screenshot:
        - Related issues:

  - type: checkboxes
    id: acceptance
    attributes:
      label: Acceptance criteria (required)
      description: These define "done"
      options:
        - label: Tests updated/added
          required: true
        - label: No regressions in smoke tests (`./dev.sh`)
          required: true
        - label: Linked to milestone (phase)
          required: true

  - type: textarea
    id: extra_checklist
    attributes:
      label: Additional checklist (edit freely)
      value: |
        - [ ] Task 1
        - [ ] Task 2
        - [ ] Task 3

  - type: dropdown
    id: area
    attributes:
      label: Area
      options: [backend, frontend, scripts]
    validations:
      required: true

  - type: dropdown
    id: size
    attributes:
      label: Size
      options: [S, M, L]
    validations:
      required: true

  - type: dropdown
    id: priority
    attributes:
      label: Priority
      options: [P1, P2, P3]
    validations:
      required: true

  - type: input
    id: branch
    attributes:
      label: Recommended branch name
      description: Suggested naming convention: type/short-slug
      placeholder: feature/hyperlink-drawer-columns

  - type: textarea
    id: copilot
    attributes:
      label: Copilot prompt (optional)
      description: Add a starting prompt for Copilot Chat to accelerate this issue
      placeholder: |
        e.g. "Update all DTOs to include 'category' field, update repos,
        API endpoints, and tests that reference Status or Brick Architect categories."
YAML

cat > .github/ISSUE_TEMPLATE/refactor.yml <<"YAML"
name: Refactor
description: Improve structure without changing behavior
title: "[Refactor]: "
labels: ["type:refactor"]
body:
  - type: input
    id: scope
    attributes:
      label: Scope
      placeholder: e.g., Repositories layer / DTOs
    validations:
      required: true

  - type: textarea
    id: risks
    attributes:
      label: Risk / Blast radius
      placeholder: Modules touched, behavior to watch

  - type: checkboxes
    id: testplan
    attributes:
      label: Test plan
      options:
        - label: Unit tests updated
        - label: Smoke tests pass locally (`./dev.sh`)
        - label: Coverage unchanged or improved

  - type: textarea
    id: extra_checklist
    attributes:
      label: Additional checklist
      value: |
        - [ ] Extract code to new module
        - [ ] Rename symbols
        - [ ] Update imports

  - type: input
    id: branch
    attributes:
      label: Recommended branch name
      description: Suggested naming convention: type/short-slug
      placeholder: refactor/error-taxonomy

  - type: textarea
    id: copilot
    attributes:
      label: Copilot prompt (optional)
      description: Add a starting prompt for Copilot Chat to accelerate this issue
      placeholder: |
        e.g. "Replace ad-hoc dict responses with DTOs across services and update tests."
YAML

cat > .github/ISSUE_TEMPLATE/test.yml <<"YAML"
name: Test
description: Add or expand tests
title: "[Test]: "
labels: ["type:test"]
body:
  - type: textarea
    id: goal
    attributes:
      label: Goal
      placeholder: What behaviors & edges are being verified?
    validations:
      required: true

  - type: textarea
    id: coverage
    attributes:
      label: Coverage targets
      value: |
        - [ ] Adapter X
        - [ ] Enum Y
        - [ ] Contract edges Z

  - type: input
    id: branch
    attributes:
      label: Recommended branch name
      description: Suggested naming convention: type/short-slug
      placeholder: test/coverage-phase-2a
YAML

cat > .github/ISSUE_TEMPLATE/config.yml <<"YAML"
blank_issues_enabled: false
contact_links: []
YAML

# ------------------------
# PR Template
# ------------------------
cat > .github/PULL_REQUEST_TEMPLATE.md <<"MD"
## Summary
-

## Linked Issues
Fixes #<id> (or) Refs #<id>

## Acceptance
- [ ] Tests updated/added
- [ ] `./dev.sh` passes
- [ ] Manual check on affected pages (list)
MD

# ------------------------
# Workflow: auto-add issues to Project
# ------------------------
cat > .github/workflows/add-to-project.yml <<"YAML"
name: Add issues to Project

on:
  issues:
    types: [opened, reopened]

permissions:
  contents: read
  issues: write
  projects: write

jobs:
  add:
    runs-on: ubuntu-latest
    steps:
      - name: Add to project
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PROJECT_ID: ${{ vars.LEGO_PROJECT_ID }}
          CONTENT_ID: ${{ github.event.issue.node_id }}
        run: |
          cat > body.json <<'JSON'
          {
            "query": "mutation($project:ID!, $content:ID!){ addProjectV2ItemById(input:{projectId:$project, contentId:$content}){ item { id }}}",
            "variables": { "project": "'"$PROJECT_ID"'", "content": "'"$CONTENT_ID"'" }
          }
          JSON
          curl -s -X POST https://api.github.com/graphql \
            -H "Authorization: Bearer $GH_TOKEN" \
            -H "Content-Type: application/json" \
            --data @body.json | jq .
YAML

# ------------------------
# Commit scaffold
# ------------------------
git add .github || true
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "Scaffold: issue templates with checklists, PR template, add-to-project workflow"
  echo "Committed scaffolding. Remember to: git push"
fi

echo "Scaffold complete."