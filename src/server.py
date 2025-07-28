"""Minimal HTTP server for the LEGO inventory system.

This script uses Python's built-in ``http.server`` module to serve a
web interface for the LEGO inventory database. It requires no
third-party dependencies. To run the server, execute ``python3
lego_inventory/server.py`` and open ``http://localhost:8000`` in your
browser.

Routes
------

* ``/`` or ``/parts`` – list all parts with their total quantities
* ``/parts/<id>`` – detailed view of a single part
* ``/locations`` – list all storage locations with the parts stored there
* ``/search?q=...`` – search for parts by number or name
* ``/static/styles.css`` – serve the stylesheet

Any other URL returns a 404 page. Error handling is basic; if the
database file is missing it will be created automatically. All pages
share a consistent layout defined in the helper methods.
"""

from __future__ import annotations

import os
import posixpath
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional

from . import inventory_db as db


class InventoryRequestHandler(BaseHTTPRequestHandler):
    """Request handler for the inventory web interface."""

    def do_GET(self) -> None:
        """Handle a GET request."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if path in ("/", "/parts", ""):
            self.handle_parts_list(query_params)
        elif path.startswith("/parts/"):
            part_id_str = path[len("/parts/"):]
            if part_id_str.isdigit():
                self.handle_part_detail(int(part_id_str))
            else:
                self.send_error_page(404)
        elif path == "/locations":
            self.handle_locations()
        elif path == "/search":
            q = query_params.get("q", [""])[0]
            self.handle_search(q)
        elif path.startswith("/static/"):
            self.handle_static(path)
        else:
            self.send_error_page(404)

    # ------------------------------------------------------------------
    # Route handlers
    #
    def handle_parts_list(self, params: Dict[str, List[str]]) -> None:
        parts = db.get_parts_with_totals()
        html = self.render_parts_list(parts)
        self.respond(html)

    def handle_part_detail(self, part_id: int) -> None:
        part = db.get_part(part_id)
        if not part:
            self.send_error_page(404)
            return
        records = db.get_inventory_records_by_part(part_id)
        html = self.render_part_detail(part, records)
        self.respond(html)

    def handle_locations(self) -> None:
        locations_map = db.get_locations_map()
        html = self.render_locations(locations_map)
        self.respond(html)

    def handle_search(self, query: str) -> None:
        query = query.strip()
        if not query:
            # Redirect to home page
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        parts = db.search_parts(query)
        html = self.render_parts_list(parts, query=query)
        self.respond(html)

    def handle_static(self, path: str) -> None:
        """Serve static files (currently only the CSS)."""
        # Only allow serving the specific stylesheet
        if path == "/static/styles.css":
            css_path = os.path.join(os.path.dirname(__file__), "static", "styles.css")
            if os.path.isfile(css_path):
                with open(css_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/css")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        # Fallback 404
        self.send_error_page(404)

    # ------------------------------------------------------------------
    # HTML rendering helpers
    #
    def render_layout(self, title: str, content: str, query: Optional[str] = None) -> str:
        """Return a complete HTML page with navigation and provided content."""
        # Escape query for input value
        query_attr = urllib.parse.quote(query or "", safe="")
        return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="stylesheet" href="/static/styles.css">
  </head>
  <body>
    <header>
      <nav class="navbar">
        <div class="nav-wrapper">
          <a href="/" class="brand">LEGO Inventory</a>
          <ul class="nav-links">
            <li><a href="/">Parts</a></li>
            <li><a href="/locations">Locations</a></li>
            <li>
              <form action="/search" method="get" class="search-form">
                <input type="text" name="q" value="{query_attr}" placeholder="Search part number or name" required>
                <button type="submit">Search</button>
              </form>
            </li>
          </ul>
        </div>
      </nav>
    </header>
    <main class="container">
      {content}
    </main>
  </body>
</html>
"""

    def render_parts_list(self, parts: List[Dict], query: Optional[str] = None) -> str:
        """Render the parts list page."""
        heading = "Search results" if query else "Parts"
        message = f"Showing results for query \"{query}\"." if query else ""
        rows_html = ""
        for part in parts:
            rows_html += f"<tr><td><a href='/parts/{part['id']}'>{part['part_number']}</a></td><td>{part['name']}</td><td>{part['total_quantity']}</td></tr>\n"
        table_html = (
            "<p>No parts found.</p>" if not parts else
            f"""
            <table>
              <thead>
                <tr><th>Part Number</th><th>Name</th><th>Total Quantity</th></tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
            """
        )
        content = f"<h1>{heading}</h1>" + (f"<p class='message'>{message}</p>" if message else "") + table_html
        return self.render_layout(f"{heading} - LEGO Inventory", content, query=query)

    def render_part_detail(self, part: Dict, records: List[Dict]) -> str:
        """Render the part detail page."""
        rows_html = ""
        for rec in records:
            status_display = rec['status'].replace('_', ' ').title()
            location_parts = []
            if rec['container']:
                location_parts.append(f"Container {rec['container']}")
            if rec['drawer']:
                location_parts.append(f"Drawer {rec['drawer']}")
            if rec['bin']:
                location_parts.append(f"Bin {rec['bin']}")
            location_str = ' - '.join(location_parts) if location_parts else 'N/A'
            rows_html += f"<tr><td>{rec['colour']}</td><td>{rec['quantity']}</td><td>{status_display}</td><td>{location_str}</td></tr>\n"
        table_html = (
            "<p>No inventory records found for this part.</p>" if not records else
            f"""
            <table>
              <thead>
                <tr><th>Colour</th><th>Quantity</th><th>Status</th><th>Location</th></tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
            """
        )
        content = f"<h1>Part {part['part_number']}</h1><p>Name: <strong>{part['name']}</strong></p><a href='/'>← Back to parts list</a>" + table_html
        return self.render_layout(f"{part['part_number']} - LEGO Inventory", content)

    def render_locations(self, locations_map: Dict) -> str:
        """Render the locations page."""
        sections = []
        if not locations_map:
            sections.append("<p>No locations with inventory records.</p>")
        else:
            for (container, drawer, bin_name), records in locations_map.items():
                loc_parts = []
                if container:
                    loc_parts.append(f"Container {container}")
                if drawer:
                    loc_parts.append(f"Drawer {drawer}")
                if bin_name:
                    loc_parts.append(f"Bin {bin_name}")
                header = ' - '.join(loc_parts) if loc_parts else 'No specified location'
                # Build table rows
                rows_html = ""
                for rec in records:
                    rows_html += f"<tr><td><a href='/parts/{rec['part_id']}'>{rec['part_number']}</a></td><td>{rec['name']}</td><td>{rec['colour']}</td><td>{rec['quantity']}</td></tr>\n"
                table_html = f"""
                <table>
                  <thead>
                    <tr><th>Part Number</th><th>Name</th><th>Colour</th><th>Quantity</th></tr>
                  </thead>
                  <tbody>
                    {rows_html}
                  </tbody>
                </table>
                """
                sections.append(f"<div class='location-header'>{header}</div>{table_html}")
        content = "<h1>Locations</h1>" + "".join(sections)
        return self.render_layout("Locations - LEGO Inventory", content)

    def send_error_page(self, code: int) -> None:
        """Send a simple HTML error page."""
        title = "Not Found" if code == 404 else "Error"
        content = f"<h1>{title}</h1><p>The requested resource could not be found.</p>"
        html = self.render_layout(f"{title} - LEGO Inventory", content)
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def respond(self, html: str) -> None:
        """Send an HTML response."""
        data = html.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the HTTP server."""
    db.init_db()
    with HTTPServer((host, port), InventoryRequestHandler) as httpd:
        print(f"Serving on http://{host}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")


if __name__ == "__main__":
    run()