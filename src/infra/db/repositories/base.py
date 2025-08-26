from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from typing import Any


class BaseRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _one(self, sql: str, params: Sequence[Any] | None = None) -> dict | None:
        cur = self.conn.execute(sql, params or [])
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def _all(self, sql: str, params: Sequence[Any] | None = None) -> list[dict]:
        cur = self.conn.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]

    def _iter(self, sql: str, params: Sequence[Any] | None = None) -> Iterable[dict]:
        cur = self.conn.execute(sql, params or [])
        for r in cur:
            yield dict(r)
