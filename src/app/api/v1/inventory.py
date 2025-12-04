"""FastAPI router for inventory endpoints."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.adapters import row_to_inventory_item, rows_to
from app.di import get_db_connection, get_inventory_service
from core.dtos import InventoryItemDTO
from core.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])


# Response models
class PartCountDTO(BaseModel):
    design_id: str
    part_name: str
    total_qty: int
    part_url: Optional[str] = None
    part_img_url: Optional[str] = None


class PartColorCountDTO(BaseModel):
    design_id: str
    part_name: str
    color_id: int
    color_name: str
    hex: Optional[str] = None
    total_qty: int
    part_url: Optional[str] = None
    part_img_url: Optional[str] = None


class LocationCountDTO(BaseModel):
    location: str
    total_qty: int


class TotalPartCountDTO(BaseModel):
    total_count: int


@router.get("/total-count", response_model=TotalPartCountDTO)
def get_total_part_count(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get total part count across all inventory (loose parts + parts in sets)."""
    row = conn.execute(
        """
        SELECT 
            COALESCE((
                SELECT SUM(i.quantity)
                FROM inventory i
                WHERE i.status = 'loose'
            ), 0) +
            COALESCE((
                SELECT SUM(sp.quantity)
                FROM set_parts sp
                JOIN sets s ON s.set_num = sp.set_num
                WHERE s.status IN ('built','wip','in_box','teardown')
            ), 0) AS total_count
        """
    ).fetchone()

    total_count = int(row["total_count"] or 0) if row else 0
    return TotalPartCountDTO(total_count=total_count)


@router.get("/loose", response_model=list[InventoryItemDTO])
def list_loose_inventory(conn: sqlite3.Connection = Depends(get_db_connection)):
    """List all loose inventory items."""
    rows = conn.execute(
        """
        SELECT  i.design_id AS part_id,
                i.color_id,
                c.name AS color_name,
                c.hex AS color_hex,
                i.quantity,
                i.status,
                COALESCE(d.name, i.drawer) AS drawer_name,
                d.id AS drawer_id,
                COALESCE(c2.name, i.container) AS container_label,
                c2.id AS container_id,
                NULL AS set_number,
                NULL AS set_name,
                p.name AS part_name,
                p.part_img_url AS image_url,
                p.part_url AS rebrickable_url
        FROM inventory i
        JOIN parts  p ON p.design_id = i.design_id
        JOIN colors c ON c.id = i.color_id
        LEFT JOIN containers c2 ON i.container_id = c2.id
        LEFT JOIN drawers d ON c2.drawer_id = d.id
        WHERE i.status = 'loose'
        ORDER BY i.quantity DESC, p.design_id, i.color_id
        """
    ).fetchall()

    rows_as_dicts = [dict(row) for row in rows]
    items = rows_to(row_to_inventory_item, rows_as_dicts)
    return [d.model_dump() for d in items]


