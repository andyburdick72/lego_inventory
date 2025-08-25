from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Protocol


class _ConnLike(Protocol):
    def commit(self) -> Any: ...
    def rollback(self) -> Any: ...


@contextmanager
def transaction(conn: _ConnLike) -> Generator[_ConnLike]:
    """
    Minimal transaction context manager. Works with sqlite3 connections and
    anything exposing commit()/rollback().
    """
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        finally:
            raise
