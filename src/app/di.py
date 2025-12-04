from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any, cast

from app.errors import DuplicateError
from app.settings import get_settings
from core.services.export_service import ExportService

# Services (match current Protocols in core/services/inventory_service.py)
from core.services.inventory_service import InventoryService

# Parts service/repo
from core.services.parts_service import PartsService
from core.services.set_parts_service import SetPartsService

# Concrete repos (your implementations)
from infra.db.repositories.drawers_repo import DrawersRepo as DrawersRepoImpl
from infra.db.repositories.drawers_repo import DuplicateLabelError as _DBDuplicateLabelError
from infra.db.repositories.inventory_repo import InventoryRepo as InventoryRepoImpl
from infra.db.repositories.parts_repo import PartsRepo as PartsRepoImpl
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

    # Enable WAL + busy timeout and autocommit to avoid long-held write locks in tests
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)  # autocommit mode
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")  # wait up to 5s if the DB is locked
        conn.execute("PRAGMA synchronous=NORMAL;")  # reasonable durability for WAL
        conn.execute("PRAGMA foreign_keys=ON;")  # safety
    except Exception:
        # Best-effort in case PRAGMAs aren't supported
        pass
    return conn


def get_db_connection() -> sqlite3.Connection:
    """FastAPI dependency to get a database connection."""
    return _get_conn()


# Normalize various row-like objects (sqlite3.Row, dict-like, etc.) to Mapping[str, Any]
def _as_mapping(row: Any) -> Mapping[str, Any]:
    if isinstance(row, Mapping):
        return cast(Mapping[str, Any], row)
    # If DB returns a bare integer id, normalize to {"id": id}
    if isinstance(row, int):
        return {"id": row}
    # sqlite3.Row supports .keys() and index access by column name
    try:
        keys = row.keys()  # type: ignore[attr-defined]
        return {k: row[k] for k in keys}  # type: ignore[index]
    except Exception:
        return {"value": row}


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
        # Prefer aggregated variant to preserve counts expected by templates/DTOs
        rows = (
            self._impl.list_drawers_with_counts()
            if hasattr(self._impl, "list_drawers_with_counts")
            else self._impl.list_drawers()
        )
        # Normalize keys: add aliases some templates expect
        normalized: list[dict] = []
        for row in rows:
            d = dict(row)
            if "container_count" in d and "containers" not in d:
                try:
                    d["containers"] = (
                        int(d["container_count"]) if d["container_count"] is not None else 0
                    )
                except Exception:
                    d["containers"] = d["container_count"]
            if "part_count" in d and "parts" not in d:
                try:
                    d["parts"] = int(d["part_count"]) if d["part_count"] is not None else 0
                except Exception:
                    d["parts"] = d["part_count"]
            normalized.append(d)
        return normalized

    # Protocol: def create(self, *, label: str) -> Mapping[str, Any]
    def create(self, *, label: str, description: str | None = None) -> Mapping[str, Any]:
        """Create a drawer via the concrete repo, tolerating different kw names/signatures."""
        impl = self._impl
        try:
            # Call concrete impl, accepting different kw signatures
            try:
                row = impl.create_drawer(name=label, description=description)  # type: ignore[call-arg]
            except TypeError:
                try:
                    row = impl.create_drawer(label=label, description=description)  # type: ignore[call-arg]
                except TypeError:
                    try:
                        row = impl.create_drawer(name=label)  # type: ignore[call-arg]
                    except TypeError:
                        row = impl.create_drawer(label=label)  # type: ignore[call-arg]
            return _as_mapping(row)
        except _DBDuplicateLabelError as e:
            # Normalize to app-level DuplicateError so HTTP layer maps to 409
            raise DuplicateError(str(e) or "Duplicate drawer name") from e

    # Protocol: def soft_delete(self, drawer_id: int) -> None
    def soft_delete(self, drawer_id: int) -> None:
        impl = self._impl
        if hasattr(impl, "soft_delete_drawer"):
            impl.soft_delete_drawer(drawer_id)  # type: ignore[attr-defined]
            return
        if hasattr(impl, "delete_drawer"):
            impl.delete_drawer(drawer_id=drawer_id)  # type: ignore[attr-defined]
            return
        raise NotImplementedError("No soft_delete/delete method for drawers on implementation")

    # Protocol: def restore(self, drawer_id: int) -> None
    def restore(self, drawer_id: int) -> None:
        impl = self._impl
        if hasattr(impl, "restore_drawer"):
            impl.restore_drawer(drawer_id)  # type: ignore[attr-defined]
            return
        if hasattr(impl, "undelete_drawer"):
            impl.undelete_drawer(drawer_id)  # type: ignore[attr-defined]
            return
        raise NotImplementedError("No restore/undelete method for drawers on implementation")


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
    def create(self, *, label: str, drawer_id: int | None = None) -> Mapping[str, Any]:
        impl = self._impl
        if drawer_id is None:
            raise ValueError("drawer_id is required to create a container")
        try:
            # Try common signatures
            if hasattr(impl, "create_container"):
                try:
                    row = impl.create_container(drawer_id=drawer_id, name=label)  # type: ignore[call-arg]
                except TypeError:
                    try:
                        row = impl.create_container(drawer_id=drawer_id, label=label)  # type: ignore[call-arg]
                    except TypeError:
                        # Some implementations may expect positional args (drawer_id, name)
                        row = impl.create_container(drawer_id, label)  # type: ignore[misc]
            else:
                raise NotImplementedError(
                    "create_container not available on DrawersRepo implementation"
                )
            return _as_mapping(row)
        except _DBDuplicateLabelError as e:
            # Normalize to app-level DuplicateError so HTTP layer maps to 409
            raise DuplicateError(str(e) or "Duplicate label in this drawer") from e

    # Protocol: def soft_delete(self, container_id: int) -> None
    def soft_delete(self, container_id: int) -> None:
        impl = self._impl
        if hasattr(impl, "soft_delete_container"):
            impl.soft_delete_container(container_id)  # type: ignore[attr-defined]
            return
        if hasattr(impl, "delete_container"):
            impl.delete_container(container_id)  # type: ignore[attr-defined]
            return
        raise NotImplementedError("No soft_delete/delete method for containers on implementation")

    # Protocol: def restore(self, container_id: int) -> None
    def restore(self, container_id: int) -> None:
        impl = self._impl
        if hasattr(impl, "restore_container"):
            impl.restore_container(container_id)  # type: ignore[attr-defined]
            return
        if hasattr(impl, "undelete_container"):
            impl.undelete_container(container_id)  # type: ignore[attr-defined]
            return
        raise NotImplementedError("No restore/undelete method for containers on implementation")


