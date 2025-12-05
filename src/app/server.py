"""
[DEPRECATED] Custom LEGO inventory management system web UI (lightweight HTTP server + Jinja templates).

⚠️  THIS SERVER IS DEPRECATED ⚠️

All functionality has been migrated to:
- FastAPI backend: src/app/api/main.py (port 8001)
- Next.js frontend: frontend/ (port 3000)

This file is kept for reference only and will be removed in a future version.

To run the modern stack:
  ./dev.sh  # Starts FastAPI server (default)
  
To run this legacy server (for reference only):
  SERVER_TYPE=legacy ./dev.sh

Original routes (for reference):
* "/"                  – Loose Parts (master inventory table: part • color • location • status)
* "/parts/<design_id>" – Part detail (tabs: Loose Parts, In Sets)
* "/drawers"           – Drawers index (create/rename/delete)
* "/drawers/<id>"      – Drawer detail (containers list; actions)
* "/containers/<id>"   – Container detail (parts in container)
* "/my-sets"           – Sets index (all sets)
* "/sets/<set_num>"    – Set detail (parts in set)
* "/part-counts"       – Part totals across site
* "/part-color-counts" – Part+Color totals across site
* "/location-counts"   – Storage location totals
* "/export"            – CSV export endpoint (driven by DataTables state)

Architecture:
* HTML is rendered with Jinja templates in src/app/templates (base + partials).
* Tables are rendered via partials/table.html and initialized by static/js/tables.js.
* Page actions (rename/delete/etc.) are handled by static/js/app.js.
* Styling is in /static/styles.css; Bootstrap 5 and jQuery DataTables are loaded via CDN.

Dependencies:
* Standard library + Jinja2 (see requirements.txt). No Flask/WSGI; runs via BaseHTTPRequestHandler.

Usage:
    python3 src/app/server.py  # [DEPRECATED - use FastAPI + Next.js instead]
"""

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import sqlite3
import sys
import traceback
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from pathlib import Path as _Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

# Ensure repo root is on sys.path when running as `python3 src/app/server.py`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

from app.adapters import (  # noqa: E402
    row_to_container_summary,
    row_to_drawer_summary,
    rows_to,
)
from app.di import get_inventory_service, get_parts_service, get_set_parts_service  # noqa: E402
from app.errors import (  # noqa: E402
    AppError,
    BadRequestError,
    ConflictError,
    DatabaseError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from core.enums import Status  # noqa: E402
from utils.routes import (  # noqa: E402
    container_url,
    drawer_url,
    part_url,
    rebrickable_part_color_url,
    rebrickable_part_url,
    rebrickable_set_url,
    set_url,
)

_BASE_DIR = _Path(__file__).resolve().parent
_TEMPLATE_DIR = (_BASE_DIR / "templates").resolve()
_STATIC_DIR = (_BASE_DIR / "static").resolve()

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=False,
)


def _url_for(endpoint: str, **values) -> str:
    """Very small url_for shim for templates."""
    if endpoint == "static":
        fn = str(values.get("filename", "")).lstrip("/")
        return f"/static/{fn}"
    mapping = {
        "index": "/",
        "drawers": "/drawers",
        "containers": "/containers",
        "sets": "/my-sets",
        "parts": "/",
        "export_csv": "/export",
    }
    return mapping.get(endpoint, "/")


def _render_template(name: str, **context) -> str:
    tmpl = _jinja_env.get_template(name)
    context.setdefault("url_for", _url_for)
    return tmpl.render(**context)


from infra.db import inventory_db as db  # noqa: E402

SET_STATUSES = {Status.BUILT.value, Status.WIP.value, Status.IN_BOX.value, Status.TEARDOWN.value}

# Mapping from status code to display-friendly name
STATUS_DISPLAY_NAMES = {
    "built": "Built",
    "wip": "Work in Progress",
    "in_box": "In Box",
    "teardown": "Teardown",
    "loose": "Loose",
}


def _query_master_rows() -> list[dict]:
    """
    Return aggregated rows:
    design_id, part_name, color_name, hex, status, location (drawer/container OR set_number), qty
    """
    with db._connect() as conn:  # pylint: disable=protected-access
        rows = conn.execute(
            """
            SELECT  i.design_id,
                    p.name            AS part_name,
                    p.part_url        AS part_url,
                    p.part_img_url    AS part_img_url,
                    c.name            AS color_name,
                    c.hex             AS hex,
                    i.status,
                    COALESCE(i.set_number, '') AS set_number,
                    COALESCE(d.name, i.drawer)    AS drawer,
                    COALESCE(c2.name, i.container)   AS container,
                    d.id               AS drawer_id,
                    c2.id              AS container_id,
                    SUM(i.quantity)   AS qty
            FROM inventory i
            JOIN parts  p ON p.design_id = i.design_id
            JOIN colors c ON c.id        = i.color_id
            LEFT JOIN containers c2 ON i.container_id = c2.id
            LEFT JOIN drawers d ON c2.drawer_id = d.id
            GROUP BY i.design_id, i.color_id, i.status,
                     i.set_number, COALESCE(d.name, i.drawer), COALESCE(c2.name, i.container)
            ORDER BY p.design_id
            """
        ).fetchall()
    result = []
    for r in rows:
        # Always include drawer and container in the dict for use in table columns
        if r["status"] in SET_STATUSES:
            location = r["set_number"] or "(unknown set)"
        else:
            location = f"{r['drawer']}/{r['container']}".strip("/")
        result.append(
            dict(
                design_id=r["design_id"],
                part_name=r["part_name"],
                part_url=r["part_url"],
                part_img_url=r["part_img_url"],
                color_name=r["color_name"],
                hex=r["hex"],
                status=r["status"],
                location=location,
                drawer=r["drawer"],
                container=r["container"],
                drawer_id=r["drawer_id"],
                container_id=r["container_id"],
                qty=r["qty"],
            )
        )
    return result


def _build_sets_map() -> dict[str, dict[str, list[dict]]]:
    """
    {status: {set_number: [{design_id, part_name, color_name, hex, qty}, …]}}
    Only parts whose status is in SET_STATUSES.
    """
    with db._connect() as conn:  # pylint: disable=protected-access
        rows = conn.execute(
            f"""
            SELECT i.status,
                   i.set_number,
                   i.design_id,
                   p.name  AS part_name,
                   c.name  AS color_name,
                   c.hex   AS hex,
                   SUM(i.quantity) AS qty
            FROM inventory i
            JOIN parts  p ON p.design_id = i.design_id
            JOIN colors c ON c.id        = i.color_id
            WHERE i.status IN ({','.join('?' * len(SET_STATUSES))})
            GROUP BY i.status, i.set_number, i.design_id, i.color_id
            ORDER BY i.status, i.set_number, i.design_id
            """,
            tuple(SET_STATUSES),
        ).fetchall()
    sets: dict[str, dict[str, list[dict]]] = {}
    for r in rows:
        status = r["status"]
        set_number = r["set_number"] or "(unknown)"
        sets.setdefault(status, {}).setdefault(set_number, []).append(
            dict(
                design_id=r["design_id"],
                part_name=r["part_name"],
                color_name=r["color_name"],
                hex=r["hex"],
                qty=r["qty"],
            )
        )
    return sets


def _numeric_set_sort_key(set_no: str) -> float:
    try:
        return int(set_no)
    except ValueError:
        return float("inf")


# Helper to get display-friendly status name
def _display_status(status: str) -> str:
    if status == "unsorted":
        return "Unsorted"
    st = Status.from_any(status)
    return st.label if st else "Loose"


