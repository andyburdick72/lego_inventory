from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol


class SetPartsRepo(Protocol):
    def list_for_set(self, *, set_number: str) -> Iterable[Mapping[str, Any]]: ...
    def upsert_for_set(self, *, set_number: str, parts: Iterable[Mapping[str, Any]]) -> None: ...


class SetsRepo(Protocol):
    def get(self, *, set_number: str) -> Mapping[str, Any] | None: ...


class SetPartsService:
    """
    Thin façade around set parts operations.
    """

    def __init__(self, sets: SetsRepo, set_parts: SetPartsRepo) -> None:
        self._sets = sets
        self._set_parts = set_parts

    def get_set(self, *, set_number: str):
        return self._sets.get(set_number=set_number)

    def list_parts(self, *, set_number: str):
        return self._set_parts.list_for_set(set_number=set_number)

    def upsert_parts(self, *, set_number: str, parts: Iterable[Mapping[str, Any]]):
        return self._set_parts.upsert_for_set(set_number=set_number, parts=parts)
