from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from app.errors import NotFoundError, ValidationError


# Keep repos abstract to avoid tight coupling
class DrawersRepo(Protocol):
    def list(self, *, filters: Mapping[str, Any] | None = None) -> Iterable[Mapping[str, Any]]: ...
    def create(self, *, label: str) -> Mapping[str, Any]: ...
    def soft_delete(self, drawer_id: int) -> None: ...
    def restore(self, drawer_id: int) -> None: ...


class ContainersRepo(Protocol):
    def list(self, *, filters: Mapping[str, Any] | None = None) -> Iterable[Mapping[str, Any]]: ...
    def create(self, *, label: str, drawer_id: int | None = None) -> Mapping[str, Any]: ...
    def soft_delete(self, container_id: int) -> None: ...
    def restore(self, container_id: int) -> None: ...


class InventoryRepo(Protocol):
    def counts_by_storage_location(self) -> Iterable[Mapping[str, Any]]: ...

    def loose_inventory_for_part(self, design_id: str) -> list[dict]: ...


class InventoryService:
    """
    Thin pass-through façade for inventory-like workflows.
    No business logic yet—just a stable seam for future workflows.
    """

    def __init__(
        self,
        drawers: DrawersRepo,
        containers: ContainersRepo,
        inventory: InventoryRepo,
    ) -> None:
        self._drawers = drawers
        self._containers = containers
        self._inventory = inventory

    # Drawers
    def list_drawers(self, *, filters: Mapping[str, Any] | None = None):
        return self._drawers.list(filters=filters)

    def create_drawer(self, *, label: str, description: str | None = None):
        label = (label or "").strip()
        if not label:
            raise ValidationError("label is required")
        # If the underlying repo supports description, pass it through.
        if description is not None and hasattr(self._drawers, "create"):
            try:
                return self._drawers.create(label=label, description=description)  # type: ignore[call-arg]
            except TypeError:
                # Repo.create does not accept description; fall back to label-only
                pass
        return self._drawers.create(label=label)

    def delete_drawer(self, *, drawer_id: int):
        if not isinstance(drawer_id, int) or drawer_id <= 0:
            raise ValidationError("drawer_id must be a positive integer")
        return self._drawers.soft_delete(drawer_id)

    def restore_drawer(self, *, drawer_id: int):
        if not isinstance(drawer_id, int) or drawer_id <= 0:
            raise ValidationError("drawer_id must be a positive integer")
        return self._drawers.restore(drawer_id)

    # Containers
    def list_containers(self, *, filters: Mapping[str, Any] | None = None):
        return self._containers.list(filters=filters)

    def create_container(self, *, label: str, drawer_id: int | None = None):
        label = (label or "").strip()
        if not label:
            raise ValidationError("label is required")
        if drawer_id is None:
            raise ValidationError("drawer_id is required")
        if not isinstance(drawer_id, int):
            raise ValidationError("drawer_id must be an integer")
        return self._containers.create(label=label, drawer_id=drawer_id)

    def delete_container(self, *, container_id: int):
        if not isinstance(container_id, int) or container_id <= 0:
            raise ValidationError("container_id must be a positive integer")
        return self._containers.soft_delete(container_id)

    def restore_container(self, *, container_id: int):
        if not isinstance(container_id, int) or container_id <= 0:
            raise ValidationError("container_id must be a positive integer")
        return self._containers.restore(container_id)

    # Inventory rollups
    def storage_location_counts(self):
        return self._inventory.counts_by_storage_location()

    # Per-part loose inventory
    def loose_inventory_for_part(self, design_id: str) -> list[dict]:
        return self._inventory.loose_inventory_for_part(design_id)


# --- Optional convenience helpers for handlers (duck-typed repos) ---
def get_drawer_or_404(service: InventoryService, drawer_id: int):
    # If the drawers repo exposes `get`, use it; otherwise fall back to list filter.
    repo = service._drawers  # noqa: SLF001 (internal access by design in service layer)
    if hasattr(repo, "get"):
        row = repo.get(drawer_id)  # type: ignore[attr-defined]
        if not row:
            raise NotFoundError("Drawer not found", details={"drawer_id": drawer_id})
        return row
    # Fallback: inefficient but safe for now
    rows = [r for r in repo.list(filters={"id": drawer_id})]
    if not rows:
        raise NotFoundError("Drawer not found", details={"drawer_id": drawer_id})
    return rows[0]


def get_container_or_404(service: InventoryService, container_id: int):
    repo = service._containers  # noqa: SLF001
    if hasattr(repo, "get"):
        row = repo.get(container_id)  # type: ignore[attr-defined]
        if not row:
            raise NotFoundError("Container not found", details={"container_id": container_id})
        return row
    rows = [r for r in repo.list(filters={"id": container_id})]
    if not rows:
        raise NotFoundError("Container not found", details={"container_id": container_id})
    return rows[0]