@router.get("/part-counts", response_model=list[PartCountDTO])
def get_part_counts(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get total part counts across all inventory."""
    rows = conn.execute(
        """
        SELECT design_id, part_name, part_url, part_img_url, SUM(total_qty) AS total_qty
        FROM (
            -- Loose parts
            SELECT i.design_id,
                   p.name AS part_name,
                   p.part_url AS part_url,
                   p.part_img_url AS part_img_url,
                   SUM(i.quantity) AS total_qty
            FROM inventory i
            JOIN parts p ON i.design_id = p.design_id
            WHERE i.status = 'loose'
            GROUP BY i.design_id, p.name, p.part_url, p.part_img_url

            UNION ALL

            -- Parts in sets
            SELECT sp.design_id,
                   p.name AS part_name,
                   p.part_url AS part_url,
                   p.part_img_url AS part_img_url,
                   SUM(sp.quantity) AS total_qty
            FROM set_parts sp
            JOIN parts p ON sp.design_id = p.design_id
            JOIN sets s  ON s.set_num   = sp.set_num
            WHERE s.status IN ('built','wip','in_box','teardown')
            GROUP BY sp.design_id, p.name, p.part_url, p.part_img_url
        ) q
        GROUP BY design_id, part_name, part_url, part_img_url
        ORDER BY total_qty DESC
        """
    ).fetchall()

    result = []
    for r in rows:
        part_url = r.get("part_url")
        if not part_url and r.get("design_id"):
            part_url = f"https://rebrickable.com/parts/{r['design_id']}/"

        part_img_url = r.get("part_img_url")
        if not part_img_url:
            part_img_url = "https://rebrickable.com/static/img/nil.png"

        result.append(
            PartCountDTO(
                design_id=str(r.get("design_id", "")),
                part_name=str(r.get("part_name", "")),
                total_qty=int(r.get("total_qty", 0)),
                part_url=part_url,
                part_img_url=part_img_url,
            )
        )
    return result


@router.get("/part-color-counts", response_model=list[PartColorCountDTO])
def get_part_color_counts(conn: sqlite3.Connection = Depends(get_db_connection)):
    """Get part counts grouped by part and color."""
    rows = conn.execute(
        """
        SELECT
            pc.design_id,
            p.name         AS part_name,
            pc.color_id,
            c.name         AS color_name,
            c.hex          AS color_hex,
            p.part_url     AS part_url,
            p.part_img_url AS part_img_url,
            SUM(pc.total_qty) AS total_qty
        FROM (
            SELECT i.design_id, i.color_id, SUM(i.quantity) AS total_qty
            FROM inventory i
            WHERE i.status = 'loose'
            GROUP BY i.design_id, i.color_id

            UNION ALL

            SELECT sp.design_id, sp.color_id, SUM(sp.quantity) AS total_qty
            FROM set_parts sp
            JOIN sets s  ON s.set_num   = sp.set_num
            WHERE s.status IN ('built','wip','in_box','teardown')
            GROUP BY sp.design_id, sp.color_id
        ) pc
        JOIN parts  p ON p.design_id = pc.design_id
        LEFT JOIN colors c ON c.id = pc.color_id
        GROUP BY pc.design_id, p.name, pc.color_id, c.name, c.hex, p.part_url, p.part_img_url
        ORDER BY total_qty DESC
        """
    ).fetchall()

    result = []
    for r in rows:
        design_id = str(r.get("design_id", ""))
        color_id = r.get("color_id")
        hex_value = r.get("color_hex")
        if hex_value:
            hex_value = hex_value.lstrip("#")

        part_url = r.get("part_url")
        if not part_url and design_id and color_id:
            part_url = f"https://rebrickable.com/parts/{design_id}/{int(color_id)}/"
        elif not part_url and design_id:
            part_url = f"https://rebrickable.com/parts/{design_id}/"

        part_img_url = r.get("part_img_url")
        if not part_img_url:
            part_img_url = "https://rebrickable.com/static/img/nil.png"

        result.append(
            PartColorCountDTO(
                design_id=design_id,
                part_name=str(r.get("part_name", "")),
                color_id=int(color_id or 0),
                color_name=str(r.get("color_name", "") or "(unknown)"),
                hex=hex_value,
                total_qty=int(r.get("total_qty", 0)),
                part_url=part_url,
                part_img_url=part_img_url,
            )
        )
    return result


@router.get("/location-counts", response_model=list[LocationCountDTO])
def get_location_counts(
    service: InventoryService = Depends(get_inventory_service),
):
    """Get inventory totals grouped by storage location."""
    rows = service.storage_location_counts()
    result = []
    for r in rows:
        drawer = r.get("drawer_name") or ""
        container = r.get("container_name") or ""
        if drawer and container:
            location = f"{drawer} / {container}"
        elif drawer:
            location = drawer
        elif container:
            location = container
        else:
            location = "(unknown)"

        result.append(
            LocationCountDTO(
                location=location,
                total_qty=int(r.get("total_quantity", r.get("total_qty", 0)) or 0),
            )
        )
    return result

