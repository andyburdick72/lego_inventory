from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from app.settings import get_settings
from core.services.export_service import ExportService

# Services (match current Protocols in core/services/inventory_service.py)
from core.services.inventory_service import InventoryService
from core.services.set_parts_service import SetPartsService

# Concrete repos (your implementations)
from infra.db.repositories.drawers_repo import DrawersRepo as DrawersRepoImpl
from infra.db.repositories.inventory_repo import InventoryRepo as InventoryRepoImpl
from infra.db.repositories.sets_repo import SetsRepo as SetsRepoImpl

# -----------------------------
# Connection helper
# -----------------------------


def _get_conn() -> sqlite3.Connection:
    """Create a sqlite3 connection using the app settings.

    Tries a few common attribute names for the DB path to be resilient:
    - settings.db_path (preferred)
    - settings.database_path
    - settings.DB_PATH
    """
    settings = get_settings()
    db_path: str | None = (
        getattr(settings, "db_path", None)
        or getattr(settings, "database_path", None)
        or getattr(settings, "DB_PATH", None)
    )
    if not db_path:
        raise RuntimeError(
            "Database path not found in settings (expected 'db_path' or 'database_path')."
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# Adapters to satisfy Protocols
# -----------------------------


class _DrawersRepoAdapter:
    """Adapts your concrete DrawersRepoImpl to the DrawersRepo Protocol.

    Implements read methods now; write methods raise NotImplementedError for this skeleton step.
    """

    def __init__(self, impl: DrawersRepoImpl) -> None:
        self._impl = impl

    # Protocol: def list(self, *, filters: Mapping[str, Any] | None = None) -> Iterable[Mapping[str, Any]]
    def list(self, *, filters: Mapping[str, Any] | None = None):
        # Your concrete repo exposes list_drawers() without filters for now.
        # We ignore filters in this skeleton; you can extend later.
        return self._impl.list_drawers()

    # Protocol: def create(self, *, label: str) -> Mapping[str, Any]
    def create(self, *, label: str):
        raise NotImplementedError("Drawer create not wired yet in skeleton services layer")

    # Protocol: def soft_delete(self, drawer_id: int) -> None
    def soft_delete(self, drawer_id: int) -> None:
        raise NotImplementedError("Drawer soft_delete not wired yet in skeleton services layer")

    # Protocol: def restore(self, drawer_id: int) -> None
    def restore(self, drawer_id: int) -> None:
        raise NotImplementedError("Drawer restore not wired yet in skeleton services layer")


class _ContainersRepoAdapter:
    """Adapts DrawersRepoImpl container reads to the ContainersRepo Protocol."""

    def __init__(self, impl: DrawersRepoImpl) -> None:
        self._impl = impl

    # Protocol: def list(self, *, filters: Mapping[str, Any] | None = None) -> Iterable[Mapping[str, Any]]
    def list(self, *, filters: Mapping[str, Any] | None = None):
        filters = dict(filters or {})
        drawer_id = filters.get("drawer_id")
        if drawer_id is None:
            return []
        return self._impl.list_containers_with_counts(int(drawer_id))

    # Protocol: def create(self, *, label: str, drawer_id: int | None = None) -> Mapping[str, Any]
    def create(self, *, label: str, drawer_id: int | None = None):
        raise NotImplementedError("Container create not wired yet in skeleton services layer")

    # Protocol: def soft_delete(self, container_id: int) -> None
    def soft_delete(self, container_id: int) -> None:
        raise NotImplementedError("Container soft_delete not wired yet in skeleton services layer")

    # Protocol: def restore(self, container_id: int) -> None
    def restore(self, container_id: int) -> None:
        raise NotImplementedError("Container restore not wired yet in skeleton services layer")


class _InventoryRepoAdapter:
    """Adapts InventoryRepoImpl to the InventoryRepo Protocol expected by the service."""

    def __init__(self, impl: InventoryRepoImpl) -> None:
        self._impl = impl

    # Protocol: def counts_by_storage_location(self) -> Iterable[Mapping[str, Any]]
    def counts_by_storage_location(self):
        # Your concrete repo method name is storage_location_counts(filters)
        return self._impl.storage_location_counts(filters=None)


class _SetsRepoAdapter:
    """
    Adapts SetsRepoImpl to the SetsRepo Protocol expected by SetPartsService.
    Protocol: get(set_number=...) -> Mapping | None
    """

    def __init__(self, impl: SetsRepoImpl) -> None:
        self._impl = impl

    def get(self, *, set_number: str):
        # Concrete uses get_set_by_num(set_num)
        return self._impl.get_set_by_num(set_number)


class _SetPartsRepoAdapter:
    """
    Adapts SetsRepoImpl to the SetPartsRepo Protocol expected by SetPartsService.
    Protocol: list_for_set(set_number=...) -> Iterable[Mapping]
              upsert_for_set(...) -> None (not wired in skeleton)
    """

    def __init__(self, impl: SetsRepoImpl) -> None:
        self._impl = impl

    def list_for_set(self, *, set_number: str):
        # Concrete uses list_parts_for_set(set_num)
        return self._impl.list_parts_for_set(set_number)

    def upsert_for_set(self, *, set_number: str, parts):
        raise NotImplementedError("Set parts upsert not wired in skeleton services layer")


class _ExportRepoAdapter:
    """
    Placeholder adapter for ExportService.
    Until export queries are extracted from handlers into a repo,
    this adapter just raises NotImplementedError.
    """

    def export_rows(
        self,
        *,
        table_key: str,
        filters: Mapping[str, Any] | None = None,
        order_by: str | None = None,
    ):
        raise NotImplementedError(
            "Export repo not wired yet; CSV logic still lives in the handler."
        )


# -----------------------------
# Factories used by route handlers
# -----------------------------


def get_inventory_service() -> InventoryService:
    conn = _get_conn()
    drawers_impl = DrawersRepoImpl(conn)
    inventory_impl = InventoryRepoImpl(conn)

    drawers = _DrawersRepoAdapter(drawers_impl)
    containers = _ContainersRepoAdapter(drawers_impl)
    inventory = _InventoryRepoAdapter(inventory_impl)

    return InventoryService(drawers=drawers, containers=containers, inventory=inventory)


def inventory_service_for_conn(conn: sqlite3.Connection) -> InventoryService:
    drawers_impl = DrawersRepoImpl(conn)
    inventory_impl = InventoryRepoImpl(conn)

    drawers = _DrawersRepoAdapter(drawers_impl)
    containers = _ContainersRepoAdapter(drawers_impl)
    inventory = _InventoryRepoAdapter(inventory_impl)

    return InventoryService(drawers=drawers, containers=containers, inventory=inventory)


def get_set_parts_service() -> SetPartsService:
    conn = _get_conn()
    sets_impl = SetsRepoImpl(conn)
    sets = _SetsRepoAdapter(sets_impl)
    set_parts = _SetPartsRepoAdapter(sets_impl)
    return SetPartsService(sets=sets, set_parts=set_parts)


def get_export_service() -> ExportService:
    exporter = _ExportRepoAdapter()
    return ExportService(exporter=exporter)
