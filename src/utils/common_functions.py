"""Utility helpers shared across loaders and scripts.

Currently includes:

* ``load_rebrickable_environment`` – load API credentials from a ``.env``
  file kept **outside** version control.  Searches these locations, in
  order:

  1. ``data/env`` file
  2. ``data/user_data/.env`` (mirrors Instabrick repo layout)

If none are found or required vars are missing the function prints a
friendly error and ``sys.exit(1)``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path: str | os.PathLike) -> None:  # type: ignore
        """Very small fallback if python-dotenv isn't installed."""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ.setdefault(key, val)

# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

def _candidate_paths() -> list[Path]:
    """Return possible .env locations in priority order."""
    explicit = os.getenv("REBRICKABLE_ENV")
    paths = []
    if explicit:
        paths.append(Path(explicit))
    # repo-root .env
    paths.append(REPO_ROOT / "data" / ".env")
    # mirror of Instabrick layout
    paths.append(REPO_ROOT / "data" / "user_data" / ".env")
    return paths


def load_rebrickable_environment() -> Tuple[str, str, str, str]:
    """Load credentials; exits program if unavailable."""
    dotenv_path: Path | None = None
    for p in _candidate_paths():
        if p.exists():
            dotenv_path = p
            break
    if not dotenv_path:
        print("Error: No .env file found in expected locations.")
        print("Checked:\n  " + "\n  ".join(map(str, _candidate_paths())))
        sys.exit(1)

    load_dotenv(str(dotenv_path))

    api_key = os.getenv("REBRICKABLE_API_KEY")
    user_token = os.getenv("REBRICKABLE_USER_TOKEN")
    username = os.getenv("REBRICKABLE_USERNAME")
    password = os.getenv("REBRICKABLE_PASSWORD")

    if not all([api_key, user_token, username, password]):
        print("Error: Missing one or more required variables in .env:")
        print("  REBRICKABLE_API_KEY, REBRICKABLE_USER_TOKEN, REBRICKABLE_USERNAME, REBRICKABLE_PASSWORD")
        sys.exit(1)

    return api_key, user_token, username, password

if __name__ == "__main__":
    print(load_rebrickable_environment())