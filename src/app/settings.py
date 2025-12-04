# src/app/settings.py
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute project root: repo/ (two levels up from this file: repo/src/app/settings.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB = DATA_DIR / "lego_inventory.db"
DEFAULT_REPORTS_DIR = DATA_DIR / "reports"


class Settings(BaseSettings):
    """
    Central application configuration.

    Sources (highest precedence first):
      1. Environment variables (prefixed with APP_, e.g. APP_DB_PATH)
      2. .env file at data/.env
      3. Defaults below
    """

    model_config = SettingsConfigDict(
        env_file=str(DATA_DIR / ".env"),
        env_prefix="APP_",
        extra="ignore",
    )

    # App/server
    debug: bool = Field(default=False, description="Enable debug mode")
    host: str = Field(default="127.0.0.1", description="Server host to bind")
    port: int = Field(default=8000, description="Server port to bind")

    # Paths
    db_path: Path = Field(default=DEFAULT_DB, description="SQLite DB path")
    reports_dir: Path = Field(default=DEFAULT_REPORTS_DIR, description="Reports output directory")

    # Credentials / API keys
    rebrickable_api_key: Optional[str] = Field(
        default=None, description="Rebrickable API key (if needed by features)"
    )
    rebrickable_user_token: Optional[str] = Field(default=None, description="Rebrickable user token")
    rebrickable_username: Optional[str] = Field(default=None, description="Rebrickable username")
    rebrickable_password: Optional[str] = Field(default=None, description="Rebrickable password")

    # --- Validators / normalizers ---
    @field_validator("db_path", "reports_dir", mode="before")
    @classmethod
    def _normalize_pathlike_and_expand(cls, v: Any):
        """Accept str/Path/PathLike; expand ~ and $VARS; let Pydantic coerce to Path.
        - If v is a non-str PathLike, coerce via os.fspath.
        - Expand env vars and user home on strings.
        - Return a string so the field type Path gets final coercion.
        """
        if v is None:
            return v
        # Coerce arbitrary PathLike to str early so we can expand
        if not isinstance(v, (str, Path)):
            try:
                v = os.fspath(v)  # PathLike -> str
            except TypeError:
                return v  # let Pydantic raise if truly invalid
        s = str(v)
        s = os.path.expandvars(os.path.expanduser(s))
        return s

    # --- Backwards compatibility for older tests ---
    @classmethod
    def _expand_user_and_env(cls, v: Any):
        """Shim retained for tests that call the old validator name.
        Delegates to `_normalize_pathlike_and_expand`, then coerces to `Path`
        when appropriate so legacy tests expecting a `Path` still pass.
        """
        res = cls._normalize_pathlike_and_expand(v)
        try:
            # If res is a str or PathLike, coerce to Path for backward compat
            return Path(os.fspath(res))
        except (TypeError, ValueError):
            # If not pathlike, return as-is (legacy tests cover this branch)
            return res

    # --- Helpers ---
    def ensure_directories(self) -> None:
        """Create parent dirs for DB and the reports dir (idempotent)."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Singleton-style accessor so imports are cheap and consistent system-wide.
    Also ensures directories exist on first access.
    """
    s = Settings()
    s.ensure_directories()
    return s


if __name__ == "__main__":
    # Handy for a quick sanity check:
    s = get_settings()
    print("PROJECT_ROOT:", PROJECT_ROOT)
    print("debug:", s.debug)
    print("host:", s.host, "port:", s.port)
    print("db_path:", s.db_path)
    print("reports_dir:", s.reports_dir)
    print("rebrickable_api_key set?:", bool(s.rebrickable_api_key))
    print("rebrickable_user_token set?:", bool(s.rebrickable_user_token))
    print("rebrickable_username set?:", bool(s.rebrickable_username))
    print("rebrickable_password set?:", bool(s.rebrickable_password))
