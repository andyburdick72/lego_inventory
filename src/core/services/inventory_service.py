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

    def loose_inventory_for_part_color(self, design_id: str, color_id: int) -> list[dict]: ...

    def get_inventory_by_id(self, inventory_id: int) -> dict | None: ...

    def update_inventory_quantity(self, inventory_id: int, quantity: int) -> None: ...

    def update_inventory_location(self, inventory_id: int, container_id: int | None) -> None: ...

    def delete_inventory(self, inventory_id: int) -> None: ...

    def move_inventory(
        self, from_inventory_id: int, to_container_id: int | None, quantity: int
    ) -> None: ...


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

    def loose_inventory_for_part_color(self, design_id: str, color_id: int) -> list[dict]:
        return self._inventory.loose_inventory_for_part_color(design_id, color_id)

    # Loose inventory CRUD operations
    def get_inventory_item(self, inventory_id: int) -> dict:
        """Get a single inventory item by id."""
        if not isinstance(inventory_id, int) or inventory_id <= 0:
            raise ValidationError("inventory_id must be a positive integer")
        item = self._inventory.get_inventory_by_id(inventory_id)
        if not item:
            raise NotFoundError("Inventory item not found", details={"inventory_id": inventory_id})
        return item

    def update_inventory_quantity(self, *, inventory_id: int, quantity: int) -> None:
        """Update the quantity of a specific inventory item."""
        if not isinstance(inventory_id, int) or inventory_id <= 0:
            raise ValidationError("inventory_id must be a positive integer")
        if not isinstance(quantity, int) or quantity < 0:
            raise ValidationError("quantity must be a non-negative integer")
        try:
            self._inventory.update_inventory_quantity(inventory_id, quantity)
        except ValueError as e:
            if "not found" in str(e).lower():
                raise NotFoundError(str(e), details={"inventory_id": inventory_id}) from e
            raise ValidationError(str(e)) from e

    def update_inventory_location(
        self, *, inventory_id: int, container_id: int | None
    ) -> None:
        """Update the location (container_id) of a specific inventory item."""
        if not isinstance(inventory_id, int) or inventory_id <= 0:
            raise ValidationError("inventory_id must be a positive integer")
        if container_id is not None and (not isinstance(container_id, int) or container_id <= 0):
            raise ValidationError("container_id must be a positive integer or None")
        try:
            self._inventory.update_inventory_location(inventory_id, container_id)
        except ValueError as e:
            if "not found" in str(e).lower():
                raise NotFoundError(str(e), details={"inventory_id": inventory_id}) from e
            raise ValidationError(str(e)) from e

    def delete_inventory_item(self, *, inventory_id: int) -> None:
        """Delete a specific inventory item."""
        if not isinstance(inventory_id, int) or inventory_id <= 0:
            raise ValidationError("inventory_id must be a positive integer")
        try:
            self._inventory.delete_inventory(inventory_id)
        except ValueError as e:
            if "not found" in str(e).lower():
                raise NotFoundError(str(e), details={"inventory_id": inventory_id}) from e
            raise ValidationError(str(e)) from e

    def move_inventory(
        self, *, from_inventory_id: int, to_container_id: int | None, quantity: int
    ) -> None:
        """Move a quantity of parts from one inventory item to another location."""
        if not isinstance(from_inventory_id, int) or from_inventory_id <= 0:
            raise ValidationError("from_inventory_id must be a positive integer")
        if to_container_id is not None and (
            not isinstance(to_container_id, int) or to_container_id <= 0
        ):
            raise ValidationError("to_container_id must be a positive integer or None")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError("quantity must be a positive integer")
        try:
            self._inventory.move_inventory(from_inventory_id, to_container_id, quantity)
        except ValueError as e:
            if "not found" in str(e).lower():
                raise NotFoundError(str(e), details={"from_inventory_id": from_inventory_id}) from e
            raise ValidationError(str(e)) from e


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
