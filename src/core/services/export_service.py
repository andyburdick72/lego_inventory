from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol


class ExportRepo(Protocol):
    def export_rows(
        self,
        *,
        table_key: str,
        filters: Mapping[str, Any] | None = None,
        order_by: str | None = None,
    ) -> Iterable[Mapping[str, Any]]: ...


class ExportService:
    """
    Façade for CSV/rows export. Keeps API stable while repos evolve.
    """

    def __init__(self, exporter: ExportRepo) -> None:
        self._export = exporter

    def rows(
        self,
        *,
        table_key: str,
        filters: Mapping[str, Any] | None = None,
        order_by: str | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        return self._export.export_rows(table_key=table_key, filters=filters, order_by=order_by)
