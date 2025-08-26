#!/usr/bin/env bash
set -euo pipefail

REPO="andyburdick72/lego_inventory"

ensure_gh() {
  if ! command -v gh >/dev/null 2>&1; then
    echo "Install GitHub CLI first: brew install gh && gh auth login" >&2
    exit 1
  fi
}

mk() {
  local name="$1" color="$2" desc="${3:-}"
  gh label create "$name" --repo "$REPO" --color "$color" ${desc:+--description "$desc"} 2>/dev/null || \
  gh label edit "$name" --repo "$REPO" --color "$color" ${desc:+--description "$desc"}
}

ensure_gh
mk "type:feature"      "1D76DB" "New functionality"
mk "type:bug"          "D73A4A" "Bug fix"
mk "type:refactor"     "A2EEEF" "Refactor / cleanup"
mk "type:test"         "0E8A16" "Testing / coverage"
mk "type:exploration"  "C5DEF5" "Prototype / spike"

mk "area:backend"      "0E8A16"
mk "area:frontend"     "FBCA04"
mk "area:scripts"      "C5DEF5"

mk "size:S"            "BFD4F2"
mk "size:M"            "006B75"
mk "size:L"            "D4C5F9"

mk "priority:P1"       "EE0701"
mk "priority:P2"       "FBCA04"
mk "priority:P3"       "C2E0C6"

# ---- Copilot label ----
mk "copilot"           "6f42c1" "AI-assisted / multi-file work"

echo "Labels ensured for $REPO"