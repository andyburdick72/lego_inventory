"""Utility helpers shared across loaders and scripts.

This module now only re-exports the centralized settings accessor.
All environment and configuration loading is handled in `app.settings`.
"""

from __future__ import annotations

from app.settings import get_settings

__all__ = ["get_settings"]
