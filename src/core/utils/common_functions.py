"""Utility helpers shared across loaders and scripts.

Currently includes:

* ``load_rebrickable_environment`` – load API credentials from a ``.env``
  file kept **outside** version control.  Searches these locations, in
  order:

  1. ``data/user_data/.env`` (mirrors Instabrick repo layout)
  2. ``data/.env``

If none are found or required vars are missing the function prints a
friendly error and ``sys.exit(1)``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import IO

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(
        dotenv_path: os.PathLike[str] | str | None = None,
        stream: IO[str] | None = None,
        verbose: bool = False,
        override: bool = False,
        interpolate: bool = True,
        encoding: str | None = "utf-8",
    ) -> bool:
        """Minimal fallback compatible with python-dotenv's load_dotenv signature."""
        fh: IO[str] | None = None
        try:
            if stream is not None:
                fh = stream
            elif dotenv_path is not None:
                fh = open(str(dotenv_path), encoding=encoding or "utf-8")
            else:
                return False
            loaded = False
            for line in fh:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    if override:
                        os.environ[key] = val
                    else:
                        os.environ.setdefault(key, val)
                    loaded = True
            return loaded
        finally:
            if fh is not None and fh is not stream:
                try:
                    fh.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]


def _candidate_paths() -> list[Path]:
    """Return possible .env locations in priority order."""
    explicit = os.getenv("REBRICKABLE_ENV")
    paths = []
    if explicit:
        paths.append(Path(explicit))
    # mirror of Instabrick layout
    paths.append(REPO_ROOT / "data" / "user_data" / ".env")
    # repo-root .env
    paths.append(REPO_ROOT / "data" / ".env")
    return paths


def load_rebrickable_environment() -> tuple[str, str, str, str]:
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

    def _require_env(name: str) -> str:
        val = os.getenv(name)
        if not val:
            print(f"Error: Missing {name} in {dotenv_path}")
            sys.exit(1)
        return val

    api_key = _require_env("REBRICKABLE_API_KEY")
    user_token = _require_env("REBRICKABLE_USER_TOKEN")
    username = _require_env("REBRICKABLE_USERNAME")
    password = _require_env("REBRICKABLE_PASSWORD")

    return api_key, user_token, username, password


if __name__ == "__main__":
    print(load_rebrickable_environment())
