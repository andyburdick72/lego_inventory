"""
Light-weight HTTP UI for the Lego inventory database (inventory_db.py).

* “/”              – master table (one row per part + color + status + location)
* “/parts/<id>”    – detail page for a single part
* “/locations”     – loose-parts hierarchy  (drawer ▸ container ▸ parts)
* “/sets/<set_num>” – detail page for a single set and its parts
* “/my-sets”        – list of all sets

No external dependencies – just the std-lib.

Usage:
    python3 src/server.py
"""
from __future__ import annotations

import html
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List

# --------------------------------------------------------------------------- local import
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))  # ensure we can import inventory_db
import inventory_db as db  # noqa: E402
from inventory_db import get_set


SET_STATUSES = {"built", "wip", "in_box", "teardown"}

# Mapping from status code to display-friendly name
STATUS_DISPLAY_NAMES = {
    "built": "Built",
    "wip": "Work in Progress",
    "in_box": "In Box",
    "teardown": "Teardown",
}


# --------------------------------------------------------------------------- helpers
def _html_page(title: str, body_html: str, total_qty: int | None = None) -> str:
    """Very small HTML skeleton with improved header."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<style>
  body {{ font-family: sans-serif; margin: 0; padding: 0; }}
  header {{ background: #0645ad; color: white; padding: 1rem; text-align: center; }}
  nav {{ background: #f2f2f2; padding: 0.5rem; text-align: center; }}
  nav a {{ margin: 0 1em; text-decoration: none; color: #0645ad; font-weight: bold; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 2px 6px; }}
  th {{ background: #eee; text-align: left; }}
  tr:hover {{ background: #ffffe0; }}
</style>
</head>
<body>
<header>
  <h1>Ervin-Burdick's Bricks</h1>
  {f"<p><strong>Total Parts in Inventory:</strong> {total_qty:,}</p>" if total_qty is not None else ""}
</header>
<nav>
  <a href="/">All Parts</a>
  <a href="/locations">Loose Parts by Location</a>
  <a href="/my-sets">Sets</a>
  <a href="/part-counts">Part Counts</a>
  <a href="/part-color-counts">Part + Color Counts</a>
  <a href="/location-counts">Storage Location Counts</a>
</nav>
<hr>
{body_html}
<script>
  $(document).ready(function () {{
    $("table").each(function () {{
      var table = $(this).DataTable({{
        pageLength: 50,
        order: [],
        paging: true,
        language: {{
          search: "Search all columns:",
          zeroRecords: "No matching parts found"
        }},
        initComplete: function () {{
          this.api().columns().every(function (index) {{
            var column = this;
            var th = $(column.header());
            var title = th.text();
            th.empty().append('<div style="margin-bottom: 6px;">' + title + '</div>');
            if (title !== "Qty" && title !== "Total Quantity" && title !== "Quantity" && title !== "Image" && title !== "Rebrickable Link") {{
              var input = $('<input type="text" placeholder="Search…" style="width:100%; margin-top: 6px;" />')
                .appendTo(th)
                .on('keyup change clear', function () {{
                  if (column.search() !== this.value) {{
                    column.search(this.value).draw();
                  }}
                }});
            }}
          }});
        }}
      }});
    }});
  }});
</script>
</body></html>"""


def _make_color_cell(name: str, hex_code: str) -> str:
    fg = "#000" if sum(int(hex_code[i : i + 2], 16) for i in (0, 2, 4)) > 382 else "#fff"
    return f'<td style="background: #{hex_code}; color:{fg}">{html.escape(name)}</td>'


