#!/usr/bin/env bash
set -euo pipefail

# gh-create-issue.sh
# Create a GitHub issue with standard labels and add it to a project.
# Usage:
#   gh-create-issue.sh "Issue title" path/to/body.md P2 M feature frontend
#   gh-create-issue.sh -r owner/repo -p 1 -o @me -c "Title" - P1 L refactor backend < body.md
#
# Positional args:
#   1: Title
#   2: Body file path OR "-" to read from stdin
#   3: Priority (P1|P2|P3)
#   4: Size (S|M|L)
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

# Allowed values based on seed_labels.sh
ALLOWED_PRIORITY=(P1 P2 P3)
ALLOWED_SIZE=(S M L)
ALLOWED_TYPE=(feature bug refactor test exploration)
ALLOWED_AREA=(frontend backend scripts)

in_array() { local needle="$1"; shift; for e in "$@"; do [[ "$e" == "$needle" ]] && return 0; done; return 1; }

in_array "$PRIORITY" "${ALLOWED_PRIORITY[@]}" || die "Invalid priority: $PRIORITY (allowed: ${ALLOWED_PRIORITY[*]})"
in_array "$SIZE"     "${ALLOWED_SIZE[@]}"     || die "Invalid size: $SIZE (allowed: ${ALLOWED_SIZE[*]})"
in_array "$TYPE"     "${ALLOWED_TYPE[@]}"     || die "Invalid type: $TYPE (allowed: ${ALLOWED_TYPE[*]})"
in_array "$AREA"     "${ALLOWED_AREA[@]}"     || die "Invalid area: $AREA (allowed: ${ALLOWED_AREA[*]})"

# --- Helpers ---
say() { printf "%s\n" "$*" >&2; }
die() { say "Error: $*"; exit 1; }

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

# Labels we enforce
LABELS=("area:$AREA" "priority:$PRIORITY" "size:$SIZE" "type:$TYPE")
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

# Dry-run info and exit early if requested
if [ "$DRY_RUN" -eq 1 ]; then
  say "(dry-run) Would ensure labels exist"
  say "(dry-run) Would create issue via gh api"
  say "(dry-run) Would add issue to project"
  exit 0
fi

# Ensure labels exist
for L in "${LABELS[@]}"; do
  ensure_label "$L"
done

# Create issue via REST (returns JSON)
ISSUE_JSON=$(gh api \
  "repos/$REPO/issues" \
  -f "title=$TITLE" \
  -f "body=@$BODY_PATH" \
  -f "labels=$(printf '["%s"]' "$(IFS='","'; echo "${LABELS[*]}")")")

ISSUE_URL=$(printf '%s' "$ISSUE_JSON" | jq -r '.html_url')
ISSUE_NUM=$(printf '%s' "$ISSUE_JSON" | jq -r '.number')

[ -n "$ISSUE_URL" ] || die "Failed to get issue URL"
say "Created issue #$ISSUE_NUM"
say "$ISSUE_URL"

# Add to project
gh project item-add "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --url "$ISSUE_URL" >/dev/null
say "Added to project $PROJECT_NUMBER"

# Output the URL (easy copy)
printf "%s\n" "$ISSUE_URL"

# Cleanup
[ -n "$TMP_BODY" ] && rm -f "$TMP_BODY"