class _InventoryRepoAdapter:
    """Adapts InventoryRepoImpl to the InventoryRepo Protocol expected by the service."""

    def __init__(self, impl: InventoryRepoImpl) -> None:
        self._impl = impl

    # Protocol: def counts_by_storage_location(self) -> Iterable[Mapping[str, Any]]
    def counts_by_storage_location(self):
        # Your concrete repo method name is storage_location_counts(filters)
        return self._impl.storage_location_counts(filters=None)

    def loose_inventory_for_part(self, design_id: str) -> list[dict]:
        return self._impl.loose_inventory_for_part(design_id)


class _SetsRepoAdapter:
    """
    Adapts SetsRepoImpl to the SetsRepo Protocol expected by SetPartsService.
    Protocol: get(set_number=...) -> Mapping | None
    """

    def __init__(self, impl: SetsRepoImpl) -> None:
        self._impl = impl

    def get(self, *, set_number: str) -> Mapping[str, Any] | None:
        # Concrete uses get_set_by_num(set_num)
        return self._impl.get_set_by_num(set_number)

    def sets_for_part(self, design_id: str) -> list[Mapping[str, Any]]:
        return cast(list[Mapping[str, Any]], self._impl.sets_for_part(design_id))

    def sets_for_part_with_colors(self, design_id: str) -> list[Mapping[str, Any]]:
        return cast(list[Mapping[str, Any]], self._impl.sets_for_part_with_colors(design_id))


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


# -----------------------------
# Parts service factory
# -----------------------------


def get_parts_service() -> PartsService:
    conn = _get_conn()
    parts_impl = PartsRepoImpl(conn)
    return PartsService(parts=parts_impl)