def _query_master_rows() -> List[Dict]:
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
                    COALESCE(i.drawer , '')    AS drawer,
                    COALESCE(i.container,'')   AS container,
                    SUM(i.quantity)   AS qty
            FROM inventory i
            JOIN parts  p ON p.design_id = i.design_id
            JOIN colors c ON c.id        = i.color_id
            GROUP BY i.design_id, i.color_id, i.status,
                     i.set_number, i.drawer, i.container
            ORDER BY p.design_id
            """
        ).fetchall()
    result = []
    for r in rows:
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
                qty=r["qty"],
            )
        )
    return result


def _build_sets_map() -> Dict[str, List[Dict]]:
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
    sets: Dict[str, Dict[str, List[Dict]]] = {}
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



def _numeric_set_sort_key(set_no: str) -> int:
    try:
        return int(set_no)
    except ValueError:
        return float('inf')


# Helper to get display-friendly status name
def _display_status(status: str) -> str:
    if status == "unsorted":
        return "Unsorted"
    return STATUS_DISPLAY_NAMES.get(status, "Loose")


# --------------------------------------------------------------------------- request-handler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        try:
            if self.path == "/" or self.path.startswith("/?"):
                self._serve_master()
            elif self.path.startswith("/parts/"):
                m = re.match(r"^/parts/([^/?#]+)", self.path)
                self._serve_part(m.group(1)) if m else self._not_found()
            elif self.path.startswith("/locations"):
                self._serve_locations()
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
            else:
                self._not_found()
        except Exception as exc:  # pylint: disable=broad-except
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Internal error:\n{exc}".encode())


    def _serve_all_sets(self):
        with db._connect() as conn:
            rows = conn.execute(
                """
                SELECT set_num, name, year, image_url, rebrickable_url, status, added_at
                FROM sets
                ORDER BY added_at DESC
                """
            ).fetchall()
            # Get total quantity of all inventory rows (all parts)
            total_qty_row = conn.execute("SELECT SUM(quantity) AS total_qty FROM inventory").fetchone()
            parts_count = total_qty_row["total_qty"] if total_qty_row and total_qty_row["total_qty"] is not None else 0

        body = ["<h1>All Owned Sets</h1>",
                """<table id="sets_table">
<thead>
    <tr>
        <th>Set Number</th>
        <th>Name</th>
        <th>Year</th>
        <th>Status</th>
        <th>Rebrickable Link</th>
        <th>Image</th>
    </tr>
