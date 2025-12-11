from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterable, Sequence
from typing import Any


class BaseRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _execute_with_retry(
        self, sql: str, params: Sequence[Any] | None = None, max_retries: int = 3
    ) -> sqlite3.Cursor:
        """Execute SQL with retry logic for database locked errors."""
        for attempt in range(max_retries):
            try:
                return self.conn.execute(sql, params or [])
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    # Exponential backoff: 0.1s, 0.2s, 0.4s
                    time.sleep(0.1 * (2**attempt))
                    continue
                raise
        raise RuntimeError("Should not reach here")

    def _one(self, sql: str, params: Sequence[Any] | None = None) -> dict | None:
        cur = self._execute_with_retry(sql, params)
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def _all(self, sql: str, params: Sequence[Any] | None = None) -> list[dict]:
        cur = self._execute_with_retry(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def _iter(self, sql: str, params: Sequence[Any] | None = None) -> Iterable[dict]:
        cur = self._execute_with_retry(sql, params)
        for r in cur:
            yield dict(r)
