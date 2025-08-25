# filepath: src/infra/db/conn.py
from __future__ import annotations

import sqlite3

from app.settings import get_settings


def get_conn() -> sqlite3.Connection:
    """
    Open a sqlite3 connection with row_factory set to Row so results
    behave like dicts. Adjust the settings attribute name if needed.
    """
    settings = get_settings()
    db_path = settings.db_path  # or settings.database_path depending on your settings
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
