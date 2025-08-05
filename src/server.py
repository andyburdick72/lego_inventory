"""
Light-weight HTTP UI for the Lego inventory database (inventory_db.py).

* “/”              – master table (one row per part + color + status + location)
* “/parts/<id>”    – detail page for a single part
* “/locations”     – loose-parts hierarchy  (drawer ▸ container ▸ parts)
* “/sets”          – set-parts  hierarchy   (set-number ▸ parts)

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

SET_STATUSES = {"built", "wip", "in_box", "teardown"}


# --------------------------------------------------------------------------- helpers
def _html_page(title: str, body_html: str, total_qty: int | None = None) -> str:
    """Very small HTML skeleton with improved header."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
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
  <a href="/sets">Parts by Set</a>
  <a href="/part-counts">Part Counts</a>
  <a href="/part-color-counts">Part + Color Counts</a>
  <a href="/location-counts">Storage Location Counts</a>
</nav>
<hr>
{body_html}
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
    {set_number: [{design_id, part_name, color_name, hex, qty}, …]}
    Only parts whose status is in SET_STATUSES.
    """
    with db._connect() as conn:  # pylint: disable=protected-access
        rows = conn.execute(
            f"""
            SELECT i.set_number,
                   i.design_id,
                   p.name  AS part_name,
                   c.name  AS color_name,
                   c.hex   AS hex,
                   SUM(i.quantity) AS qty
            FROM inventory i
            JOIN parts  p ON p.design_id = i.design_id
            JOIN colors c ON c.id        = i.color_id
            WHERE i.status IN ({','.join('?' * len(SET_STATUSES))})
            GROUP BY i.set_number, i.design_id, i.color_id
            ORDER BY i.design_id
            """,
            tuple(SET_STATUSES),
        ).fetchall()
    sets: Dict[str, List[Dict]] = {}
    for r in rows:
        sets.setdefault(r["set_number"] or "(unknown)", []).append(
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
            elif self.path.startswith("/sets"):
                self._serve_sets()
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
        total_qty = sum(qty for _, qty in locations)

        body = ["<h1>Storage Location Counts</h1>",
                "<table><thead><tr><th>Location</th><th>Total Quantity</th></tr></thead><tbody>"]

        for loc, qty in locations:
            body.append(f"<tr><td>{html.escape(loc)}</td><td>{qty:,}</td></tr>")

        body.append("</tbody>")
        body.append(f"<tfoot><tr><th>Total</th><th>{total_qty:,}</th></tr></tfoot>")
        body.append("</table>")

        self._send_ok(_html_page("Storage Location Counts", "".join(body), total_qty=total_qty))

    # ..................................................................... pages
    def _serve_master(self):
        rows = _query_master_rows()
        total_qty = sum(r["qty"] for r in rows)
        body = [f"<h1>All Parts by Status and Location</h1>",
                "<table><thead><tr>",
                "<th>ID</th><th>Name</th><th>Color</th><th>Status</th>",
                "<th>Location</th><th>Qty</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(
                f"<td><a href='/parts/{r['design_id']}'>{html.escape(r['design_id'])}</a></td>"
            )
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(_make_color_cell(r["color_name"], r["hex"]))
            body.append(f"<td>{html.escape(r['status'])}</td>")
            body.append(f"<td>{html.escape(r['location'])}</td>")
            body.append(f"<td>{r['qty']}</td>")
            body.append("</tr>")
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='5'>Total</th><th>{total_qty:,}</th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Inventory – Parts", "".join(body), total_qty=total_qty))

    def _serve_part(self, design_id: str):
        total_qty = sum(r["qty"] for r in _query_master_rows())
        part = db.get_part(design_id)
        if not part:
            self._not_found()
            return
        rows = db.inventory_by_part(design_id)
        body = [f"<h1>Part {html.escape(design_id)}</h1>",
                f"<p>Name: {html.escape(part['name'])}</p>",
                "<table><thead><tr><th>Color</th><th>Status</th>"
                "<th>Location</th><th>Qty</th></tr></thead><tbody>"]
        for r in rows:
            if r["status"] in SET_STATUSES:
                loc = r["set_number"] or "(unknown set)"
            else:
                loc = f"{r['drawer']}/{r['container']}".strip("/")
            body.append("<tr>")
            body.append(_make_color_cell(r["color_name"], r["hex"]))
            body.append(f"<td>{html.escape(r['status'])}</td>")
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
            # Drawer heading as <h2>
            body.append(f"<h2>{html.escape(drawer)} (total quantity: {drawer_total:,})</h2>")
            for container, parts in containers.items():
                container_total = container_totals[container]
                # Container details with increased indent and total in summary
                body.append(
                    f"<details style='margin-left: 4em;'><summary>{html.escape(container)} (total: {container_total:,})</summary>"
                )
                body.append("<table><thead><tr><th>ID</th><th>Name</th>"
                            "<th>Color</th><th>Qty</th></tr></thead><tbody>")
                for p in parts:
                    body.append("<tr>")
                    body.append(
                        f"<td><a href='/parts/{p['design_id']}'>{html.escape(p['design_id'])}</a></td>"
                    )
                    body.append(f"<td>{html.escape(p['name'])} ({html.escape(p['design_id'])})</td>")
                    body.append(_make_color_cell(p["color_name"], p["hex"]))
                    body.append(f"<td>{p['qty']}</td></tr>")
                body.append("</tbody>")
                body.append(f"<tfoot><tr><th colspan='3'>Total</th><th>{container_total:,}</th></tr></tfoot>")
                body.append("</table></details>")
        self._send_ok(_html_page("Locations", "".join(body), total_qty=total_qty))

    def _serve_sets(self):
        total_qty = sum(r["qty"] for r in _query_master_rows())
        sets = _build_sets_map()
        body = ["<h1>Sets</h1>"]
        for set_no in sorted(sets.keys(), key=str):
            parts = sets[set_no]
            set_total = sum(p["qty"] for p in parts)
            body.append(f"<details><summary>{html.escape(set_no)} (total: {set_total:,})</summary>")
            body.append("<table><thead><tr><th>ID</th><th>Name</th>"
                        "<th>Color</th><th>Qty</th></tr></thead><tbody>")
            for p in parts:
                body.append("<tr>")
                body.append(
                    f"<td><a href='/parts/{p['design_id']}'>{html.escape(p['design_id'])}</a></td>"
                )
                body.append(f"<td>{html.escape(p['part_name'])}</td>")
                body.append(_make_color_cell(p["color_name"], p["hex"]))
                body.append(f"<td>{p['qty']}</td></tr>")
            body.append("</tbody>")
            body.append(f"<tfoot><tr><th colspan='3'>Total</th><th>{set_total:,}</th></tr></tfoot>")
            body.append("</table></details>")
        self._send_ok(_html_page("Sets", "".join(body), total_qty=total_qty))

    def _serve_part_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT i.design_id, p.name AS part_name, SUM(i.quantity) AS total_qty
                FROM inventory i
                JOIN parts p ON i.design_id = p.design_id
                GROUP BY i.design_id, p.name
                ORDER BY total_qty DESC
                """
            ).fetchall()
        total_qty = sum(r["total_qty"] for r in rows)
        body = ["<h1>Part Counts</h1>",
                "<table><thead><tr><th>Part ID</th><th>Name</th><th>Total Quantity</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(f"<td><a href='/parts/{html.escape(r['design_id'])}'>{html.escape(r['design_id'])}</a></td>")
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(f"<td>{r['total_qty']:,}</td>")
            body.append("</tr>")
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='2'>Total</th><th>{total_qty:,}</th></tr></tfoot>")
        body.append("</table>")
        self._send_ok(_html_page("Part Counts", "".join(body), total_qty=total_qty))

    def _serve_part_color_counts(self):
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT i.design_id, p.name AS part_name, c.name AS color_name, c.hex AS hex, SUM(i.quantity) AS total_qty
                FROM inventory i
                JOIN parts p ON i.design_id = p.design_id
                JOIN colors c ON i.color_id = c.id
                GROUP BY i.design_id, p.name, c.name, c.hex
                ORDER BY total_qty DESC
                """
            ).fetchall()
        total_qty = sum(r["total_qty"] for r in rows)
        body = ["<h1>Part + Color Counts</h1>",
                "<table><thead><tr><th>Part ID</th><th>Name</th><th>Color</th><th>Total Quantity</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(f"<td><a href='/parts/{html.escape(r['design_id'])}'>{html.escape(r['design_id'])}</a></td>")
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(_make_color_cell(r["color_name"], r["hex"]))
            body.append(f"<td>{r['total_qty']:,}</td>")
            body.append("</tr>")
        body.append("</tbody>")
        body.append(f"<tfoot><tr><th colspan='3'>Total</th><th>{total_qty:,}</th></tr></tfoot>")
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