# --------------------------------------------------------------------------- request-handler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        try:
            # --- Static files ---
            if self.path.startswith("/static/"):
                return self._serve_static()

            # --- JSON API (GET) ---
            if self.path.startswith("/api/"):
                return self._handle_api_get()

            # --- Existing HTML routes ---
            if self.path == "/" or self.path.startswith("/?"):
                self._serve_master()
            elif self.path.startswith("/parts/"):
                m = re.match(r"^/parts/([^/?#]+)", self.path)
                self._serve_part(m.group(1)) if m else self._not_found()
            elif self.path == "/drawers" or re.match(r"^/drawers/\d+", self.path):
                m = re.match(r"^/drawers/(\d+)", self.path)
                if m:
                    self._serve_drawer_detail(int(m.group(1)))
                else:
                    self._serve_drawers()
            elif re.match(r"^/containers/\d+", self.path):
                m = re.match(r"^/containers/(\d+)", self.path)
                self._serve_container_detail(int(m.group(1))) if m else self._not_found()
            elif re.match(r"^/sets/([^/?#]+)", self.path):
                m = re.match(r"^/sets/([^/?#]+)", self.path)
                self._serve_set(m.group(1)) if m else self._not_found()
            elif self.path.startswith("/my-sets"):
                self._serve_all_sets()
            elif self.path.startswith("/part-counts"):
                self._serve_part_counts()
            elif self.path.startswith("/part-color-counts"):
                self._serve_part_color_counts()
            elif self.path.startswith("/location-counts"):
                self._serve_location_counts()
            elif self.path.startswith("/export"):
                self._serve_export()
            else:
                self._not_found()
        except Exception as exc:  # pylint: disable=broad-except
            traceback.print_exc()
            self._handle_unexpected(exc)

    # ------------------------------ JSON helpers
    def _send_json(self, status: int, payload) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, err: AppError) -> None:
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        payload = err.to_dict(request_id=request_id)
        self._send_json(err.http_status, payload)

    def _handle_unexpected(self, exc: Exception) -> None:
        # Coarse mapping of common infra errors; expand as needed
        msg = str(exc) or "Internal error"
        if "UNIQUE constraint failed" in msg:
            err = DatabaseError(details={"hint": "unique_constraint", "message": msg})
        else:
            err = AppError(msg)
        self._send_error(err)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        body = self.rfile.read(length) if length else b""
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    # ------------------------------ typed JSON helpers
    def _parse_int(self, data: dict[str, Any], key: str) -> tuple[bool, int | None, str | None]:
        """Safely parse an integer field from a JSON dict.
        Returns (ok, value, error). If not ok, value is None and error is a message.
        """
        val = data.get(key)
        if val is None:
            return False, None, f"{key} is required"
        try:
            return True, int(cast(Any, val)), None
        except (TypeError, ValueError):
            return False, None, f"{key} must be an integer"

    def _parse_optional_int(
        self, data: dict[str, Any], key: str
    ) -> tuple[bool, int | None, str | None]:
        """Parse an optional integer field; missing returns (True, None, None)."""
        if key not in data or data.get(key) is None:
            return True, None, None
        try:
            return True, int(cast(Any, data.get(key))), None
        except (TypeError, ValueError):
            return False, None, f"{key} must be an integer"

    def _serve_static(self):
        # Map /static/... to files under _STATIC_DIR
        rel = self.path[len("/static/") :]
        safe_rel = rel.lstrip("/").replace("..", "")
        file_path = (_STATIC_DIR / safe_rel).resolve()
        try:
            # Ensure path is inside static dir
            if not str(file_path).startswith(str(_STATIC_DIR)):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
                return
            if not file_path.is_file():
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")
                return

            # Content types (minimal)
            if file_path.suffix == ".js":
                ctype = "application/javascript; charset=utf-8"
            elif file_path.suffix == ".css":
                ctype = "text/css; charset=utf-8"
            else:
                ctype = "application/octet-stream"

            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._handle_unexpected(e)

    # ------------------------------ API GET router
    def _handle_api_get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        try:
            if path == "/api/drawers":
                # Use InventoryService (read-only) to fetch drawers with counts
                svc = get_inventory_service()
                rows = svc.list_drawers()
                items = rows_to(row_to_drawer_summary, rows)
                payload = [d.model_dump() for d in items]
                return self._send_json(200, payload)

            if path == "/api/containers":
                drawer_id = qs.get("drawer_id", [None])[0]
                if drawer_id is None:
                    return self._send_error(BadRequestError("drawer_id is required"))
                svc = get_inventory_service()
                rows = svc.list_containers(filters={"drawer_id": int(drawer_id)})
                items = rows_to(row_to_container_summary, rows)
                payload = [d.model_dump() for d in items]
                return self._send_json(200, payload)
        except Exception as e:
            return self._handle_unexpected(e)

        return self._send_error(NotFoundError("Not Found"))

    # ------------------------------ API write methods
    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/api/"):
            return self._not_found()
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        try:
            # Rename drawer (action-style)
            if path == "/api/drawers/rename":
                ok, did, err = self._parse_int(data, "id")
                if not ok:
                    return self._send_error(ValidationError(err))
                new_name = (data.get("new_name") or data.get("new_label") or "").strip()
                if not new_name:
                    return self._send_error(ValidationError("new_name is required"))
                try:
                    with db._connect() as conn:  # pylint: disable=protected-access
                        db.update_drawer(conn, did, name=new_name)
                    return self._send_json(200, {"updated": did})
                except getattr(db, "DuplicateLabelError", sqlite3.IntegrityError):  # type: ignore[attr-defined]
                    return self._send_error(
                        DuplicateError(
                            "Duplicate drawer name", details={"field": "name", "value": new_name}
                        )
                    )

            # Move drawer (action-style) – updates sort_index
            if path == "/api/drawers/move":
                ok, did, err = self._parse_int(data, "id")
                if not ok:
                    return self._send_error(ValidationError(err))
                ok, new_sort_index, err = self._parse_optional_int(data, "new_sort_index")
                if not ok:
                    return self._send_error(ValidationError(err))
                with db._connect() as conn:  # pylint: disable=protected-access
                    db.update_drawer(conn, did, sort_index=new_sort_index)
                return self._send_json(200, {"updated": did})

            # Delete drawer (action-style)
            if path == "/api/drawers/delete":
                ok, did, err = self._parse_int(data, "id")
                if not ok:
                    return self._send_error(ValidationError(err))
                with db._connect() as conn:  # pylint: disable=protected-access
                    try:
                        db.soft_delete_drawer(conn, did)
                        return self._send_json(200, {"deleted": did})
                    except db.InventoryConstraintError as e:  # type: ignore[attr-defined]
                        return self._send_error(
                            ConflictError(str(e), details={"needed": "merge_move"})
                        )

            # Rename container (action-style)
            if path == "/api/containers/rename":
                ok, cid, err = self._parse_int(data, "id")
                if not ok:
                    return self._send_error(ValidationError(err))
                new_name = (data.get("new_name") or data.get("new_label") or "").strip()
                if not new_name:
                    return self._send_error(ValidationError("new_name is required"))
                try:
                    with db._connect() as conn:  # pylint: disable=protected-access
                        db.update_container(conn, cid, name=new_name)
                    return self._send_json(200, {"updated": cid})
                except db.DuplicateLabelError as e:  # type: ignore[attr-defined]
                    return self._send_error(
                        DuplicateError(str(e) or "Duplicate label in this drawer")
                    )

            # Move container (action-style)
            if path == "/api/containers/move":
                ok, cid, err = self._parse_int(data, "id")
                if not ok:
                    return self._send_error(ValidationError(err))
                # Accept any subset of these; only provided fields will be updated
                patch: dict[str, int] = {}
                ok, v, err = self._parse_optional_int(data, "new_drawer_id")
                if not ok:
                    return self._send_error(ValidationError(err))
                if v is not None:
                    patch["drawer_id"] = v
                for k in ("row_index", "col_index", "sort_index"):
                    ok, v, err = self._parse_optional_int(data, k)
                    if not ok:
                        return self._send_error(ValidationError(err))
                    if v is not None:
                        patch[k] = v
                if not patch:
                    return self._send_error(BadRequestError("no fields to update"))
                with db._connect() as conn:  # pylint: disable=protected-access
                    db.update_container(conn, cid, **patch)
                return self._send_json(200, {"updated": cid})

            # Delete container (action-style) – mirrors DELETE pre-check behavior
            if path == "/api/containers/delete":
                ok, cid, err = self._parse_int(data, "id")
                if not ok:
                    return self._send_error(ValidationError(err))
                with db._connect() as conn:  # pylint: disable=protected-access
                    # Pre-check: if inventory exists, request merge/move
                    row = conn.execute(
                        "SELECT COUNT(*) AS n FROM inventory WHERE container_id=?",
                        (cid,),
                    ).fetchone()
                    has_inv = bool(row and (row["n"] or 0) > 0)
                    if has_inv:
                        return self._send_error(
                            ConflictError(
                                "Container has inventory; merge/move required",
                                details={"needed": "merge_move"},
                            )
                        )
                    try:
                        db.soft_delete_container(conn, cid)
                        return self._send_json(200, {"deleted": cid})
                    except db.InventoryConstraintError as e:  # type: ignore[attr-defined]
                        return self._send_error(
                            ConflictError(str(e), details={"needed": "merge_move"})
                        )

            # Create drawer
            if path == "/api/drawers":
                name = (data.get("name") or "").strip()
                if not name:
                    return self._send_error(ValidationError("name is required"))
                description = (data.get("description") or "").strip() or None
                try:
                    svc = get_inventory_service()
                    did_or_row = svc.create_drawer(label=name, description=description)
                    did = None
                    if isinstance(did_or_row, dict):
                        did = (
                            did_or_row.get("id")
                            or did_or_row.get("drawer_id")
                            or did_or_row.get("value")
                        )
                    else:
                        # Support sqlite3.Row or mapping-like objects
                        try:
                            did = did_or_row["id"]  # type: ignore[index]
                        except Exception:
                            try:
                                did = did_or_row["drawer_id"]  # type: ignore[index]
                            except Exception:
                                # Fall back to bare value if it is an int
                                if isinstance(did_or_row, int):
                                    did = did_or_row
                    if did is None:
                        # As a last resort, try to coerce to dict for debugging/clients
                        try:
                            as_dict = dict(did_or_row)  # type: ignore[arg-type]
                        except Exception:
                            as_dict = {"value": str(did_or_row)}
                        return self._send_json(201, {"drawer": as_dict})
                    return self._send_json(201, {"id": int(did)})
                except AppError as e:
                    return self._send_error(e)
                except (
                    sqlite3.IntegrityError,
                    getattr(db, "DuplicateLabelError", sqlite3.IntegrityError),
                ) as _:
                    return self._send_error(
                        DuplicateError(
                            "Duplicate drawer name", details={"field": "name", "value": name}
                        )
                    )

            # Create drawer (action-style alias)
            if path == "/api/drawers/create":
                name = (data.get("name") or data.get("label") or "").strip()
                if not name:
                    return self._send_error(ValidationError("name is required"))
                description = (data.get("description") or "").strip() or None
                try:
                    svc = get_inventory_service()
                    did_or_row = svc.create_drawer(label=name, description=description)
                    did = None
                    if isinstance(did_or_row, dict):
                        did = (
                            did_or_row.get("id")
                            or did_or_row.get("drawer_id")
                            or did_or_row.get("value")
                        )
                    else:
                        try:
                            did = did_or_row["id"]  # type: ignore[index]
                        except Exception:
                            try:
                                did = did_or_row["drawer_id"]  # type: ignore[index]
                            except Exception:
                                if isinstance(did_or_row, int):
                                    did = did_or_row
                    if did is None:
                        try:
                            as_dict = dict(did_or_row)  # type: ignore[arg-type]
                        except Exception:
                            as_dict = {"value": str(did_or_row)}
                        return self._send_json(201, {"drawer": as_dict})
                    return self._send_json(201, {"id": int(did)})
                except AppError as e:
                    return self._send_error(e)
                except getattr(db, "DuplicateLabelError", sqlite3.IntegrityError):  # type: ignore[attr-defined]
                    return self._send_error(
                        DuplicateError(
                            "Duplicate drawer name", details={"field": "name", "value": name}
                        )
                    )

            # Create container
            if path == "/api/containers":
                if "drawer_id" not in data or "name" not in data:
                    return self._send_error(ValidationError("drawer_id and name are required"))
                ok, drawer_id_val, err = self._parse_int(data, "drawer_id")
                if not ok:
                    return self._send_error(ValidationError(err))
                try:
                    svc = get_inventory_service()
                    cid_or_row = svc.create_container(
                        label=str(data["name"]).strip(),
                        drawer_id=drawer_id_val,
                    )
                    cid = None
                    if isinstance(cid_or_row, dict):
                        cid = (
                            cid_or_row.get("id")
                            or cid_or_row.get("container_id")
                            or cid_or_row.get("value")
                        )
                    else:
                        try:
                            cid = cid_or_row["id"]  # type: ignore[index]
                        except Exception:
                            try:
                                cid = cid_or_row["container_id"]  # type: ignore[index]
                            except Exception:
                                if isinstance(cid_or_row, int):
                                    cid = cid_or_row
                    if cid is None:
                        try:
                            as_dict = dict(cid_or_row)  # type: ignore[arg-type]
                        except Exception:
                            as_dict = {"value": str(cid_or_row)}
                        return self._send_json(201, {"container": as_dict})
                    return self._send_json(201, {"id": int(cid)})
                except AppError as e:
                    return self._send_error(e)
                except db.DuplicateLabelError as e:  # type: ignore[attr-defined]
                    return self._send_error(
                        DuplicateError(str(e) or "Duplicate label in this drawer")
                    )

            # Create container (action-style alias)
            if path == "/api/containers/create":
                if "drawer_id" not in data or (
                    data.get("name") is None and data.get("label") is None
                ):
                    return self._send_error(ValidationError("drawer_id and name are required"))
                ok, drawer_id_val, err = self._parse_int(data, "drawer_id")
                if not ok:
                    return self._send_error(ValidationError(err))
                try:
                    svc = get_inventory_service()
                    cid_or_row = svc.create_container(
                        label=str(data.get("name") or data.get("label") or "").strip(),
                        drawer_id=drawer_id_val,
                    )
                    cid = None
                    if isinstance(cid_or_row, dict):
                        cid = (
                            cid_or_row.get("id")
                            or cid_or_row.get("container_id")
                            or cid_or_row.get("value")
                        )
                    else:
                        try:
                            cid = cid_or_row["id"]  # type: ignore[index]
                        except Exception:
                            try:
                                cid = cid_or_row["container_id"]  # type: ignore[index]
                            except Exception:
                                if isinstance(cid_or_row, int):
                                    cid = cid_or_row
                    if cid is None:
                        try:
                            as_dict = dict(cid_or_row)  # type: ignore[arg-type]
                        except Exception:
                            as_dict = {"value": str(cid_or_row)}
                        return self._send_json(201, {"container": as_dict})
                    return self._send_json(201, {"id": int(cid)})
                except AppError as e:
                    return self._send_error(e)
                except db.DuplicateLabelError as e:  # type: ignore[attr-defined]
                    return self._send_error(
                        DuplicateError(str(e) or "Duplicate label in this drawer")
                    )

            # Restore drawer
            m = re.match(r"^/api/drawers/(\d+)/restore$", path)
            if m:
                did = int(m.group(1))
                with db._connect() as conn:  # pylint: disable=protected-access
                    db.restore_drawer(conn, did)
                return self._send_json(200, {"restored": did})

            # Restore container
            m = re.match(r"^/api/containers/(\d+)/restore$", path)
            if m:
                cid = int(m.group(1))
                with db._connect() as conn:  # pylint: disable=protected-access
                    db.restore_container(conn, cid)
                return self._send_json(200, {"restored": cid})

            # Merge/move container inventory and soft-delete source
            m = re.match(r"^/api/containers/(\d+)/merge_move$", path)
            if m:
                source_id = int(m.group(1))
                target_id = int(data.get("target_container_id", 0))
                if not target_id:
                    return self._send_error(ValidationError("target_container_id is required"))
                with db._connect() as conn:  # pylint: disable=protected-access
                    # Move rows
                    cur = conn.execute(
                        "UPDATE inventory SET container_id=? WHERE container_id=?",
                        (target_id, source_id),
                    )
                    moved = cur.rowcount or 0
                    # Soft delete source & audit
                    before = conn.execute(
                        "SELECT * FROM containers WHERE id=?", (source_id,)
                    ).fetchone()
                    conn.execute(
                        "UPDATE containers SET deleted_at=CURRENT_TIMESTAMP WHERE id=?",
                        (source_id,),
                    )
                    after = conn.execute(
                        "SELECT * FROM containers WHERE id=?", (source_id,)
                    ).fetchone()
                    if hasattr(db, "_audit"):
                        try:
                            db._audit(conn, "container", source_id, "merge_move", dict(before) if before else None, dict(after) if after else None)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    conn.commit()
                return self._send_json(200, {"moved": moved, "source_deleted": True})

            return self._send_error(NotFoundError("Not Found"))
        except Exception as e:  # pylint: disable=broad-except
            traceback.print_exc()
            return self._handle_unexpected(e)

    def do_PUT(self):  # noqa: N802
        if not self.path.startswith("/api/"):
            return self._not_found()
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        try:
            # Update drawer
            m = re.match(r"^/api/drawers/(\d+)$", path)
            if m:
                did = int(m.group(1))
                try:
                    with db._connect() as conn:  # pylint: disable=protected-access
                        db.update_drawer(conn, did, **data)
                    return self._send_json(200, {"updated": did})
                except sqlite3.IntegrityError:
                    return self._send_error(DuplicateError("Duplicate drawer name"))

            # Update container
            m = re.match(r"^/api/containers/(\d+)$", path)
            if m:
                cid = int(m.group(1))
                with db._connect() as conn:  # pylint: disable=protected-access
                    try:
                        db.update_container(conn, cid, **data)
                        return self._send_json(200, {"updated": cid})
                    except db.DuplicateLabelError as e:  # type: ignore[attr-defined]
                        return self._send_error(
                            DuplicateError(str(e) or "Duplicate label in this drawer")
                        )

            return self._send_error(NotFoundError("Not Found"))
        except Exception as e:
            return self._handle_unexpected(e)

    def do_DELETE(self):  # noqa: N802
        if not self.path.startswith("/api/"):
            return self._not_found()
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        check_only = qs.get("check", ["0"])[0] == "1"
        try:
            # Delete drawer (soft)
            m = re.match(r"^/api/drawers/(\d+)$", path)
            if m:
                did = int(m.group(1))
                with db._connect() as conn:  # pylint: disable=protected-access
                    try:
                        db.soft_delete_drawer(conn, did)
                        return self._send_json(200, {"deleted": did})
                    except db.InventoryConstraintError as e:  # type: ignore[attr-defined]
                        return self._send_error(
                            ConflictError(str(e), details={"needed": "merge_move"})
                        )

            # Delete container (soft)
            m = re.match(r"^/api/containers/(\d+)$", path)
            if m:
                cid = int(m.group(1))
                # If this is a pre-check request, do not mutate; just report whether merge/move is required
                if check_only:
                    with db._connect() as conn:  # pylint: disable=protected-access
                        row = conn.execute(
                            "SELECT COUNT(*) AS n FROM inventory WHERE container_id=?", (cid,)
                        ).fetchone()
                        has_inv = bool(row and (row["n"] or 0) > 0)
                    if has_inv:
                        return self._send_error(
                            ConflictError(
                                "Container has inventory; merge/move required",
                                details={"needed": "merge_move"},
                            )
                        )
                    # No inventory: tell the client it is safe to proceed
                    return self._send_json(204, {})

                with db._connect() as conn:  # pylint: disable=protected-access
                    # Explicit pre-check: if any inventory rows reference this container, require merge/move
                    try:
                        row = conn.execute(
                            "SELECT COUNT(*) AS n FROM inventory WHERE container_id=?", (cid,)
                        ).fetchone()
                        has_inv = bool(row and (row["n"] or 0) > 0)
                    except Exception:
                        has_inv = False
                    if has_inv:
                        # Signal that a merge/move is required (frontend opens merge/move modal on this)
                        return self._send_error(
                            ConflictError(
                                "Container has inventory; merge/move required",
                                details={"needed": "merge_move"},
                            )
                        )

                    # Otherwise proceed with soft delete
                    try:
                        db.soft_delete_container(conn, cid)
                        return self._send_json(200, {"deleted": cid})
                    except db.InventoryConstraintError as e:  # type: ignore[attr-defined]
                        # Fallback: if helper enforces the rule, surface the same signal
                        return self._send_error(
                            ConflictError(str(e), details={"needed": "merge_move"})
                        )

            return self._send_error(NotFoundError("Not Found"))
        except Exception as e:
            return self._handle_unexpected(e)

    def _serve_all_sets(self):
        # List all sets using template rendering (no inline HTML)
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT
                    s.set_num,
                    s.name,
                    s.year,
                    s.image_url,
                    s.rebrickable_url,
                    s.status,
                    s.added_at,
                    (
                      SELECT COALESCE(SUM(sp.quantity), 0)
                      FROM set_parts sp
                      WHERE sp.set_num = s.set_num
                    ) AS total_parts
                FROM sets s
                ORDER BY s.added_at DESC
                """
            ).fetchall()

        # Build rows for the shared table macro used by sets.html
        rows_for_table = []
        for r in rows:
            set_num = r["set_num"]
            name = r["name"] or ""
            year = int(r["year"] or 0)
            status = _display_status(r["status"]) if r["status"] else ""
            total_parts = int(r["total_parts"] or 0)
            img = r["image_url"] or "https://rebrickable.com/static/img/nil.png"
            rb_url = r["rebrickable_url"] or rebrickable_set_url(set_num)

            cell_set = f"<a href='{html.escape(set_url(set_num))}'>{html.escape(set_num)}</a>"
            cell_name = html.escape(name)
            cell_year = str(year) if year else ""
            cell_total = f"{total_parts:,}"
            cell_status = html.escape(status)
            cell_link = f"<a href='{html.escape(rb_url)}' target='_blank'>View</a>"
            cell_img = f"<img src='{html.escape(img)}' alt='Set image' style='height: 48px;'>"

            rows_for_table.append(
                [cell_set, cell_name, cell_year, cell_total, cell_status, cell_link, cell_img]
            )

        # Header context for base.html
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            header_total_parts = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not header_total_parts:
                header_total_parts = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            header_total_parts = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "sets.html",
            title="EB's Bricks - Sets",
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="sets",
            site_title=site_title,
            total_parts=header_total_parts,
        )
        return self._send_html(html_doc, status=200)

    def _serve_set(self, set_num: str):
        # Get set metadata and parts using new service
        svc = get_set_parts_service()
        set_info = svc.get_set(set_number=set_num)
        if not set_info:
            self._not_found()
            return

        parts = list(svc.list_parts(set_number=set_num))

        # Compute total quantity for the set
        total_qty = sum(int(p.get("quantity", 0) or 0) for p in parts)
        total_qty_str = f"{total_qty:,}"

        # Helper for foreground color
        def _fg_for_hex(h: str) -> str:
            try:
                h = (h or "").lstrip("#")
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
                return "#000" if (r + g + b) > 382 else "#fff"
            except Exception:
                return "#000"

        # Build rows for template table: [Part ID, Part Name, Color(td_style), Qty, Link, Image]
        rows_for_table = []
        for part in parts:
            design_id = html.escape(str(part.get("design_id", "")))
            name = html.escape(str(part.get("name", "")))
            color_name = str(part.get("color_name", ""))
            hex_code = (part.get("hex") or "").lstrip("#")
            qty = int(part.get("quantity", 0) or 0)

            # Part ID links to part detail
            cell_id = f"<a href='{html.escape(part_url(design_id))}'>{design_id}</a>"
            cell_name = name

            # Color cell as full-cell background via td_style
            if hex_code:
                fg = _fg_for_hex(hex_code)
                cell_color = {
                    "html": html.escape(color_name),
                    "td_style": f"background:#{html.escape(hex_code)}; color:{fg}",
                }
            else:
                cell_color = html.escape(color_name)

            cell_qty = f"{qty:,}"

            link = part.get("part_url") or rebrickable_part_url(design_id)
            img = part.get("part_img_url") or "https://rebrickable.com/static/img/nil.png"
            cell_link = f"<a href='{html.escape(link)}' target='_blank'>View</a>"
            cell_img = f"<img src='{html.escape(img)}' alt='Part image' style='height: 32px;'>"

            rows_for_table.append([cell_id, cell_name, cell_color, cell_qty, cell_link, cell_img])

        # Header context
        set_img_url = set_info.get("image_url") or set_info.get("set_img_url") or ""
        set_name = set_info.get("name", set_num)
        rb_set_url = (
            set_info.get("rebrickable_url")
            or set_info.get("set_url")
            or rebrickable_set_url(set_num)
        )

        # Overall site totals for the header
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            overall_total = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not overall_total:
                overall_total = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            overall_total = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "set_detail.html",
            title=f"EB's Bricks - Set {set_num}",
            set_num=set_num,
            set_name=set_name,
            set_url=rb_set_url,
            set_img_url=set_img_url,
            total_qty=total_qty,
            total_qty_str=total_qty_str,
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="set_parts",
            site_title=site_title,
            total_parts=overall_total,
        )
        return self._send_html(html_doc, status=200)

    def _send_html(self, html_doc: str, status: int = 200):
        html_bytes = html_doc.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def _not_found(self):
        """Send a simple 404 response."""
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        try:
            self.wfile.write(b"Not Found")
        except Exception:
            # If client closed connection early, just ignore
            pass

    def _serve_location_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT
                    COALESCE(d.name, i.drawer)     AS drawer,
                    COALESCE(c2.name, i.container) AS container,
                    c2.id                          AS container_id,
                    SUM(i.quantity)                AS total_qty
                FROM inventory i
                LEFT JOIN containers c2 ON c2.id = i.container_id
                LEFT JOIN drawers    d  ON d.id  = c2.drawer_id
                WHERE i.status NOT IN ('built', 'wip', 'in_box', 'teardown')
                GROUP BY COALESCE(d.name, i.drawer), COALESCE(c2.name, i.container)
                """
            ).fetchall()

        # Build normalized locations and totals
        locations = []
        for r in rows:
            drawer = r["drawer"] or ""
            container = r["container"] or ""
            container_id = r["container_id"]
            if drawer and container:
                loc_label = f"{drawer} / {container}"
            elif drawer:
                loc_label = drawer
            elif container:
                loc_label = container
            else:
                loc_label = "(unknown)"

            # Link to container detail when we have a real container id
            if container_id:
                loc_html = f"<a href='{html.escape(container_url(int(container_id)))}'>{html.escape(loc_label)}</a>"
            else:
                loc_html = html.escape(loc_label)

            locations.append(
                {
                    "label": loc_label,
                    "html": loc_html,
                    "total_qty": int(r["total_qty"] or 0),
                }
            )

        # Sort desc by total and convert to rows for the table macro
        locations.sort(key=lambda x: x["total_qty"], reverse=True)
        rows_for_table = [[x["html"], f"{x['total_qty']:,}"] for x in locations]

        # Compute header totals/context similar to _serve_drawers
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            total_parts = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not total_parts:
                total_parts = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            total_parts = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "location_counts.html",
            title="EB's Bricks - Storage Location Counts",
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="location_counts",
            site_title=site_title,
            total_parts=total_parts,
        )
        return self._send_html(html_doc, status=200)

    # ..................................................................... pages
    def _serve_master(self):
        # Build master rows using the shared query
        rows = _query_master_rows()

        # Convert to rows for the shared table macro used by loose_parts.html
        rows_for_table = []

        def _fg_for_hex(h):
            try:
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
                return "#000" if (r + g + b) > 382 else "#fff"
            except Exception:
                return "#000"

        total_qty = 0
        for r in rows:
            design_id = str(r.get("design_id", ""))
            part_name = r.get("part_name", "")
            color_name = r.get("color_name", "")
            hex_code = (r.get("hex") or "").lstrip("#")
            drawer = r.get("drawer") or ""
            container = r.get("container") or ""
            drawer_id = r.get("drawer_id")
            container_id = r.get("container_id")
            qty = int(r.get("qty", 0) or 0)
            total_qty += qty

            # Cells
            cell_id = f"<a href='{html.escape(part_url(design_id))}'>{html.escape(design_id)}</a>"
            cell_name = html.escape(part_name)

            # Color cell as full-cell background via td_style (consumed by table macro + tables.js)
            if hex_code:
                fg = _fg_for_hex(hex_code)
                cell_color = {
                    "html": html.escape(color_name),
                    "td_style": f"background:#{html.escape(hex_code)}; color:{fg}",
                }
            else:
                cell_color = html.escape(color_name)

            if drawer and drawer_id:
                cell_drawer = (
                    f"<a href='{html.escape(drawer_url(int(drawer_id)))}'>{html.escape(drawer)}</a>"
                )
            else:
                cell_drawer = html.escape(drawer)

            if container and container_id:
                cell_container = f"<a href='{html.escape(container_url(int(container_id)))}'>{html.escape(container)}</a>"
            else:
                cell_container = html.escape(container)

            cell_qty = f"{qty:,}"

            link = r.get("part_url") or rebrickable_part_url(design_id)
            img = r.get("part_img_url") or "https://rebrickable.com/static/img/nil.png"
            cell_link = f"<a href='{html.escape(link)}' target='_blank'>View</a>"
            cell_img = f"<img src='{html.escape(img)}' alt='Part image' style='height: 32px;'>"

            rows_for_table.append(
                [
                    cell_id,
                    cell_name,
                    cell_color,
                    cell_drawer,
                    cell_container,
                    cell_qty,
                    cell_link,
                    cell_img,
                ]
            )

        # Header context for base.html
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            total_parts = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not total_parts:
                total_parts = sum(x.get("qty", 0) for x in rows)
        except Exception:
            total_parts = sum(x.get("qty", 0) for x in rows)

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "loose_parts.html",
            title="EB's Bricks - Loose Parts",
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="inventory_master",
            site_title=site_title,
            total_parts=total_parts,
        )
        return self._send_html(html_doc, status=200)

    def _serve_part(self, design_id: str):
        # Resolve part meta via service (fallbacks preserved)
        part = get_parts_service().get_part(design_id=design_id) or {
            "design_id": design_id,
            "name": "Unknown part",
            "part_url": None,
            "part_img_url": None,
        }

        # "In Sets" rows via service (with per-color detail)
        sets_rows = get_set_parts_service().sets_for_part_with_colors(design_id=design_id)

        # Loose inventory rows aggregated by drawer/container/color via service
        loose_rows = get_inventory_service().loose_inventory_for_part(design_id)

        # Foreground color helper
        def _fg_for_hex(h: str) -> str:
            try:
                h = (h or "").lstrip("#")
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
                return "#000" if (r + g + b) > 382 else "#fff"
            except Exception:
                return "#000"

        # Cache for resolving IDs by names (drawer_name, container_name) -> (drawer_id, container_id)
        _name_to_ids_cache: dict[tuple[str, str], tuple[int | None, int | None]] = {}

        def _resolve_ids(drawer_name: str, container_name: str) -> tuple[int | None, int | None]:
            key = (drawer_name or "", container_name or "")
            if key in _name_to_ids_cache:
                return _name_to_ids_cache[key]
            try:
                with db._connect() as conn:  # pylint: disable=protected-access
                    # Resolve drawer by name
                    drow = conn.execute(
                        "SELECT id FROM drawers WHERE name = ? LIMIT 1", (drawer_name,)
                    ).fetchone()
                    did = int(drow["id"]) if drow and drow["id"] is not None else None
                    cid = None
                    if did is not None and container_name:
                        crow = conn.execute(
                            "SELECT id FROM containers WHERE name = ? AND drawer_id = ? LIMIT 1",
                            (container_name, did),
                        ).fetchone()
                        cid = int(crow["id"]) if crow and crow["id"] is not None else None
            except Exception:
                did, cid = None, None
            _name_to_ids_cache[key] = (did, cid)
            return did, cid

        # Build rows for the two tables used by part_detail.html
        # Loose Parts: Drawer, Container, Color(td_style), Qty
        rows_loose_tbl: list[list] = []
        for r in loose_rows:
            drawer_txt = str(r.get("drawer", ""))
            container_txt = str(r.get("container", ""))
            drawer_id = r.get("drawer_id")
            container_id = r.get("container_id")
            # Fallback: resolve IDs by name if missing and names are present
            if (drawer_id is None or container_id is None) and (drawer_txt or container_txt):
                rid, cid = _resolve_ids(drawer_txt, container_txt)
                drawer_id = drawer_id or rid
                container_id = container_id or cid
            color_name = str(r.get("color_name", ""))
            hex_code = (r.get("hex") or "").lstrip("#")
            qty = int(r.get("quantity", 0) or 0)

            # Linkify drawer/container when we have real IDs (dict with html so template renders safely)
            if drawer_id:
                drawer_cell = {
                    "html": f"<a href='/drawers/{int(drawer_id)}'>{html.escape(drawer_txt)}</a>"
                }
            else:
                drawer_cell = html.escape(drawer_txt)

            if container_id:
                container_cell = {
                    "html": f"<a href='/containers/{int(container_id)}'>{html.escape(container_txt)}</a>"
                }
            else:
                container_cell = html.escape(container_txt)

            if hex_code:
                fg = _fg_for_hex(hex_code)
                color_cell = {
                    "html": html.escape(color_name),
                    "td_style": f"background:#{html.escape(hex_code)}; color:{fg}",
                }
            else:
                color_cell = html.escape(color_name)

            rows_loose_tbl.append([drawer_cell, container_cell, color_cell, f"{qty:,}"])

        # In Sets: Set (link + name), Color(td_style), Qty
        rows_sets_tbl: list[list] = []
        for r in sets_rows:
            set_num = str(r.get("set_num", ""))
            set_name = str(r.get("set_name", ""))
            color_name = str(r.get("color_name", ""))
            hex_code = (r.get("hex") or "").lstrip("#")
            qty = int(r.get("quantity", 0) or 0)

            set_id_cell = f"<a href='{html.escape(set_url(set_num))}'>{html.escape(set_num)}</a>"
            set_name_cell = html.escape(set_name)
            if hex_code:
                fg = _fg_for_hex(hex_code)
                color_cell = {
                    "html": html.escape(color_name),
                    "td_style": f"background:#{html.escape(hex_code)}; color:{fg}",
                }
            else:
                color_cell = html.escape(color_name)

            rows_sets_tbl.append([set_id_cell, set_name_cell, color_cell, f"{qty:,}"])

        # Per-part total quantity (raw sums, not formatted strings)
        part_total = sum(int(r.get("quantity", 0) or 0) for r in loose_rows) + sum(
            int(r.get("quantity", 0) or 0) for r in sets_rows
        )

        # Overall site totals for the header
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            overall_total = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not overall_total:
                overall_total = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            overall_total = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        # Part meta for header
        rb_part_url = part.get("part_url") or rebrickable_part_url(design_id)
        part_img_url = part.get("part_img_url") or "https://rebrickable.com/static/img/nil.png"
        part_name = part.get("name", "")

        html_doc = _render_template(
            "part_detail.html",
            title=f"EB's Bricks - Part {design_id}",
            design_id=design_id,
            part_id=design_id,
            part_name=part_name,
            part_url=rb_part_url,
            part_img_url=part_img_url,
            total_qty=part_total,
            total_qty_str=f"{part_total:,}",
            rows_loose=rows_loose_tbl,
            rows_sets=rows_sets_tbl,
            # Export keys & per-table context
            loose_table_key="part_in_loose",
            sets_table_key="part_in_sets",
            loose_table_ctx={"design_id": design_id},
            sets_table_ctx={"design_id": design_id},
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            site_title=site_title,
            total_parts=overall_total,
        )
        return self._send_html(html_doc, status=200)

    def _serve_drawers(self):
        svc = get_inventory_service()
        rows = list(svc.list_drawers())
        total_containers = sum(r.get("container_count", 0) for r in rows)
        total_pieces = sum(r.get("part_count", 0) for r in rows)

        drawers = []
        for r in rows:
            drawers.append(
                {
                    "id": r["id"],
                    "name": r.get("name", "") or "",
                    "description": r.get("description") or "",
                    "container_count": r.get("container_count", 0) or 0,
                    "part_count": r.get("part_count", 0) or 0,
                    "cols": r.get("cols"),
                    "rows": r.get("rows"),
                }
            )

        # Build rows for the shared table macro: [Drawer(link), Containers, Actions]
        rows_for_table = []
        for d in drawers:
            drawer_link = (
                f"<a href='{html.escape(drawer_url(int(d['id'])))}'>{html.escape(d['name'])}</a>"
            )
            actions = (
                f"<button type='button' data-action=\"rename-drawer\" "
                f"data-drawer-id=\"{d['id']}\" data-name=\"{html.escape(d['name'])}\" "
                f"data-description=\"{html.escape(d.get('description') or '')}\" "
                f"data-cols=\"{html.escape(str(d.get('cols') or ''))}\" "
                f"data-rows=\"{html.escape(str(d.get('rows') or ''))}\">Rename</button> "
                f"<button type='button' data-action=\"delete-drawer\" data-id=\"{d['id']}\">Delete</button>"
            )
            rows_for_table.append([drawer_link, d["container_count"], actions])

        # Header context for base.html
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            total_parts = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not total_parts:
                # Fallback: sum from master query
                total_parts = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            total_parts = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "drawers.html",
            title="EB's Bricks - Drawers",
            drawers=drawers,
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="drawers",
            totals={"containers": total_containers, "pieces": total_pieces},
            site_title=site_title,
            total_parts=total_parts,
        )
        return self._send_html(html_doc, status=200)

    def _serve_drawer_detail(self, drawer_id: int):
        d = db.get_drawer(drawer_id)
        if not d:
            self._not_found()
            return

        # Gather parts across all containers in this drawer
        svc = get_inventory_service()
        containers = list(svc.list_containers(filters={"drawer_id": drawer_id}))

        rows_for_table: list[list] = []

        for c in containers:
            c_id = int(c["id"])
            c_name = str(c.get("name") or "")
            desc = str(c.get("description") or "")
            row_index = c.get("row_index")
            col_index = c.get("col_index")

            # Position label (rX cY) when we have both
            pos = ""
            if row_index is not None and col_index is not None:
                pos = f"r{int(row_index)} c{int(col_index)}"

            # Prefer precomputed counts if present; otherwise derive from parts
            unique_parts = c.get("unique_parts")
            total_pieces = c.get("part_count")
            if unique_parts is None or total_pieces is None:
                parts = db.list_parts_in_container(c_id)
                unique_parts = len(parts)
                total_pieces = sum(int(p.get("qty") or p.get("quantity") or 0) for p in parts)

            name_link = f"<a href='{html.escape(container_url(c_id))}'>{html.escape(c_name)}</a>"
            total_pieces_str = f"{int(total_pieces or 0):,}"

            actions_html = (
                f'<button type=\'button\' data-action="rename-container" data-container-id="{c_id}" '
                f'data-name="{html.escape(c_name)}" data-description="{html.escape(desc)}" '
                f"data-row-index=\"{html.escape(str(row_index or ''))}\" data-col-index=\"{html.escape(str(col_index or ''))}\">Rename</button> "
                f'<button type=\'button\' data-action="move-container" data-id="{c_id}" data-drawer-id="{drawer_id}">Move</button> '
                f'<button type=\'button\' data-action="delete-container" data-id="{c_id}" data-drawer-id="{drawer_id}">Delete</button>'
            )

            rows_for_table.append(
                [
                    pos,
                    name_link,
                    html.escape(desc),
                    int(unique_parts or 0),
                    total_pieces_str,
                    actions_html,
                ]
            )

        # Header totals
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            overall_total = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not overall_total:
                overall_total = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            overall_total = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "drawer_detail.html",
            title=f"EB's Bricks - Drawer {d['name']}",
            drawer_name=d["name"],
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="containers_in_drawer",
            site_title=site_title,
            total_parts=overall_total,
            drawer_id=drawer_id,
        )
        return self._send_html(html_doc, status=200)

    def _serve_container_detail(self, container_id: int):
        c = db.get_container(container_id)
        if not c:
            self._not_found()
            return

        # Parts in this container
        parts = db.list_parts_in_container(container_id)

        # Foreground color helper
        def _fg_for_hex(h: str) -> str:
            try:
                h = (h or "").lstrip("#")
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
                return "#000" if (r + g + b) > 382 else "#fff"
            except Exception:
                return "#000"

        # Rows for container_detail.html table: [Design ID, Part, Color(td_style), Qty, Link, Image]
        rows_for_table: list[list] = []
        for p in parts:
            raw_design_id = str(p.get("design_id", ""))  # use raw for lookups
            design_id = html.escape(raw_design_id)  # escaped for HTML
            part_name = html.escape(str(p.get("part_name", "")))
            color_name = str(p.get("color_name", ""))
            hex_code = (p.get("hex") or "").lstrip("#")
            qty = int(p.get("qty", 0) or 0)

            cell_id = f"<a href='{html.escape(part_url(design_id))}'>{design_id}</a>"
            cell_name = part_name

            if hex_code:
                fg = _fg_for_hex(hex_code)
                cell_color = {
                    "html": html.escape(color_name),
                    "td_style": f"background:#{html.escape(hex_code)}; color:{fg}",
                }
            else:
                cell_color = html.escape(color_name)

            cell_qty = f"{qty:,}"

            # Prefer explicit URLs on the row; fall back to a Rebrickable guess
            link = (
                p.get("rebrickable_url")
                or p.get("part_url")
                or (rebrickable_part_url(raw_design_id) if raw_design_id else "")
            )

            # Image: try row fields, then look up part meta as a fallback
            part_meta = db.get_part(raw_design_id) or {}
            img = (
                p.get("image_url")
                or p.get("img_url")
                or p.get("part_img_url")
                or part_meta.get("part_img_url")
                or part_meta.get("image_url")
                or "https://rebrickable.com/static/img/nil.png"
            )

            cell_link = f"<a href='{html.escape(link)}' target='_blank'>View</a>"
            cell_img = f"<img src='{html.escape(img)}' alt='Part image' style='height: 32px;'>"

            rows_for_table.append([cell_id, cell_name, cell_color, cell_qty, cell_link, cell_img])

        # Header context like other templated pages
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            total_parts = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not total_parts:
                total_parts = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            total_parts = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "container_detail.html",
            title=f"EB's Bricks - Container {c['name']}",
            container_id=container_id,
            container_name=c.get("name") or "",
            container_desc=c.get("description") or "",
            drawer_id=c.get("drawer_id"),
            drawer_name=c.get("drawer_name") or "",
            row_index=c.get("row_index"),
            col_index=c.get("col_index"),
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="container_parts",
            site_title=site_title,
            total_parts=total_parts,
        )
        return self._send_html(html_doc, status=200)

    # The /sets route and _serve_sets method have been removed.

    def _serve_part_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
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

                    -- Parts in sets (exclude sets marked as loose)
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

        # Build rows for the shared table macro used by part_counts.html
        rows_for_table = []
        for r in rows:
            design_id = str(r["design_id"]) if r["design_id"] is not None else ""
            name = r["part_name"] or ""
            qty = int(r["total_qty"] or 0)
            link = r["part_url"] or rebrickable_part_url(design_id)
            img = r["part_img_url"] or "https://rebrickable.com/static/img/nil.png"

            cell_id = f"<a href='{html.escape(part_url(design_id))}'>{html.escape(design_id)}</a>"
            cell_name = html.escape(name)
            cell_qty = f"{qty:,}"  # display formatted; DT will still sort correctly via num/num-fmt
            cell_link = f"<a href='{html.escape(link)}' target='_blank'>View</a>"
            cell_img = f"<img src='{html.escape(img)}' alt='Part image' style='height: 32px;'>"
            rows_for_table.append([cell_id, cell_name, cell_qty, cell_link, cell_img])

        # Header context for base.html
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            total_parts = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not total_parts:
                total_parts = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            total_parts = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "part_counts.html",
            title="EB's Bricks - Part Counts",
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="part_counts",
            site_title=site_title,
            total_parts=total_parts,
        )
        return self._send_html(html_doc, status=200)

    def _serve_part_color_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
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
                    -- loose inventory by part+color
                    SELECT i.design_id, i.color_id, SUM(i.quantity) AS total_qty
                    FROM inventory i
                    WHERE i.status = 'loose'
                    GROUP BY i.design_id, i.color_id

                    UNION ALL

                    -- parts in sets (exclude sets marked loose)
                    SELECT sp.design_id, sp.color_id, SUM(sp.quantity) AS total_qty
                    FROM set_parts sp
                    JOIN parts p ON sp.design_id = p.design_id
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

        # Build rows for the shared table macro
        rows_for_table = []
        for r in rows:
            design_id = str(r["design_id"]) if r["design_id"] is not None else ""
            name = r["part_name"] or ""
            color_id = r["color_id"]
            color_name = r["color_name"] or "(unknown)"
            color_hex = (r["color_hex"] or "").lstrip("#")  # e.g. F2F2F2
            qty = int(r["total_qty"] or 0)

            # Rebrickable URLs
            rb_color_url = rebrickable_part_color_url(design_id, color_id)
            img_url = r["part_img_url"] or "https://rebrickable.com/static/img/nil.png"

            # Cells
            cell_id = f"<a href='{html.escape(part_url(design_id))}'>{html.escape(design_id)}</a>"
            cell_name = html.escape(name)

            # Color cell: full-cell background via td_style (consumed by table macro + tables.js)
            def _fg_for_hex(h):
                try:
                    r = int(h[0:2], 16)
                    g = int(h[2:4], 16)
                    b = int(h[4:6], 16)
                    return "#000" if (r + g + b) > 382 else "#fff"
                except Exception:
                    return "#000"

            if color_hex:
                fg = _fg_for_hex(color_hex)
                cell_color = {
                    "html": html.escape(color_name),
                    "td_style": f"background:#{html.escape(color_hex)}; color:{fg}",
                }
            else:
                cell_color = html.escape(color_name)

            cell_qty = f"{qty:,}"
            cell_link = f"<a href='{html.escape(rb_color_url)}' target='_blank'>View</a>"
            cell_img = f"<img src='{html.escape(img_url)}' alt='Part image' style='height: 32px;'>"

            rows_for_table.append([cell_id, cell_name, cell_color, cell_qty, cell_link, cell_img])

        # Header context for base.html
        try:
            _totals = getattr(db, "totals", lambda: {})() or {}
            total_parts = (
                _totals.get("overall_total")
                or _totals.get("total_parts")
                or _totals.get("loose_total")
            )
            if not total_parts:
                total_parts = sum(r.get("qty", 0) for r in _query_master_rows())
        except Exception:
            total_parts = sum(r.get("qty", 0) for r in _query_master_rows())

        site_title = os.getenv("SITE_TITLE") or "Ervin-Burdick's Bricks"

        html_doc = _render_template(
            "part_color_counts.html",
            title="EB's Bricks - Part + Color Counts",
            rows=rows_for_table,
            breadcrumbs=[{"href": _url_for("index"), "label": "Back to Home"}],
            export_key="part_color_counts",
            site_title=site_title,
            total_parts=total_parts,
        )
        return self._send_html(html_doc, status=200)

    # ------------------------------ export + utilities (inside Handler)
    def _parse_query(self):
        parsed = urlparse(self.path)
        return parse_qs(parsed.query)

    def _serve_export(self):
        try:
            qs = self._parse_query()
            table_key = (qs.get("table") or [""])[0]
            dt_json = (qs.get("dt") or ["{}"])[0]
            ctx_json = (qs.get("ctx") or ["{}"])[0]
            dt_state = json.loads(dt_json)
            ctx = json.loads(ctx_json)
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Bad request: {e}".encode())
            return

        try:
            rows, columns = self._get_rows_for_table(table_key, ctx)
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Unknown table or data error: {e}".encode())
            return

        rows = self._filter_and_order_rows(rows, columns, dt_state)

        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{table_key}_export_{stamp}.csv"
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()

        # UTF-8 BOM for Excel
        self.wfile.write("\ufeff".encode())

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(columns)
        self.wfile.write(out.getvalue().encode("utf-8"))
        out.seek(0)
        out.truncate(0)

        for r in rows:
            writer.writerow([r.get(col, "") for col in columns])
            self.wfile.write(out.getvalue().encode("utf-8"))
            out.seek(0)
            out.truncate(0)

    def _filter_and_order_rows(self, rows, columns, dt_state):
        def cell_str(row, col):
            v = row.get(col, "")
            return "" if v is None else str(v)

        # Global search
        search_val = ((dt_state or {}).get("search") or {}).get("value", "")
        if search_val:
            sval = search_val.lower()
            rows = [r for r in rows if any(sval in cell_str(r, c).lower() for c in columns)]

        # Per-column search
        cols_state = (dt_state or {}).get("columns") or []
        for i, col_state in enumerate(cols_state):
            if i >= len(columns):
                break
            val = ((col_state or {}).get("search") or {}).get("value", "")
            if val:
                sval = str(val).lower()
                colname = columns[i]
                rows = [r for r in rows if sval in cell_str(r, colname).lower()]

        # Ordering (stable: apply last spec first)
        order_specs = (dt_state or {}).get("order") or []
        for spec in reversed(order_specs):
            try:
                idx = int(spec.get("column", 0))
            except Exception:
                idx = 0
            if not (0 <= idx < len(columns)):
                continue
            colname = columns[idx]
            reverse = str(spec.get("dir", "asc")).lower() == "desc"
            rows.sort(key=lambda r: cell_str(r, colname), reverse=reverse)

        return rows

    def _get_rows_for_table(self, table_key: str, ctx: dict):
        """
        Return (rows, columns) for the provided export key.

        rows: list[dict[str, Any]] with plain-text (non-HTML) values
        columns: list[str] header order to preserve in the CSV
        """
        # ----- Sets index -----
        if table_key == "sets":
            with db._connect() as conn:  # pylint: disable=protected-access
                rs = conn.execute(
                    """
                    SELECT
                        s.set_num,
                        s.name,
                        s.year,
                        s.status,
                        s.rebrickable_url,
                        s.image_url,
                        (
                          SELECT COALESCE(SUM(sp.quantity), 0)
                          FROM set_parts sp
                          WHERE sp.set_num = s.set_num
                        ) AS total_parts
                    FROM sets s
                    ORDER BY s.added_at DESC
                    """
                ).fetchall()

            rows = [
                {
                    "Set Number": r["set_num"],
                    "Name": r["name"],
                    "Year": int(r["year"] or 0),
                    "Total Parts": int(r["total_parts"] or 0),
                    "Status": _display_status(r["status"]) if r["status"] else "",
                    "Rebrickable Link": r["rebrickable_url"],
                    "Image": r["image_url"],
                }
                for r in rs
            ]
            columns = [
                "Set Number",
                "Name",
                "Year",
                "Total Parts",
                "Status",
                "Rebrickable Link",
                "Image",
            ]
            return rows, columns

        # ----- Drawers index -----
        if table_key == "drawers":
            rows = []
            for r in db.list_drawers():
                rows.append(
                    {
                        "Name": r.get("name", "") or "",
                        "Description": r.get("description") or "",
                        "Containers": int(r.get("container_count", 0) or 0),
                        "Total Pieces": int(r.get("part_count", 0) or 0),
                        "Rows": r.get("rows"),
                        "Cols": r.get("cols"),
                    }
                )
            columns = ["Name", "Description", "Containers", "Total Pieces", "Rows", "Cols"]
            return rows, columns

        # ----- Containers within a drawer (drawer detail page) -----
        if table_key == "containers_in_drawer":
            drawer_id = int(ctx.get("drawer_id", 0) or ctx.get("id", 0))
            if not drawer_id:
                raise ValueError("drawer_id required")

            svc = get_inventory_service()
            containers = list(svc.list_containers(filters={"drawer_id": drawer_id}))

            rows = []
            for c in containers:
                row_index = c.get("row_index")
                col_index = c.get("col_index")
                pos = ""
                if row_index is not None and col_index is not None:
                    pos = f"r{int(row_index)} c{int(col_index)}"

                unique_parts = c.get("unique_parts")
                total_pieces = c.get("part_count")
                if unique_parts is None or total_pieces is None:
                    parts = db.list_parts_in_container(int(c["id"]))
                    unique_parts = len(parts)
                    total_pieces = sum(int(p.get("qty") or p.get("quantity") or 0) for p in parts)

                rows.append(
                    {
                        "Position": pos,
                        "Container": c.get("name") or "",
                        "Description": c.get("description") or "",
                        "Unique Parts": int(unique_parts or 0),
                        "Total Pieces": int(total_pieces or 0),
                    }
                )
            columns = ["Position", "Container", "Description", "Unique Parts", "Total Pieces"]
            return rows, columns

        # ----- Parts inside a specific container (container detail page) -----
        if table_key == "container_parts":
            container_id = int(ctx.get("container_id", 0) or ctx.get("id", 0))
            if not container_id:
                raise ValueError("container_id required")

            parts = db.list_parts_in_container(container_id)
            rows = []
            for p in parts:
                raw_design_id = str(p.get("design_id", "") or "")
                # Prefer row values, then part meta
                part_meta = db.get_part(raw_design_id) or {}
                color_name = str(p.get("color_name", "") or "")
                qty = int(p.get("qty", 0) or p.get("quantity", 0) or 0)

                link = (
                    p.get("rebrickable_url")
                    or p.get("part_url")
                    or (f"https://rebrickable.com/parts/{raw_design_id}/" if raw_design_id else "")
                )
                img = (
                    p.get("image_url")
                    or p.get("img_url")
                    or p.get("part_img_url")
                    or part_meta.get("part_img_url")
                    or part_meta.get("image_url")
                    or ""
                )

                rows.append(
                    {
                        "Design ID": raw_design_id,
                        "Part Name": str(p.get("part_name", "") or part_meta.get("name") or ""),
                        "Color": color_name,
                        "Qty": qty,
                        "Link": link,
                        "Image": img,
                    }
                )
            columns = ["Design ID", "Part Name", "Color", "Qty", "Link", "Image"]
            return rows, columns

        # ----- Master (loose parts) index -----
        if table_key == "inventory_master":
            rows_raw = _query_master_rows()
            rows = []
            for r in rows_raw:
                rows.append(
                    {
                        "Design ID": str(r.get("design_id", "")),
                        "Part Name": str(r.get("part_name", "")),
                        "Color": str(r.get("color_name", "")),
                        "Drawer": str(r.get("drawer", "")),
                        "Container": str(r.get("container", "")),
                        "Qty": int(r.get("qty", 0) or 0),
                        "Link": r.get("part_url")
                        or (
                            f"https://rebrickable.com/parts/{r.get('design_id','')}/"
                            if r.get("design_id")
                            else ""
                        ),
                        "Image": r.get("part_img_url") or "",
                    }
                )
            columns = [
                "Design ID",
                "Part Name",
                "Color",
                "Drawer",
                "Container",
                "Qty",
                "Link",
                "Image",
            ]
            return rows, columns

        # ----- Parts for a specific set (set detail page) -----
        if table_key == "set_parts":
            set_number = str(ctx.get("set_number") or ctx.get("set_num") or ctx.get("id") or "")
            if not set_number:
                raise ValueError("set_number required")

            svc = get_set_parts_service()
            parts = list(svc.list_parts(set_number=set_number))
            rows = []
            for part in parts:
                design_id = str(part.get("design_id", "") or "")
                rows.append(
                    {
                        "Design ID": design_id,
                        "Part Name": str(part.get("name", "")),
                        "Color": str(part.get("color_name", "")),
                        "Qty": int(part.get("quantity", 0) or 0),
                        "Link": part.get("part_url")
                        or f"https://rebrickable.com/parts/{design_id}/",
                        "Image": part.get("part_img_url") or "",
                    }
                )
            columns = ["Design ID", "Part Name", "Color", "Qty", "Link", "Image"]
            return rows, columns

        # ----- Part counts across site -----
        if table_key == "part_counts":
            with db._connect() as conn:  # pylint: disable=protected-access
                rs = conn.execute(
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

            rows = [
                {
                    "Design ID": str(r["design_id"]) if r["design_id"] is not None else "",
                    "Part Name": r["part_name"] or "",
                    "Total Qty": int(r["total_qty"] or 0),
                    "Link": r["part_url"]
                    or (
                        f"https://rebrickable.com/parts/{r['design_id']}/"
                        if r["design_id"] is not None
                        else ""
                    ),
                    "Image": r["part_img_url"] or "",
                }
                for r in rs
            ]
            columns = ["Design ID", "Part Name", "Total Qty", "Link", "Image"]
            return rows, columns

        # ----- Part+Color counts across site -----
        if table_key == "part_color_counts":
            with db._connect() as conn:  # pylint: disable=protected-access
                rs = conn.execute(
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
                        JOIN parts p ON sp.design_id = p.design_id
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

            def color_hex_to_css(h: str | None) -> str:
                return (h or "").lstrip("#")

            rows = []
            for r in rs:
                design_id = str(r["design_id"]) if r["design_id"] is not None else ""
                color_id = r["color_id"]
                rb_color_url = (
                    f"https://rebrickable.com/parts/{design_id}/{int(color_id)}/"
                    if design_id and (color_id is not None)
                    else (
                        r["part_url"]
                        or (f"https://rebrickable.com/parts/{design_id}/" if design_id else "")
                    )
                )
                rows.append(
                    {
                        "Design ID": design_id,
                        "Part Name": r["part_name"] or "",
                        "Color": r["color_name"] or "(unknown)",
                        "Hex": color_hex_to_css(r["color_hex"]),
                        "Total Qty": int(r["total_qty"] or 0),
                        "Link": rb_color_url,
                        "Image": r["part_img_url"] or "",
                    }
                )
            columns = ["Design ID", "Part Name", "Color", "Hex", "Total Qty", "Link", "Image"]
            return rows, columns

        # ----- Storage location counts -----
        if table_key == "location_counts":
            with db._connect() as conn:  # pylint: disable=protected-access
                rs = conn.execute(
                    """
                    SELECT
                        COALESCE(d.name, i.drawer)     AS drawer,
                        COALESCE(c2.name, i.container) AS container,
                        c2.id                          AS container_id,
                        SUM(i.quantity)                AS total_qty
                    FROM inventory i
                    LEFT JOIN containers c2 ON c2.id = i.container_id
                    LEFT JOIN drawers    d  ON d.id  = c2.drawer_id
                    WHERE i.status NOT IN ('built', 'wip', 'in_box', 'teardown')
                    GROUP BY COALESCE(d.name, i.drawer), COALESCE(c2.name, i.container)
                    """
                ).fetchall()

            rows = []
            for r in rs:
                drawer = r["drawer"] or ""
                container = r["container"] or ""
                if drawer and container:
                    loc = f"{drawer} / {container}"
                elif drawer:
                    loc = drawer
                elif container:
                    loc = container
                else:
                    loc = "(unknown)"
                rows.append(
                    {
                        "Location": loc,
                        "Total Qty": int(r["total_qty"] or 0),
                    }
                )
            columns = ["Location", "Total Qty"]
            return rows, columns

        # ----- Per-part loose inventory (part detail: Loose Parts table) -----
        if table_key == "part_in_loose":
            design_id = str(ctx.get("design_id") or ctx.get("part_id") or ctx.get("id") or "")
            if not design_id:
                raise ValueError("design_id required")
            rows_src = get_inventory_service().loose_inventory_for_part(design_id)
            rows = []
            for r in rows_src:
                rows.append(
                    {
                        "Drawer": str(r.get("drawer", "") or ""),
                        "Container": str(r.get("container", "") or ""),
                        "Color": str(r.get("color_name", "") or ""),
                        "Qty": int(r.get("quantity", 0) or 0),
                    }
                )
            columns = ["Drawer", "Container", "Color", "Qty"]
            return rows, columns

        # ----- Per-part in-sets inventory (part detail: In Sets table) -----
        if table_key == "part_in_sets":
            design_id = str(ctx.get("design_id") or ctx.get("part_id") or ctx.get("id") or "")
            if not design_id:
                raise ValueError("design_id required")
            rows_src = get_set_parts_service().sets_for_part_with_colors(design_id=design_id)
            rows = []
            for r in rows_src:
                rows.append(
                    {
                        "Set Number": str(r.get("set_num", "") or ""),
                        "Set Name": str(r.get("set_name", "") or ""),
                        "Color": str(r.get("color_name", "") or ""),
                        "Qty": int(r.get("quantity", 0) or 0),
                    }
                )
            columns = ["Set Number", "Set Name", "Color", "Qty"]
            return rows, columns

        # If we reached here, the key is unknown.
        raise ValueError(f"Unknown export key: {table_key}")


# --- BEGIN: bootstrap helpers for dev.sh and direct execution ---

# If a FastAPI app named `app` exists, add a simple /health route for readiness checks.
try:
    from fastapi import FastAPI  # type: ignore[attr-defined]

    if isinstance(globals().get("app"), FastAPI):  # noqa: SIM401
        _fastapi_app = globals()["app"]

        @_fastapi_app.get("/health")
        def _health() -> dict[str, str]:
            return {"status": "ok"}

except Exception:
    # If FastAPI isn't in use here, just ignore.
    pass


def _bootstrap_start() -> None:
    """
    Try to start the server in a forgiving way for local dev:
    - If there's a FastAPI app, run it with uvicorn.
    - Else if there is a callable named run/serve/start/main, call it.
    - Else if there's a Handler class, spin up a basic HTTPServer with it.
    """
    import os
    import sys

    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")  # allow LAN access by default

    # 1) FastAPI app + uvicorn
    try:
        from fastapi import FastAPI  # type: ignore

        app_obj = globals().get("app")
        if isinstance(app_obj, FastAPI):
            try:
                import uvicorn  # type: ignore
            except Exception:
                print("uvicorn is not installed; cannot run FastAPI app.", file=sys.stderr)
            else:
                print(f"🔌 Starting FastAPI app on http://{host}:{port}")
                uvicorn.run(app_obj, host=host, port=port, log_level="info")
                return
    except Exception:
        # Not a FastAPI setup or import error; continue to other strategies.
        pass

    # 2) Conventional entrypoints: run/serve/start/main
    for name in ("run", "serve", "start", "main"):
        fn = globals().get(name)
        if callable(fn):
            print(f"🔌 Starting via `{name}()` on http://127.0.0.1:{port}")
            try:
                # If the function accepts a port, pass it; otherwise call without args.
                import inspect

                sig = inspect.signature(fn)
                if any(
                    p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.name == "port"
                    for p in sig.parameters.values()
                ):
                    fn(port=port)  # type: ignore[call-arg]
                else:
                    fn()  # type: ignore[misc]
            except TypeError:
                # Some servers expect (host, port)
                try:
                    fn("127.0.0.1", port)  # type: ignore[misc]
                except Exception:
                    fn()  # type: ignore[misc]
            return

    # 3) Barebones HTTPServer if a `Handler` is defined in this module
    try:
        from http.server import HTTPServer  # type: ignore

        Handler = globals().get("Handler")
        if Handler is not None:
            print(f"🔌 Starting basic HTTPServer on http://{host}:{port}")
            httpd = HTTPServer((host, port), Handler)  # type: ignore[arg-type]
            httpd.serve_forever()
            return
    except Exception as e:  # pragma: no cover
        print(f"Failed to start basic HTTPServer: {e}", file=sys.stderr)

    print("No known server entrypoint found. Nothing to run.", file=sys.stderr)


if __name__ == "__main__":
    _bootstrap_start()

# --- END: bootstrap helpers for dev.sh and direct execution ---
