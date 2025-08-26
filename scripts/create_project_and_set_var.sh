#!/usr/bin/env bash
set -euo pipefail

# Creates (or finds) a user Project v2 named by $TITLE for $OWNER
# and sets the repo variable LEGO_PROJECT_ID for $OWNER/$REPO.
#
# Prereqs: gh (GitHub CLI), jq; run `gh auth login` first.
# Recommended scopes (refresh if needed):
#   gh auth refresh -h github.com -s read:project -s project -s repo

OWNER="andyburdick72"
REPO="lego_inventory"
TITLE="LEGO Inventory Management System Roadmap"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }
}

need gh
need jq

echo "Looking up Projects (v2) for user: $OWNER ..."
QUERY_LIST='query($login:String!){ user(login:$login){ projectsV2(first:100){ nodes { id title number } } } }'
resp="$(gh api graphql -f login="$OWNER" -f query="$QUERY_LIST")"
node_id="$(echo "$resp" | jq -r --arg T "$TITLE" '.data.user.projectsV2.nodes[] | select(.title==$T) | .id')"
number="$(echo "$resp"  | jq -r --arg T "$TITLE" '.data.user.projectsV2.nodes[] | select(.title==$T) | .number')"

if [[ -z "${node_id:-}" || "$node_id" == "null" ]]; then
  echo "No existing project titled \"$TITLE\". Creating..."
  created="$(gh project create --owner "$OWNER" --title "$TITLE" --format json)"
  # Some gh versions return null nodeId here; capture number and refetch via GraphQL
  number="$(echo "$created" | jq -r .number)"
  node_id="$(echo "$created" | jq -r .nodeId)"

  if [[ -z "${node_id:-}" || "$node_id" == "null" ]]; then
    echo "nodeId not returned by create; resolving via GraphQL using project number=$number ..."
    QUERY_ONE='query($login:String!,$number:Int!){ user(login:$login){ projectV2(number:$number){ id title number } } }'
    one="$(gh api graphql -F login="$OWNER" -F number="$number" -f query="$QUERY_ONE")"
    node_id="$(echo "$one" | jq -r '.data.user.projectV2.id')"
  fi

  echo "Created project: number=${number:-unknown}  node_id=${node_id:-null}"
else
  echo "Found existing project: number=$number  node_id=$node_id"
fi

if [[ -z "${node_id:-}" || "$node_id" == "null" ]]; then
  echo "ERROR: Could not resolve a valid node_id for project \"$TITLE\". Please ensure your gh token has read:project/project scopes and try:"
  echo "  gh auth refresh -h github.com -s read:project -s project -s repo"
  exit 1
fi

echo "Setting repo variable LEGO_PROJECT_ID for $OWNER/$REPO ..."
gh variable set LEGO_PROJECT_ID --repo "$OWNER/$REPO" --body "$node_id"

echo "Done."
echo "Project title: $TITLE"
echo "Project number: ${number:-unknown}"
echo "Project node_id (saved to repo var LEGO_PROJECT_ID): $node_id"