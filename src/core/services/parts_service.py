from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class PartsRepo(Protocol):
    def get_part(self, design_id: str) -> Mapping[str, Any] | None: ...


class PartsService:
    """
    Thin façade for parts metadata lookups.
    """

    def __init__(self, parts: PartsRepo) -> None:
        self._parts = parts

    def get_part(self, *, design_id: str):
        return self._parts.get_part(design_id)
