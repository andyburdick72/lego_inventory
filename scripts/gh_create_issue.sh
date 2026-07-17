#!/usr/bin/env bash
set -euo pipefail

# gh-create-issue.sh
# Create a GitHub issue with standard labels, add it to Project #1, and set
# Priority / Size as project fields (not labels).
# Usage:
#   gh-create-issue.sh "Issue title" path/to/body.md P2 M feature frontend
#   gh-create-issue.sh -r owner/repo -p 1 -o @me -c "Title" - P1 L refactor backend < body.md
#
# Positional args:
#   1: Title
#   2: Body file path OR "-" to read from stdin
#   3: Priority (P1|P2|P3)  — set on Project #1 field
#   4: Size (S|M|L)         — set on Project #1 field
#   5: Type (feature|bug|refactor|test|exploration)
#   6: Area (frontend|backend|scripts)  [optional, default: frontend]
#
# Flags:
#   -r  owner/repo override (default: auto-detected from git)
#   -p  project number      (default: 1)
#   -o  project owner       (default: @me)
#   -c  add 'copilot' label
#   -n  dry-run (echo actions; won’t create anything)
#   -h  help

PROJECT_NUMBER=1
PROJECT_OWNER="@me"
REPO=""
DRY_RUN=0
COPILOT=0

usage() {
  sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

while getopts ":r:p:o:nch" opt; do
  case "$opt" in
    r) REPO="$OPTARG" ;;
    p) PROJECT_NUMBER="$OPTARG" ;;
    o) PROJECT_OWNER="$OPTARG" ;;
    c) COPILOT=1 ;;
    n) DRY_RUN=1 ;;
    h) usage ;;
    *) usage ;;
  esac
done
shift $((OPTIND-1))

if [ "$#" -lt 5 ]; then
  usage
fi

TITLE="$1"
BODY_PATH="$2"
PRIORITY="$3"
SIZE="$4"
TYPE="$5"
AREA="${6:-frontend}"

# Allowed values
ALLOWED_PRIORITY=(P1 P2 P3)
ALLOWED_SIZE=(S M L)
ALLOWED_TYPE=(feature bug refactor test exploration)
ALLOWED_AREA=(frontend backend scripts)

# --- Helpers ---
say() { printf "%s\n" "$*" >&2; }
die() { say "Error: $*"; exit 1; }

in_array() { local needle="$1"; shift; for e in "$@"; do [[ "$e" == "$needle" ]] && return 0; done; return 1; }

in_array "$PRIORITY" "${ALLOWED_PRIORITY[@]}" || die "Invalid priority: $PRIORITY (allowed: ${ALLOWED_PRIORITY[*]})"
in_array "$SIZE"     "${ALLOWED_SIZE[@]}"     || die "Invalid size: $SIZE (allowed: ${ALLOWED_SIZE[*]})"
in_array "$TYPE"     "${ALLOWED_TYPE[@]}"     || die "Invalid type: $TYPE (allowed: ${ALLOWED_TYPE[*]})"
in_array "$AREA"     "${ALLOWED_AREA[@]}"     || die "Invalid area: $AREA (allowed: ${ALLOWED_AREA[*]})"

need() { command -v "$1" >/dev/null 2>&1 || die "Missing dependency: $1"; }
need gh
need git
need jq

# Auth check
if ! gh auth status >/dev/null 2>&1; then
  die "GitHub CLI not authenticated. Run: gh auth login"
fi

# Repo detection
if [ -z "$REPO" ]; then
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    origin_url=$(git remote get-url origin 2>/dev/null || true)
    if [[ "$origin_url" =~ github.com[:/](.+)/(.+)(\.git)?$ ]]; then
      owner="${BASH_REMATCH[1]}"
      name="${BASH_REMATCH[2]%.*}"
      REPO="$owner/$name"
    fi
  fi
fi
[ -n "$REPO" ] || die "Could not detect repo. Use -r owner/repo."

# Body handling
TMP_BODY=""
if [ "$BODY_PATH" = "-" ]; then
  TMP_BODY=$(mktemp)
  cat > "$TMP_BODY"
  BODY_PATH="$TMP_BODY"
fi
[ -f "$BODY_PATH" ] || die "Body file not found: $BODY_PATH"

# Labels we enforce (Priority/Size are project fields, not labels)
LABELS=("area:$AREA" "type:$TYPE")
if [ "$COPILOT" -eq 1 ]; then
  LABELS+=("copilot")
fi

ensure_label() {
  local label="$1"
  if ! gh label list --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$label"; then
    say "Creating label: $label"
    if [ "$DRY_RUN" -eq 0 ]; then
      gh label create "$label" --repo "$REPO" >/dev/null || true
    fi
  fi
}

