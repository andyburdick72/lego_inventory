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
  {f"<p><strong>Total Parts in Inventory:</strong> {total_qty:,}</p>" if total_qty is not None else f"<p><strong>Total Parts in Inventory:</strong> {db.totals()['overall_total']:,}</p>"}
</header>
<nav>
  <a href="/">Loose Parts</a>
  <a href="/drawers">Drawers</a>
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
            if (title !== "Qty" && title !== "Total Quantity" && title !== "Quantity" && title !== "Image" && title !== "Rebrickable Link" && title !== "Unique Parts" && title !== "Total Pieces" && title !== "Containers") {{
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

        total_sets = len(rows)

        body = [f"<h1>All Owned Sets ({total_sets})</h1>",
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
        self._send_ok(_html_page("All Owned Sets", "".join(body), total_qty=None))

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

        # Use _html_page for consistent look, pass None for total_qty to use combined totals in the header
        self._send_ok(_html_page(f"Set {set_num}", header_html + table_html, total_qty=None))

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

        self._send_ok(_html_page("Storage Location Counts", "".join(body), total_qty=None))

    # ..................................................................... pages
    def _serve_master(self):
        rows = _query_master_rows()
        total_qty = sum(r["qty"] for r in rows)
        body = [f"<h1>All Loose Parts</h1>",
                "<table><thead><tr>",
                "<th>ID</th><th>Name</th><th>Color</th>"
                "<th>Drawer</th><th>Container</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(
                f"<td><a href='/parts/{r['design_id']}'>{html.escape(r['design_id'])}</a></td>"
            )
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(_make_color_cell(r["color_name"], r["hex"]))
            # Insert drawer and container columns before quantity
            body.append(f"<td>{html.escape(r['drawer'] or '')}</td>")
            body.append(f"<td>{html.escape(r['container'] or '')}</td>")
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
        self._send_ok(_html_page("Inventory – Parts", "".join(body), total_qty=None))

    def _serve_part(self, design_id: str):
        # Resolve part meta
        part = db.get_part(design_id) or {"design_id": design_id, "name": "Unknown part", "part_url": None, "part_img_url": None}

        # Data for the two sections
        sets_rows = db.sets_for_part(design_id)
        loose_rows = db.loose_inventory_for_part(design_id)

        # Totals for this part
        part_total = sum(r.get("quantity", 0) for r in sets_rows) + sum(r.get("quantity", 0) for r in loose_rows)

        # Header
        part_url = part.get("part_url") or f"https://rebrickable.com/parts/{design_id}/"
        part_img_url = part.get("part_img_url") or "https://rebrickable.com/static/img/nil.png"
        part_name = part.get("name", "")
        header_html = (
            f"<div style='display: flex; align-items: center; gap: 1em; margin-bottom: 1em;'>"
            f"<img src='{html.escape(part_img_url)}' alt='{html.escape(part_name)}' style='height: 64px;'>"
            f"<h1 style='margin:0;'><a href='{html.escape(part_url)}' target='_blank'>{html.escape(design_id)} - {html.escape(part_name)}</a></h1>"
            f"<span style='font-size: 1.1em; margin-left: 1em;'>Total Quantity: {part_total:,}</span>"
            f"</div>"
        )

        # In Sets table
        sets_body = []
        for r in sets_rows:
            color_cell = _make_color_cell(r["color_name"], r.get("hex")) if r.get("hex") else f"<td>{html.escape(r['color_name'])}</td>"
            sets_body.append("<tr>")
            sets_body.append(f"<td><a href='/sets/{html.escape(r['set_num'])}'>{html.escape(r['set_num'])}</a> – {html.escape(r['set_name'])}</td>")
            sets_body.append(color_cell)
            sets_body.append(f"<td>{r['quantity']}</td>")
            sets_body.append("</tr>")
        if not sets_body:
            sets_body.append("<tr><td colspan='3'>This part is not currently in any sets.</td></tr>")
        sets_table = (
            "<h2>In Sets</h2>"
            "<table><thead><tr><th>Set</th><th>Color</th><th>Qty</th></tr></thead><tbody>"
            + "".join(sets_body) + "</tbody></table>"
        )

        # Loose Parts table
        loose_body = []
        for r in loose_rows:
            color_cell = _make_color_cell(r["color_name"], r.get("hex")) if r.get("hex") else f"<td>{html.escape(r['color_name'])}</td>"
            loose_body.append("<tr>")
            loose_body.append(f"<td>{html.escape(str(r.get('drawer','')))}</td>")
            loose_body.append(f"<td>{html.escape(str(r.get('container','')))}</td>")
            loose_body.append(color_cell)
            loose_body.append(f"<td>{r['quantity']}</td>")
            loose_body.append("</tr>")
        if not loose_body:
            loose_body.append("<tr><td colspan='4'>No loose parts on hand.</td></tr>")
        loose_table = (
            "<h2>Loose Parts</h2>"
            "<table><thead><tr><th>Drawer</th><th>Container</th><th>Color</th><th>Qty</th></tr></thead><tbody>"
            + "".join(loose_body) + "</tbody></table>"
        )

        self._send_ok(_html_page(f"Part {design_id}", header_html + sets_table + loose_table, total_qty=None))

    # The _serve_locations method has been removed.

    def _serve_drawers(self):
        rows = db.list_drawers()
        total_containers = sum(r.get("container_count", 0) for r in rows)
        total_pieces = sum(r.get("part_count", 0) for r in rows)
        body = ["<h1>Drawers</h1>",
                "<table id='drawers_table'>",
                "<thead><tr><th>Name</th><th>Description</th><th>Containers</th><th>Total Pieces</th></tr></thead><tbody>"]
        for r in rows:
            name = html.escape(r.get("name", ""))
            desc = html.escape(r.get("description") or "")
            containers = r.get("container_count", 0)
            pieces = r.get("part_count", 0)
            body.append(
                f"<tr><td><a href='/drawers/{r['id']}'>{name}</a></td><td>{desc}</td><td>{containers}</td><td>{pieces:,}</td></tr>"
            )
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='2' style='text-align:right'>Totals</th><th>{total_containers}</th><th>{total_pieces:,}</th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Drawers", "".join(body), total_qty=None))

    def _serve_drawer_detail(self, drawer_id: int):
        d = db.get_drawer(drawer_id)
        if not d:
            self._not_found(); return
        containers = db.list_containers_for_drawer(drawer_id)
        total_unique = sum(c.get("unique_parts", 0) for c in containers)
        total_pieces = sum(c.get("part_count", 0) for c in containers)
        header = f"<h1>Drawer: {html.escape(d['name'])}</h1>"
        if d.get("description"):
            header += f"<p>{html.escape(d['description'])}</p>"
        body = [header,
                "<p><a href='/drawers'>&larr; All drawers</a></p>",
                "<table id='containers_table'>",
                "<thead><tr><th>Pos</th><th>Name</th><th>Description</th><th>Unique Parts</th><th>Total Pieces</th></tr></thead><tbody>"]
        for c in containers:
            pos = ""
            if c.get("row_index") is not None and c.get("col_index") is not None:
                pos = f"r{c['row_index']} c{c['col_index']}"
            name = html.escape(c.get("name", ""))
            desc = html.escape(c.get("description") or "")
            uniq = c.get("unique_parts", 0)
            pieces = c.get("part_count", 0)
            body.append(
                f"<tr><td>{pos}</td><td><a href='/containers/{c['id']}'>{name}</a></td><td>{desc}</td><td>{uniq}</td><td>{pieces:,}</td></tr>"
            )
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='3' style='text-align:right'>Totals</th><th>{total_unique}</th><th>{total_pieces:,}</th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page(f"Drawer {d['name']}", "".join(body), total_qty=None))

    def _serve_container_detail(self, container_id: int):
        c = db.get_container(container_id)
        if not c:
            self._not_found(); return
        parts = db.list_parts_in_container(container_id)
        total_qty = sum(p.get("qty", 0) for p in parts)
        header = (
            f"<h1>Container: {html.escape(c['name'])}</h1>"
            f"<p>Drawer: <a href='/drawers/{c['drawer_id']}'>{html.escape(c.get('drawer_name',''))}</a></p>"
        )
        body = [header,
                "<table id='container_parts'>",
                "<thead><tr><th>Design ID</th><th>Part</th><th>Color</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>"]
        for p in parts:
            design_id = html.escape(str(p.get("design_id", "")))
            part_name = html.escape(str(p.get("part_name", "")))
            color_name = str(p.get("color_name", ""))
            hex_code = p.get("hex")
            color_td = _make_color_cell(color_name, hex_code) if hex_code else f"<td>{html.escape(color_name)}</td>"
            qty = p.get("qty", 0)
            link = f"https://rebrickable.com/parts/{p.get('design_id','')}/"
            part_meta = db.get_part(p.get('design_id','')) or {}
            img = part_meta.get('part_img_url') or "https://rebrickable.com/static/img/nil.png"
            body.append(
                f"<tr><td><a href='/parts/{design_id}'>{design_id}</a></td><td>{part_name}</td>{color_td}<td>{qty}</td>"
                f"<td><a href='{html.escape(link)}' target='_blank'>View</a></td><td><img src='{html.escape(img)}' alt='Part image' style='height: 32px;'></td></tr>"
            )
        if not parts:
            body.append("<tr><td colspan='6'>(empty)</td></tr>")
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='3' style='text-align:right'>Total</th><th>{total_qty:,}</th><th colspan='2'></th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page(f"Container {c['name']}", "".join(body), total_qty=None))

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
        body.append(f"<tfoot><tr><th colspan='2'>Total</th><th>{total_qty:,}</th><th colspan='2'></th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Part Counts", "".join(body), total_qty=None))

    def _serve_part_color_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT design_id, part_name, part_url, part_img_url, color_name, hex, SUM(total_qty) AS total_qty
                FROM (
                    -- Loose parts
                    SELECT i.design_id,
                           p.name AS part_name,
                           p.part_url AS part_url,
                           p.part_img_url AS part_img_url,
                           c.name AS color_name,
                           c.hex  AS hex,
                           SUM(i.quantity) AS total_qty
                    FROM inventory i
                    JOIN parts  p ON i.design_id = p.design_id
                    JOIN colors c ON i.color_id  = c.id
                    WHERE i.status = 'loose'
                    GROUP BY i.design_id, p.name, p.part_url, p.part_img_url, c.name, c.hex

                    UNION ALL

                    -- Parts in sets (exclude sets marked as loose)
                    SELECT sp.design_id,
                           p.name AS part_name,
                           p.part_url AS part_url,
                           p.part_img_url AS part_img_url,
                           c.name AS color_name,
                           c.hex  AS hex,
                           SUM(sp.quantity) AS total_qty
                    FROM set_parts sp
                    JOIN parts  p ON sp.design_id = p.design_id
                    JOIN colors c ON sp.color_id  = c.id
                    JOIN sets  s  ON s.set_num    = sp.set_num
                    WHERE s.status IN ('built','wip','in_box','teardown')
                    GROUP BY sp.design_id, p.name, p.part_url, p.part_img_url, c.name, c.hex
                ) q
                GROUP BY design_id, part_name, part_url, part_img_url, color_name, hex
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
        body.append(f"<tfoot><tr><th colspan='3'>Total</th><th>{total_qty:,}</th><th colspan='2'></th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Part + Color Counts", "".join(body), total_qty=None))

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