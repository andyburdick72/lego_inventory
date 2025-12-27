from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any, cast

from fastapi import Depends

from app.errors import DuplicateError
from app.settings import get_settings
from core.services.export_service import ExportService

# Services (match current Protocols in core/services/inventory_service.py)
from core.services.inventory_service import InventoryService

# Parts service/repo
from core.services.location_reconciliation_service import LocationReconciliationService
from core.services.mismatch_service import MismatchService
from core.services.parts_service import PartsService
from core.services.search_service import SearchService
from core.services.set_parts_service import SetPartsService
from core.services.storage_hierarchy_service import StorageHierarchyService

# Concrete repos (your implementations)
from infra.db.repositories.drawers_repo import DrawersRepo as DrawersRepoImpl
from infra.db.repositories.drawers_repo import DuplicateLabelError as _DBDuplicateLabelError
from infra.db.repositories.inventory_repo import InventoryRepo as InventoryRepoImpl
from infra.db.repositories.parts_repo import PartsRepo as PartsRepoImpl
from infra.db.repositories.search_repo import SearchRepo as SearchRepoImpl
from infra.db.repositories.sets_repo import SetsRepo as SetsRepoImpl

# -----------------------------
# Connection helper
# -----------------------------

_SCHEMA_INIT_FOR_DB_PATHS: set[str] = set()


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
    # check_same_thread=False allows connections to be used across threads (required for FastAPI async)
    # Increased timeout to 10s for better handling of concurrent access in tests
    conn = sqlite3.connect(
        db_path, timeout=10.0, isolation_level=None, check_same_thread=False
    )  # autocommit mode
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")  # wait up to 10s if the DB is locked
        conn.execute("PRAGMA synchronous=NORMAL;")  # reasonable durability for WAL
        conn.execute("PRAGMA foreign_keys=ON;")  # safety
    except Exception:
        # Best-effort in case PRAGMAs aren't supported
        pass

    # Ensure schema exists for this DB path (important for tests that point APP_DB_PATH at a fresh
    # temporary file). This is idempotent (CREATE TABLE IF NOT EXISTS).
    db_path_key = str(db_path)
    if db_path_key not in _SCHEMA_INIT_FOR_DB_PATHS:
        try:
            from infra.db.inventory_db import init_db

            init_db()
            _SCHEMA_INIT_FOR_DB_PATHS.add(db_path_key)
        except Exception:
            # If schema init fails, let downstream code raise a clearer error.
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

    def get_put_away_bin(self) -> dict | None:
        """Get the container marked as the put away bin."""
        return self._impl.get_put_away_bin()


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

    def loose_inventory_for_part_color(self, design_id: str, color_id: int) -> list[dict]:
        return self._impl.loose_inventory_for_part_color(design_id, color_id)

    def get_loose_inventory_totals(self) -> list[dict]:
        return self._impl.get_loose_inventory_totals()

    def get_part_color_info(self, design_id: str, color_id: int) -> dict | None:
        return self._impl.get_part_color_info(design_id, color_id)

    def update_loose_inventory_quantity(
        self, design_id: str, color_id: int, new_quantity: int
    ) -> None:
        return self._impl.update_loose_inventory_quantity(design_id, color_id, new_quantity)

    def get_inventory_by_location(
        self, design_id: str, color_id: int, drawer_id: int | None, container_id: int | None
    ) -> list[dict]:
        return self._impl.get_inventory_by_location(design_id, color_id, drawer_id, container_id)

    def get_inventory_totals_by_location(self, design_id: str, color_id: int) -> list[dict]:
        return self._impl.get_inventory_totals_by_location(design_id, color_id)

    def set_inventory_quantity_at_location(
        self,
        design_id: str,
        color_id: int,
        quantity: int,
        drawer_id: int | None,
        container_id: int | None,
    ) -> None:
        return self._impl.set_inventory_quantity_at_location(
            design_id, color_id, quantity, drawer_id, container_id
        )

    def get_inventory_by_id(self, inventory_id: int) -> dict | None:
        return self._impl.get_inventory_by_id(inventory_id)

    def update_inventory_quantity(self, inventory_id: int, quantity: int) -> None:
        return self._impl.update_inventory_quantity(inventory_id, quantity)

    def update_inventory_location(self, inventory_id: int, container_id: int | None) -> None:
        return self._impl.update_inventory_location(inventory_id, container_id)

    def delete_inventory(self, inventory_id: int) -> None:
        return self._impl.delete_inventory(inventory_id)

    def move_inventory(
        self, from_inventory_id: int, to_container_id: int | None, quantity: int
    ) -> None:
        return self._impl.move_inventory(from_inventory_id, to_container_id, quantity)

    def find_element_location(self, design_id: str, color_id: int) -> list[dict]:
        return self._impl.find_element_location(design_id, color_id)

    def find_part_location(self, design_id: str) -> list[dict]:
        return self._impl.find_part_location(design_id)

    def find_category_location(self, part_category_id: int) -> list[dict]:
        return self._impl.find_category_location(part_category_id)

    def analyze_element_storage_patterns(self) -> list[dict]:
        return self._impl.analyze_element_storage_patterns()

    def analyze_part_storage_patterns(self) -> list[dict]:
        return self._impl.analyze_part_storage_patterns()

    def analyze_category_storage_patterns(self) -> list[dict]:
        return self._impl.analyze_category_storage_patterns()

    def analyze_element_storage_strategies(self) -> list[dict]:
        return self._impl.analyze_element_storage_strategies()


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

    def list_sets_with_statuses(self, statuses: list[str]) -> list[Mapping[str, Any]]:
        return cast(list[Mapping[str, Any]], self._impl.list_sets_with_statuses(statuses))


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