say "Repo: $REPO"
say "Project: $PROJECT_OWNER / $PROJECT_NUMBER"
say "Title: $TITLE"
say "Labels: ${LABELS[*]}"
say "Project fields: Priority=$PRIORITY Size=$SIZE"

# Dry-run info and exit early if requested
if [ "$DRY_RUN" -eq 1 ]; then
  say "(dry-run) Would ensure labels exist"
  say "(dry-run) Would create issue via gh api"
  say "(dry-run) Would add issue to project and set Priority/Size fields"
  exit 0
fi

# Ensure labels exist
for L in "${LABELS[@]}"; do
  ensure_label "$L"
done

# Create issue via REST (returns JSON)
LABEL_FLAGS=()
for L in "${LABELS[@]}"; do
  LABEL_FLAGS+=( -f "labels[]=$L" )
done
ISSUE_JSON=$(gh api \
  "repos/$REPO/issues" \
  -f "title=$TITLE" \
  -f "body=@$BODY_PATH" \
  "${LABEL_FLAGS[@]}")

ISSUE_URL=$(printf '%s' "$ISSUE_JSON" | jq -r '.html_url')
ISSUE_NUM=$(printf '%s' "$ISSUE_JSON" | jq -r '.number')
ISSUE_NODE_ID=$(printf '%s' "$ISSUE_JSON" | jq -r '.node_id')

[ -n "$ISSUE_URL" ] || die "Failed to get issue URL"
say "Created issue #$ISSUE_NUM"
say "$ISSUE_URL"

# Add to project
ITEM_ID=$(gh project item-add "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --url "$ISSUE_URL" --format json | jq -r '.id')
say "Added to project $PROJECT_NUMBER (item=$ITEM_ID)"

# Resolve project + Priority/Size field option IDs, then set fields
OWNER_LOGIN="$PROJECT_OWNER"
if [ "$OWNER_LOGIN" = "@me" ]; then
  OWNER_LOGIN=$(gh api user --jq .login)
fi

PROJECT_META=$(gh api graphql -f query='
query($login:String!, $number:Int!) {
  user(login:$login) {
    projectV2(number:$number) {
      id
      fields(first: 40) {
        nodes {
          __typename
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name }
          }
        }
      }
    }
  }
}' -f login="$OWNER_LOGIN" -F number="$PROJECT_NUMBER")

PROJECT_ID=$(printf '%s' "$PROJECT_META" | jq -r '.data.user.projectV2.id')
PRIORITY_FIELD=$(printf '%s' "$PROJECT_META" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name=="Priority") | .id')
SIZE_FIELD=$(printf '%s' "$PROJECT_META" | jq -r '.data.user.projectV2.fields.nodes[] | select(.name=="Size") | .id')
PRIORITY_OPT=$(printf '%s' "$PROJECT_META" | jq -r --arg p "$PRIORITY" '.data.user.projectV2.fields.nodes[] | select(.name=="Priority") | .options[] | select(.name==$p) | .id')
SIZE_OPT=$(printf '%s' "$PROJECT_META" | jq -r --arg s "$SIZE" '.data.user.projectV2.fields.nodes[] | select(.name=="Size") | .options[] | select(.name==$s) | .id')

[ -n "$PROJECT_ID" ] && [ "$PROJECT_ID" != "null" ] || die "Could not resolve project id"
[ -n "$ITEM_ID" ] && [ "$ITEM_ID" != "null" ] || die "Could not resolve project item id"
[ -n "$PRIORITY_FIELD" ] && [ -n "$PRIORITY_OPT" ] || die "Could not resolve Priority field/option"
[ -n "$SIZE_FIELD" ] && [ -n "$SIZE_OPT" ] || die "Could not resolve Size field/option"

set_field() {
  local field_id="$1" option_id="$2"
  gh api graphql -f query='
  mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
    updateProjectV2ItemFieldValue(input:{
      projectId:$project, itemId:$item, fieldId:$field,
      value:{ singleSelectOptionId:$option }
    }) { projectV2Item { id } }
  }' -f project="$PROJECT_ID" -f item="$ITEM_ID" -f field="$field_id" -f option="$option_id" >/dev/null
}

set_field "$PRIORITY_FIELD" "$PRIORITY_OPT"
set_field "$SIZE_FIELD" "$SIZE_OPT"
say "Set project fields Priority=$PRIORITY Size=$SIZE"

# Output the URL (easy copy)
printf "%s\n" "$ISSUE_URL"

# Cleanup
[ -n "$TMP_BODY" ] && rm -f "$TMP_BODY"
