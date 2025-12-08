from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from app.errors import NotFoundError, ValidationError


class PartsRepo(Protocol):
    def get_part(self, design_id: str) -> Mapping[str, Any] | None: ...
    def update_part(self, design_id: str, **fields: Any) -> None: ...


class PartsService:
    """
    Thin façade for parts metadata lookups.
    """

    def __init__(self, parts: PartsRepo) -> None:
        self._parts = parts

    def get_part(self, *, design_id: str):
        design_id = (design_id or "").strip()
        if not design_id:
            raise ValidationError("design_id is required")
        part = self._parts.get_part(design_id)
        if not part:
            raise NotFoundError("Part not found", details={"design_id": design_id})
        return part

    def update_part(self, *, design_id: str, **fields: Any):
        design_id = (design_id or "").strip()
        if not design_id:
            raise ValidationError("design_id is required")
        # Verify part exists
        part = self._parts.get_part(design_id)
        if not part:
            raise NotFoundError("Part not found", details={"design_id": design_id})
        # Update part
        self._parts.update_part(design_id, **fields)
        # Return updated part
        return self._parts.get_part(design_id)