</thead>
<tbody>"""]

        for r in rows:
            body.append("<tr>")
            # Set Number, Name, Year, Status, Rebrickable Link, Image
            # Make set number a link to /sets/<set_num>
            body.append(f"<td><a href='/sets/{html.escape(r['set_num'])}'>{html.escape(r['set_num'])}</a></td>")
            body.append(f"<td>{html.escape(r['name'])}</td>")
            body.append(f"<td>{r['year']}</td>")
            body.append(f"<td>{html.escape(_display_status(r['status']))}</td>")
            body.append(f"<td><a href='{html.escape(r['rebrickable_url'])}' target='_blank'>View</a></td>")
            body.append(f"<td><img src='{html.escape(r['image_url'])}' alt='Set image' style='height: 48px;'></td>")
            body.append("</tr>")

        body.append("</tbody></table>")
        self._send_ok(_html_page("Sets", "".join(body), total_qty=parts_count))

    def _serve_set(self, set_num: str):
        # Get set metadata using get_set
        set_info = get_set(set_num)
        if not set_info:
            self._not_found()
            return

        # Retrieve the list of parts for this set by calling the appropriate DB function.
        if hasattr(db, "get_parts_for_set"):
            parts = db.get_parts_for_set(set_num)
        else:
            # fallback: do the query inline (legacy)
            with db._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        p.design_id,
                        p.name AS name,
                        c.name AS color_name,
                        c.hex AS hex,
                        sp.quantity AS quantity,
                        p.part_url AS part_url,
                        p.part_img_url AS part_img_url
                    FROM set_parts sp
                    JOIN parts p ON p.design_id = sp.design_id
                    JOIN colors c ON c.id = sp.color_id
                    WHERE sp.set_num = ?
                    """,
                    (set_num,)
                ).fetchall()
                # Convert to list of dicts
                parts = []
                for r in rows:
                    parts.append({
                        "design_id": r["design_id"],
                        "name": r["name"],
                        "color_name": r["color_name"],
                        "hex": r["hex"],
                        "quantity": r["quantity"],
                        "part_url": r["part_url"],
                        "part_img_url": r["part_img_url"],
                    })

        # Compute total quantity for the set
        total_qty = sum(p.get('quantity', 0) for p in parts)
        total_qty_str = f"{total_qty:,}"

        # Overall inventory total for the site header
        with db._connect() as conn:
            total_qty_row = conn.execute("SELECT SUM(quantity) AS total_qty FROM inventory").fetchone()
            overall_total_qty = total_qty_row["total_qty"] if total_qty_row and total_qty_row["total_qty"] is not None else 0

        # Header: set image on left, set ID + name as a hyperlink to Rebrickable in header, total quantity in header
        set_img_url = set_info.get("image_url") or set_info.get("set_img_url") or ""
        set_name = set_info.get("name", set_num)
        set_url = set_info.get("rebrickable_url") or set_info.get("set_url") or ""
        header_html = (
            f"<div style='display: flex; align-items: center; gap: 1.5em; margin-bottom: 1em;'>"
            f"<img src='{html.escape(set_img_url)}' alt='Set image' style='max-width: 150px; height: auto;'>"
            f"<div>"
            f"<h1 style='margin:0;'><a href='{html.escape(set_url)}' target='_blank'>{html.escape(set_num)} - {html.escape(set_name)} (Total Qty: {total_qty_str})</a></h1>"
            f"</div>"
            f"</div>"
        )

        # Table with columns: Part ID, Part Name, Color, Qty, Rebrickable Link, Image
        table_body = []
        for part in parts:
            table_body.append("<tr>")
            design_id = html.escape(str(part.get('design_id', '')))
            # Part ID cell: hyperlink to part page
            table_body.append(f'<td><a href="/parts/{design_id}">{design_id}</a></td>')
            # Part Name cell: plain text
            table_body.append(f"<td>{html.escape(str(part.get('name', '')))}</td>")
            color_name = str(part.get('color_name', ''))
            hex_code = part.get('hex')
            if hex_code:
                table_body.append(_make_color_cell(color_name, hex_code))
            else:
                table_body.append(f"<td>{html.escape(color_name)}</td>")
            table_body.append(f"<td>{part.get('quantity', 0)}</td>")
            link = part.get('part_url') or (f"https://rebrickable.com/parts/{part.get('design_id','')}/")
            img = part.get('part_img_url') or "https://rebrickable.com/static/img/nil.png"
            table_body.append(f"<td><a href='{html.escape(link)}' target='_blank'>View</a></td>")
            table_body.append(f"<td><img src='{html.escape(img)}' alt='Part image' style='height: 32px;'></td>")
            table_body.append("</tr>")

        if not table_body:
            table_body.append("<tr><td colspan='6'>No matching parts found</td></tr>")

        table_html = (
            "<table><thead><tr>"
            "<th>Part ID</th><th>Part Name</th><th>Color</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th>"
            "</tr></thead><tbody>"
            + "".join(table_body) +
            "</tbody>"
            f"<tfoot><tr><th colspan='3'>Total</th><th>{total_qty:,}</th><th colspan='2'></th></tr></tfoot>"
            "</table>"
        )

        # Use _html_page for consistent look, pass overall inventory total for header
        self._send_ok(_html_page(f"Set {set_num}", header_html + table_html, total_qty=overall_total_qty))

    def _send_html(self, html_doc: str, status: int = 200):
        html_bytes = html_doc.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)
    def _serve_location_counts(self):
        with db._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(i.drawer, '') AS drawer,
                    COALESCE(i.container, '') AS container,
                    SUM(i.quantity) AS total_qty
                FROM inventory i
                WHERE i.status NOT IN ('built', 'wip', 'in_box', 'teardown')
                GROUP BY i.drawer, i.container
                """
            ).fetchall()
            # Get total quantity of all inventory rows (not just filtered)
            total_qty_row = conn.execute(
                "SELECT SUM(quantity) AS total_qty FROM inventory"
            ).fetchone()
            total_qty = total_qty_row["total_qty"] if total_qty_row and total_qty_row["total_qty"] is not None else 0

        locations = []
        for r in rows:
            if r["drawer"] and r["container"]:
                loc = f"{r['drawer']} / {r['container']}"
            elif r["drawer"]:
                loc = r["drawer"]
            elif r["container"]:
                loc = r["container"]
            else:
                loc = "(unknown)"
            locations.append((loc, r["total_qty"]))

        locations.sort(key=lambda x: x[1], reverse=True)
        subtotal = sum(qty for _, qty in locations)

        body = ["<h1>Storage Location Counts</h1>",
                "<table><thead><tr><th>Location</th><th>Total Quantity</th></tr></thead><tbody>"]

        for loc, qty in locations:
            body.append(f"<tr><td>{html.escape(loc)}</td><td>{qty:,}</td></tr>")

        body.append("</tbody>")
        body.append(f"<tfoot><tr><th>Total</th><th>{subtotal:,}</th></tr></tfoot>")
        body.append("</table>")

        self._send_ok(_html_page("Storage Location Counts", "".join(body), total_qty=total_qty))

    # ..................................................................... pages
    def _serve_master(self):
        rows = _query_master_rows()
        total_qty = sum(r["qty"] for r in rows)
        body = [f"<h1>All Parts by Status and Location</h1>",
                "<table><thead><tr>",
                "<th>ID</th><th>Name</th><th>Color</th><th>Status</th>"
                "<th>Location</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(
                f"<td><a href='/parts/{r['design_id']}'>{html.escape(r['design_id'])}</a></td>"
            )
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(_make_color_cell(r["color_name"], r["hex"]))
            body.append(f"<td>{html.escape(_display_status(r['status']))}</td>")
            body.append(f"<td>{html.escape(r['location'])}</td>")
            body.append(f"<td>{r['qty']}</td>")
            # Rebrickable link and image
            link = r['part_url'] or f"https://rebrickable.com/parts/{r['design_id']}/"
            img  = r['part_img_url'] or "https://rebrickable.com/static/img/nil.png"
            body.append(f"<td><a href='{html.escape(link)}' target='_blank'>View</a></td>")
            body.append(f"<td><img src='{html.escape(img)}' alt='Part image' style='height: 32px;'></td>")
            body.append("</tr>")
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='6'>Total</th><th colspan='2'>{total_qty:,}</th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Inventory – Parts", "".join(body), total_qty=total_qty))

    def _serve_part(self, design_id: str):
        # Get overall inventory total for header
        total_qty = sum(r["qty"] for r in _query_master_rows())
        # Fetch part details including part_url and part_img_url
        with db._connect() as conn:
            part_row = conn.execute(
                """
                SELECT design_id, name, part_url, part_img_url
                FROM parts WHERE design_id = ?
                """,
                (design_id,)
            ).fetchone()
            if not part_row:
                self._not_found()
                return
            # Get total quantity of this part across all inventory
            total_quantity_row = conn.execute(
                "SELECT SUM(quantity) AS total_quantity FROM inventory WHERE design_id = ?",
                (design_id,)
            ).fetchone()
            total_quantity = total_quantity_row["total_quantity"] if total_quantity_row and total_quantity_row["total_quantity"] is not None else 0
            # Get inventory rows for this part
            rows = conn.execute(
                """
                SELECT i.status, i.set_number, i.drawer, i.container, i.quantity,
                       c.name AS color_name, c.hex AS hex
                FROM inventory i
                JOIN colors c ON c.id = i.color_id
                WHERE i.design_id = ?
                """,
                (design_id,)
            ).fetchall()

        # Build header with image, (design_id - part_name) as link, and total quantity
        part_url = part_row["part_url"] or f"https://rebrickable.com/parts/{design_id}/"
        part_img_url = part_row["part_img_url"] or "https://rebrickable.com/static/img/nil.png"
        part_name = part_row["name"]
        body = [
            f"<div style='display: flex; align-items: center; gap: 1em; margin-bottom: 1em;'>"
            f"<img src='{html.escape(part_img_url)}' alt='{html.escape(part_name)}' style='height: 64px;'>"
            f"<h1 style='margin:0;'><a href='{html.escape(part_url)}' target='_blank'>{html.escape(design_id)} - {html.escape(part_name)}</a></h1>"
            f"<span style='font-size: 1.1em; margin-left: 1em;'>Total Quantity: {total_quantity:,}</span>"
            f"</div>"
        ]
        body.append("<table><thead><tr><th>Color</th><th>Status</th><th>Location</th><th>Qty</th></tr></thead><tbody>")
        for r in rows:
            if r["status"] in SET_STATUSES:
                loc = r["set_number"] or "(unknown set)"
            else:
                loc = f"{r['drawer']}/{r['container']}".strip("/")
            body.append("<tr>")
            body.append(_make_color_cell(r["color_name"], r["hex"]))
            body.append(f"<td>{html.escape(_display_status(r['status']))}</td>")
            body.append(f"<td>{html.escape(loc)}</td>")
            body.append(f"<td>{r['quantity']}</td>")
            body.append("</tr>")
        body.append("</tbody>")
        total_qty_part = sum(r["quantity"] for r in rows)
        body.append(f"<tfoot><tr><th colspan='3'>Total</th><th>{total_qty_part:,}</th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page(f"Part {design_id}", "".join(body), total_qty=total_qty))

    def _serve_locations(self):
        total_qty = sum(r["qty"] for r in _query_master_rows())
        tree = db.locations_map()
        body = ["<h1>Loose Parts by Location</h1>"]
        # Organize parts by drawer and container
        drawer_map: Dict[str, Dict[str, List[Dict]]] = {}
        for (drawer, container), parts in tree.items():
            drawer_map.setdefault(drawer, {}).setdefault(container, parts)
        for drawer, containers in drawer_map.items():
            # Compute drawer total up front
            drawer_total = 0
            container_totals = {}
            for container, parts in containers.items():
                container_total = sum(p["qty"] for p in parts)
                container_totals[container] = container_total
                drawer_total += container_total
            # Drawer heading as <details>/<summary>
            body.append(f"<details>")
            body.append(f"<summary style='font-size: 1.5em; font-weight: bold; margin-top: 1em;'>{html.escape(drawer)} (total quantity: {drawer_total:,})</summary>")
            for container, parts in containers.items():
                container_total = container_totals[container]
                # Container details with increased indent and total in summary
                body.append(
                    f"<details style='margin-left: 4em;'><summary>{html.escape(container)} (total: {container_total:,})</summary>"
                )
                body.append("<table><thead><tr><th>ID</th><th>Name</th><th>Color</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>")
                for p in parts:
                    body.append("<tr>")
                    body.append(
                        f"<td><a href='/parts/{p['design_id']}'>{html.escape(p['design_id'])}</a></td>"
                    )
                    body.append(f"<td>{html.escape(p['name'])} ({html.escape(p['design_id'])})</td>")
                    body.append(_make_color_cell(p["color_name"], p["hex"]))
                    body.append(f"<td>{p['qty']}</td>")
                    # Rebrickable link + image (fallbacks)
                    _link = f"https://rebrickable.com/parts/{p['design_id']}/"
                    _part = db.get_part(p['design_id']) or {}
                    _img  = _part.get('part_img_url') or "https://rebrickable.com/static/img/nil.png"
                    body.append(f"<td><a href='{html.escape(_link)}' target='_blank'>View</a></td>")
                    body.append(f"<td><img src='{html.escape(_img)}' alt='Part image' style='height: 32px;'></td>")
                    body.append("</tr>")
                body.append("</tbody>")
                body.append(f"<tfoot><tr><th colspan='3'>Total</th><th colspan='3'>{container_total:,}</th></tr></tfoot>")
                body.append("</table></details>")
            body.append("</details>")
        self._send_ok(_html_page("Locations", "".join(body), total_qty=total_qty))

    # The /sets route and _serve_sets method have been removed.

    def _serve_part_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT i.design_id, p.name AS part_name, p.part_url AS part_url, p.part_img_url AS part_img_url, SUM(i.quantity) AS total_qty
                FROM inventory i
                JOIN parts p ON i.design_id = p.design_id
                GROUP BY i.design_id, p.name, p.part_url, p.part_img_url
                ORDER BY total_qty DESC
                """
            ).fetchall()
        total_qty = sum(r["total_qty"] for r in rows)
        body = ["<h1>Part Counts</h1>",
                "<table><thead><tr><th>Part ID</th><th>Name</th><th>Total Quantity</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(f"<td><a href='/parts/{html.escape(r['design_id'])}'>{html.escape(r['design_id'])}</a></td>")
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(f"<td>{r['total_qty']:,}</td>")
            _link = r['part_url'] or f"https://rebrickable.com/parts/{r['design_id']}/"
            _img  = r['part_img_url'] or "https://rebrickable.com/static/img/nil.png"
            body.append(f"<td><a href='{html.escape(_link)}' target='_blank'>View</a></td>")
            body.append(f"<td><img src='{html.escape(_img)}' alt='Part image' style='height: 32px;'></td>")
            body.append("</tr>")
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='3'>Total</th><th colspan='2'></th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Part Counts", "".join(body), total_qty=total_qty))

    def _serve_part_color_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT i.design_id, p.name AS part_name, p.part_url AS part_url, p.part_img_url AS part_img_url, c.name AS color_name, c.hex AS hex, SUM(i.quantity) AS total_qty
                FROM inventory i
                JOIN parts p ON i.design_id = p.design_id
                JOIN colors c ON i.color_id = c.id
                GROUP BY i.design_id, p.name, p.part_url, p.part_img_url, c.name, c.hex
                ORDER BY total_qty DESC
                """
            ).fetchall()
        total_qty = sum(r["total_qty"] for r in rows)
        body = ["<h1>Part + Color Counts</h1>",
                "<table><thead><tr><th>Part ID</th><th>Name</th><th>Color</th><th>Total Quantity</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(f"<td><a href='/parts/{html.escape(r['design_id'])}'>{html.escape(r['design_id'])}</a></td>")
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(_make_color_cell(r["color_name"], r["hex"]))
            body.append(f"<td>{r['total_qty']:,}</td>")
            _link = r['part_url'] or f"https://rebrickable.com/parts/{r['design_id']}/"
            _img  = r['part_img_url'] or "https://rebrickable.com/static/img/nil.png"
            body.append(f"<td><a href='{html.escape(_link)}' target='_blank'>View</a></td>")
            body.append(f"<td><img src='{html.escape(_img)}' alt='Part image' style='height: 32px;'></td>")
            body.append("</tr>")
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='4'>Total</th><th colspan='2'></th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Part + Color Counts", "".join(body), total_qty=total_qty))

    # ..................................................................... utilities
    def _not_found(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def _send_ok(self, html_doc: str):
        html_bytes = html_doc.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)


# --------------------------------------------------------------------------- bootstrap
def main():
    host, port = "0.0.0.0", int(os.environ.get("PORT", 8000))
    # Auto-detect and print the local IP address for user convenience
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "localhost"
    finally:
        s.close()
    httpd = HTTPServer((host, port), Handler)
    print(f"Serving on http://{local_ip}:{port}  – Ctrl+C to quit")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…")


if __name__ == "__main__":
    main()