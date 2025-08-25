from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol


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

    # …add other signatures you actually expose


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

    def create_drawer(self, *, label: str):
        return self._drawers.create(label=label)

    def delete_drawer(self, *, drawer_id: int):
        return self._drawers.soft_delete(drawer_id)

    def restore_drawer(self, *, drawer_id: int):
        return self._drawers.restore(drawer_id)

    # Containers
    def list_containers(self, *, filters: Mapping[str, Any] | None = None):
        return self._containers.list(filters=filters)

    def create_container(self, *, label: str, drawer_id: int | None = None):
        return self._containers.create(label=label, drawer_id=drawer_id)

    def delete_container(self, *, container_id: int):
        return self._containers.soft_delete(container_id)

    def restore_container(self, *, container_id: int):
        return self._containers.restore(container_id)

    # Inventory rollups
    def storage_location_counts(self):
        return self._inventory.counts_by_storage_location()