def get_inventory_service(
    conn: sqlite3.Connection = Depends(get_db_connection),
) -> InventoryService:
    """Get InventoryService with a connection from the current request context."""
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


def get_set_parts_service(conn: sqlite3.Connection = Depends(get_db_connection)) -> SetPartsService:
    """Get SetPartsService with a connection from the current request context."""
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


def get_parts_service(conn: sqlite3.Connection = Depends(get_db_connection)) -> PartsService:
    """Get PartsService with a connection from the current request context."""
    parts_impl = PartsRepoImpl(conn)
    return PartsService(parts=parts_impl)


def get_mismatch_service(conn: sqlite3.Connection = Depends(get_db_connection)) -> MismatchService:
    """Get MismatchService with a connection from the current request context."""
    sets_impl = SetsRepoImpl(conn)
    inventory_impl = InventoryRepoImpl(conn)

    sets = _SetsRepoAdapter(sets_impl)
    set_parts = _SetPartsRepoAdapter(sets_impl)
    inventory = _InventoryRepoAdapter(inventory_impl)

    return MismatchService(sets=sets, set_parts=set_parts, inventory=inventory)


def get_location_reconciliation_service(
    conn: sqlite3.Connection = Depends(get_db_connection),
) -> LocationReconciliationService:
    """Get LocationReconciliationService with a connection from the current request context."""
    sets_impl = SetsRepoImpl(conn)
    inventory_impl = InventoryRepoImpl(conn)
    drawers_impl = DrawersRepoImpl(conn)

    sets = _SetsRepoAdapter(sets_impl)
    set_parts = _SetPartsRepoAdapter(sets_impl)
    inventory = _InventoryRepoAdapter(inventory_impl)
    drawers = _DrawersRepoAdapter(drawers_impl)

    return LocationReconciliationService(
        sets=sets, set_parts=set_parts, inventory=inventory, drawers=drawers
    )


def get_storage_hierarchy_service(
    conn: sqlite3.Connection = Depends(get_db_connection),
) -> StorageHierarchyService:
    """Get StorageHierarchyService with a connection from the current request context."""
    inventory_impl = InventoryRepoImpl(conn)
    parts_impl = PartsRepoImpl(conn)

    inventory = _InventoryRepoAdapter(inventory_impl)
    parts = parts_impl  # PartsRepoImpl already matches the Protocol

    return StorageHierarchyService(inventory=inventory, parts=parts)


def get_search_service(
    conn: sqlite3.Connection = Depends(get_db_connection),
) -> SearchService:
    """Get SearchService with a connection from the current request context."""
    search_impl = SearchRepoImpl(conn)
    return SearchService(search_repo=search_impl)
