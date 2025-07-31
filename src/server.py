"""
Light-weight HTTP UI for the Lego inventory database (inventory_db.py).

* “/”              – master table (one row per part + colour + status + location)
* “/parts/<id>”    – detail page for a single part
* “/locations”     – loose-parts hierarchy  (drawer ▸ container ▸ parts)
* “/sets”          – set-parts  hierarchy   (set-number ▸ parts)

No external dependencies – just the std-lib.
Run with:  python -m http.server 8000 --bind 127.0.0.1 (or simply `python server.py`)
"""
from __future__ import annotations

import html
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- local import
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))  # ensure we can import inventory_db
import inventory_db as db  # noqa: E402

SET_STATUSES = {"built", "wip", "in_box", "teardown"}


# --------------------------------------------------------------------------- helpers
def _html_page(title: str, body_html: str) -> str:
    """Very small HTML skeleton."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
 body {{ font-family: sans-serif; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #ccc; padding: 2px 6px; }}
 th {{ background: #eee; text-align: left; }}
 a {{ text-decoration: none; color: #0645ad; }}
 tr:hover {{ background: #ffffe0; }}
</style>
</head><body>
<nav>
  <a href="/">Parts</a> |
  <a href="/locations">Locations</a> |
  <a href="/sets">Sets</a>
</nav>
<hr>
{body_html}
</body></html>"""


def _make_colour_cell(name: str, hex_code: str) -> str:
    fg = "#000" if sum(int(hex_code[i : i + 2], 16) for i in (0, 2, 4)) > 382 else "#fff"
    return f'<td style="background: #{hex_code}; color:{fg}">{html.escape(name)}</td>'


def _query_master_rows() -> List[Dict]:
    """
    Return aggregated rows:
    design_id, part_name, colour_name, hex, status, location (drawer/container OR set_number), qty
    """
    with db._connect() as conn:  # pylint: disable=protected-access
        rows = conn.execute(
            """
            SELECT  i.design_id,
                    p.name            AS part_name,
                    c.name            AS colour_name,
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
                colour_name=r["colour_name"],
                hex=r["hex"],
                status=r["status"],
                location=location,
                qty=r["qty"],
            )
        )
    return result


def _build_sets_map() -> Dict[str, List[Dict]]:
    """
    {set_number: [{design_id, part_name, colour_name, hex, qty}, …]}
    Only parts whose status is in SET_STATUSES.
    """
    with db._connect() as conn:  # pylint: disable=protected-access
        rows = conn.execute(
            f"""
            SELECT i.set_number,
                   i.design_id,
                   p.name  AS part_name,
                   c.name  AS colour_name,
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
                colour_name=r["colour_name"],
                hex=r["hex"],
                qty=r["qty"],
            )
        )
    return sets


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
            else:
                self._not_found()
        except Exception as exc:  # pylint: disable=broad-except
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Internal error:\n{exc}".encode())

    # ..................................................................... pages
    def _serve_master(self):
        rows = _query_master_rows()
        body = ["<h1>Inventory – Parts view</h1>", "<table><thead><tr>",
                "<th>ID</th><th>Name</th><th>Colour</th><th>Status</th>",
                "<th>Location</th><th>Qty</th></tr></thead><tbody>"]
        for r in rows:
            body.append("<tr>")
            body.append(
                f"<td><a href='/parts/{r['design_id']}'>{html.escape(r['design_id'])}</a></td>"
            )
            body.append(f"<td>{html.escape(r['part_name'])}</td>")
            body.append(_make_colour_cell(r["colour_name"], r["hex"]))
            body.append(f"<td>{html.escape(r['status'])}</td>")
            body.append(f"<td>{html.escape(r['location'])}</td>")
            body.append(f"<td>{r['qty']}</td>")
            body.append("</tr>")
        body.append("</tbody></table>")
        self._send_ok(_html_page("Inventory – Parts", "".join(body)))

    def _serve_part(self, design_id: str):
        part = db.get_part(design_id)
        if not part:
            self._not_found()
            return
        rows = db.inventory_by_part(design_id)
        body = [f"<h1>Part {html.escape(design_id)}</h1>",
                f"<p>Name: {html.escape(part['name'])}</p>",
                "<table><thead><tr><th>Colour</th><th>Status</th>"
                "<th>Location</th><th>Qty</th></tr></thead><tbody>"]
        for r in rows:
            if r["status"] in SET_STATUSES:
                loc = r["set_number"] or "(unknown set)"
            else:
                loc = f"{r['drawer']}/{r['container']}".strip("/")
            body.append("<tr>")
            body.append(_make_colour_cell(r["color_name"], r["hex"]))
            body.append(f"<td>{html.escape(r['status'])}</td>")
            body.append(f"<td>{html.escape(loc)}</td>")
            body.append(f"<td>{r['quantity']}</td>")
            body.append("</tr>")
        body.append("</tbody></table>")
        self._send_ok(_html_page(f"Part {design_id}", "".join(body)))

    def _serve_locations(self):
        tree = db.locations_map()
        body = ["<h1>Loose-parts locations</h1>"]
        for (drawer, container), parts in tree.items():
            body.append(f"<h2>Drawer {html.escape(drawer)} / {html.escape(container)}</h2>")
            body.append("<table><thead><tr><th>ID</th><th>Name</th>"
                        "<th>Colour</th><th>Qty</th></tr></thead><tbody>")
            for p in parts:
                body.append("<tr>")
                body.append(
                    f"<td><a href='/parts/{p['design_id']}'>{html.escape(p['design_id'])}</a></td>"
                )
                body.append(f"<td>{html.escape(p['name'])}</td>")
                body.append(_make_colour_cell(p["color_name"], p["hex"]))
                body.append(f"<td>{p['qty']}</td></tr>")
            body.append("</tbody></table>")
        self._send_ok(_html_page("Locations", "".join(body)))

    def _serve_sets(self):
        sets = _build_sets_map()
        body = ["<h1>Set inventory</h1>"]
        for set_no, parts in sets.items():
            body.append(f"<h2>Set {html.escape(set_no)}</h2>")
            body.append("<table><thead><tr><th>ID</th><th>Name</th>"
                        "<th>Colour</th><th>Qty</th></tr></thead><tbody>")
            for p in parts:
                body.append("<tr>")
                body.append(
                    f"<td><a href='/parts/{p['design_id']}'>{html.escape(p['design_id'])}</a></td>"
                )
                body.append(f"<td>{html.escape(p['part_name'])}</td>")
                body.append(_make_colour_cell(p["colour_name"], p["hex"]))
                body.append(f"<td>{p['qty']}</td></tr>")
            body.append("</tbody></table>")
        self._send_ok(_html_page("Sets", "".join(body)))

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
    host, port = "127.0.0.1", int(os.environ.get("PORT", 8000))
    httpd = HTTPServer((host, port), Handler)
    print(f"Serving on http://{host}:{port}  – Ctrl+C to quit")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…")


if __name__ == "__main__":
    main()