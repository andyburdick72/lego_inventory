"""
Light-weight HTTP UI for the Lego inventory database (inventory_db.py).

* “/”               – master table (one row per part + color + status + location)
* “/parts/<id>”     – detail page for a single part
* “/locations”      – loose-parts hierarchy  (drawer ▸ container ▸ parts)
* “/sets/<set_num>” – detail page for a single set and its parts
* “/my-sets”        – list of all sets

No external dependencies – just the std-lib.

Usage:
    python3 src/server.py
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
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from pathlib import Path as _Path
from urllib.parse import parse_qs, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore

# Ensure repo root is on sys.path when running as `python3 src/app/server.py`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

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


# Safely embed Python strings inside inline JS (produces a quoted JSON string)
def _js_str(s: str | None) -> str:
    return json.dumps(s or "")


from infra.db import inventory_db as db  # noqa: E402
from infra.db.inventory_db import get_set  # noqa: E402

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
    # The main HTML skeleton. We'll inject JS helpers before </script> below.
    html_str = f"""<!doctype html>
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
  /* Inline modal */
  #lego-modal {{ display:none; position:fixed; inset:0; background: rgba(0,0,0,.4); align-items:center; justify-content:center; z-index: 9999; }}
  #lego-modal .panel {{ background:#fff; padding:1rem; width:min(420px, 90vw); border-radius:8px; box-shadow:0 10px 30px rgba(0,0,0,.2); }}
  #lego-modal .panel h3 {{ margin: 0 0 .75rem 0; }}
  #lego-modal .panel .actions {{ margin-top: .75rem; display:flex; gap:.5rem; justify-content:flex-end; }}
  #lego-modal .panel input {{ box-sizing: border-box; width: 100%; }}
  #lego-modal .panel select {{ box-sizing: border-box; width: 100%; }}
  #lego-modal .panel .msg {{ margin: .25rem 0 .5rem 0; color: #333; }}
  #lego-modal .panel #lego-modal-form {{ margin: .25rem 0 .5rem 0; }}
  #lego-modal .panel #lego-modal-form input {{ width: 100%; box-sizing: border-box; }}
  #lego-modal .panel #lego-modal-form .row {{ display:flex; gap:.5rem; }}
  #lego-modal .panel #lego-modal-form .row > div {{ flex:1; }}
  .hidden {{ display: none; }}
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
<div id="lego-modal" role="dialog" aria-modal="true" aria-labelledby="lego-modal-title">
  <div class="panel">
    <h3 id="lego-modal-title">Rename</h3>
    <div id="lego-modal-msg" class="msg hidden"></div>
    <div id="lego-modal-form" class="hidden"></div>
    <input id="lego-modal-input" type="text" style="width:100%; padding:.5rem;" />
    <select id="lego-modal-select" class="hidden" style="width:100%; padding:.5rem;"></select>
    <div class="actions">
      <button type="button" id="lego-modal-cancel">Cancel</button>
      <button type="button" id="lego-modal-ok">OK</button>
    </div>
  </div>
</div>
<script>
  $(document).ready(function () {{
    $("table").each(function () {{
      var $table = $(this);
      var table = $table.DataTable({{
        pageLength: 50,
        order: [],
        paging: true,
        language: {{
          search: "Search all columns:",
          zeroRecords: "No matching parts found"
        }},
        initComplete: function () {{
          var api = this.api();
          api.columns().every(function (index) {{
            var column = this;
            var th = $(column.header());
            var title = th.text();
            th.empty().append('<div style="margin-bottom: 6px;">' + title + '</div>');
            if (title !== "Qty" && title !== "Total Quantity" && title !== "Quantity" && title !== "Image" && title !== "Rebrickable Link" && title !== "Unique Parts" && title !== "Total Pieces" && title !== "Containers") {{
              $('<input type="text" placeholder="Search…" style="width:100%; margin-top: 6px;" />')
                .appendTo(th)
                .on('keyup change clear', function () {{
                  if (column.search() !== this.value) {{
                    column.search(this.value).draw();
                  }}
                }});
            }}
          }});

          // Add Export CSV button next to the search box
          var btn = $('<button type="button" class="export-csv" style="margin: 8px 8px 8px 0;">Export CSV</button>');
          var wrapper = $table.closest('.dataTables_wrapper');
          var filter = wrapper.find('.dataTables_filter');
          if (filter.length) {{
            filter.prepend(btn);
          }} else {{
            $table.before(btn);
          }}

          btn.on('click', function () {{
            var dt = $table.DataTable();
            // Build DataTables state payload
            var columns = dt.settings()[0].aoColumns.map(function (col) {{
              var idx = col.idx;
              return {{
                data: col.mData || col.sName || col.sTitle || idx,
                name: col.sName || null,
                search: {{ value: dt.column(idx).search() || "" }}
              }};
            }});
            var order = (dt.order() || []).map(function (pair) {{
              return {{ column: pair[0], dir: pair[1] }};
            }});
            var state = {{ columns: columns, search: {{ value: dt.search() || "" }}, order: order }};

            var tableKey = $table.attr("data-tablekey") || "";
            var contextJson = $table.attr("data-context") || "{{}}";

            var url = new URL('/export', window.location.origin);
            url.searchParams.set('table', tableKey);
            url.searchParams.set('dt', JSON.stringify(state));
            url.searchParams.set('ctx', contextJson);
            window.location.href = url.toString();
          }});
        }}
      }});
    }});
  }});
  // ---- Diagnostics + delegated handlers
  console.log("[lego] script loaded");

  // jQuery delegation as a backup (coexists with vanilla)
  $(document).on('click', 'button[data-action]', function (e) {{
    const $btn = $(this);
    const action = $btn.data('action');
    const id = parseInt($btn.data('id') || 0, 10) || 0;
    const name = $btn.data('name') || '';
    const drawerId = parseInt($btn.data('drawer-id') || 0, 10) || 0;
    console.log('[lego][jquery] click', {{ action, id, name, drawerId }});
    switch (action) {{
      case 'create-drawer': return createDrawer();
      case 'rename-drawer': return renameDrawer(id, name, $btn.data('desc') || '', parseInt($btn.data('cols') || 0, 10) || '', parseInt($btn.data('rows') || 0, 10) || '');
      case 'delete-drawer': return deleteDrawer(id);
      case 'restore-drawer': return restoreDrawer(id);
      case 'add-container': return addContainer(drawerId);
      case 'rename-container': return renameContainer(id, name, $btn.data('desc') || '', parseInt($btn.data('row') || 0, 10) || '', parseInt($btn.data('col') || 0, 10) || '');
      case 'move-container': return moveContainer(id);
      case 'delete-container': return deleteContainer(id, drawerId);
      case 'restore-container': return restoreContainer(id);
    }}
  }});

  // Existing vanilla delegation (kept)
  document.addEventListener('click', function (e) {{
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const action = btn.getAttribute('data-action');
    const id = parseInt(btn.getAttribute('data-id') || '0', 10) || 0;
    const name = btn.getAttribute('data-name') || '';
    const drawerId = parseInt(btn.getAttribute('data-drawer-id') || '0', 10) || 0;
    console.log('[lego][vanilla] click', {{ action, id, name, drawerId }});
    switch (action) {{
      case 'create-drawer': return createDrawer();
      case 'rename-drawer': return renameDrawer(id, name, btn.getAttribute('data-desc') || '', parseInt(btn.getAttribute('data-cols') || '0', 10) || '', parseInt(btn.getAttribute('data-rows') || '0', 10) || '');
      case 'delete-drawer': return deleteDrawer(id);
      case 'restore-drawer': return restoreDrawer(id);
      case 'add-container': return addContainer(drawerId);
      case 'rename-container': return renameContainer(id, name, btn.getAttribute('data-desc') || '', parseInt(btn.getAttribute('data-row') || '0', 10) || '', parseInt(btn.getAttribute('data-col') || '0', 10) || '');
      case 'move-container': return moveContainer(id);
      case 'delete-container': return deleteContainer(id, drawerId);
      case 'restore-container': return restoreContainer(id);
    }}
  }});
  // ---- API + UI helpers (CRUD for drawers/containers)
  async function api(method, path, body) {{
    const res = await fetch(path, {{
      method,
      headers: {{ 'Content-Type': 'application/json' }},
      body: body ? JSON.stringify(body) : undefined
    }});
    let json = null;
    try {{ json = await res.json(); }} catch (_) {{}}
    return {{ ok: res.ok, status: res.status, json }};
  }}
  function toast(msg) {{ alert(msg); }}

  // Drawers
    async function createDrawer() {{
    const name = (document.getElementById('new-drawer-name')||{{}}).value?.trim();
    const desc = (document.getElementById('new-drawer-desc')||{{}}).value?.trim() || '';
    const cols = parseInt((document.getElementById('new-drawer-cols')||{{}}).value || '0', 10) || null;
    const rows = parseInt((document.getElementById('new-drawer-rows')||{{}}).value || '0', 10) || null;
    if (!name) {{ toast('Please enter a drawer name.'); return; }}
    const r = await api('POST', '/api/drawers', {{ name, description: desc, cols, rows }});
    if (r.ok) {{ location.reload(); }} else {{ toast(r.json?.error || 'Failed to create drawer'); }}
  }}

  async function renameDrawer(id, currentName, currentDesc, currentCols, currentRows) {{
    openEditDrawerModal(id, {{ name: currentName, desc: currentDesc, cols: currentCols, rows: currentRows }});
  }}

  async function deleteDrawer(id) {{
    openConfirmModal('Delete Drawer', 'Soft delete this drawer? (must be empty)', async () => {{
      const r = await api('DELETE', `/api/drawers/${{id}}`);
      if (r.ok) {{ location.href = '/drawers'; }}
      else if (r.status === 409) {{ toast(r.json?.error || 'Drawer not empty'); }}
      else {{ toast(r.json?.error || 'Failed to delete drawer'); }}
    }});
  }}
  async function restoreDrawer(id) {{
    const r = await api('POST', `/api/drawers/${{id}}/restore`);
    if (r.ok) {{ location.reload(); }} else {{ toast(r.json?.error || 'Failed to restore drawer'); }}
  }}

  // Containers
  async function addContainer(drawerId) {{
    const name = (document.getElementById('new-container-name')||{{}}).value?.trim();
    const row_index = (document.getElementById('new-container-row')||{{}}).value;
    const col_index = (document.getElementById('new-container-col')||{{}}).value;
    const description = (document.getElementById('new-container-desc')||{{}}).value;
    if (!name) {{ toast('Please enter a container label.'); return; }}
    const payload = {{ drawer_id: drawerId, name }};
    if (row_index !== undefined && row_index !== '') payload.row_index = parseInt(row_index, 10);
    if (col_index !== undefined && col_index !== '') payload.col_index = parseInt(col_index, 10);
    if (description) payload.description = description;
    const r = await api('POST', '/api/containers', payload);
    if (r.ok) {{ location.reload(); }}
    else if (r.status === 409) {{ toast('Duplicate label in this drawer'); }}
    else {{ toast(r.json?.error || 'Failed to add container'); }}
  }}

  async function renameContainer(id, currentName, currentDesc, currentRow, currentCol) {{
    openEditContainerModal(id, {{ name: currentName, desc: currentDesc, row: currentRow, col: currentCol }});
  }}

  // ---- Generic modals ----
  function openTextModal(title, initial, onOk) {{
    const modal = document.getElementById('lego-modal');
    document.getElementById('lego-modal-title').textContent = title;
    const input = document.getElementById('lego-modal-input');
    const msgDiv = document.getElementById('lego-modal-msg');
    input.value = initial || '';
    if (msgDiv) {{ msgDiv.textContent = ''; msgDiv.classList.add('hidden'); }}
    modal.style.display = 'flex';
    setTimeout(() => input.focus(), 0);
    function cleanup() {{
      modal.style.display = 'none';
      okBtn.removeEventListener('click', okHandler);
      cancelBtn.removeEventListener('click', cancelHandler);
      input.removeEventListener('keydown', keyHandler);
      modal.removeEventListener('click', backdropHandler);
    }}
    const okBtn = document.getElementById('lego-modal-ok');
    const cancelBtn = document.getElementById('lego-modal-cancel');
    async function okHandler() {{
      const value = (input.value || '').trim();
      if (!value) {{
        if (msgDiv) {{ msgDiv.textContent = 'Please enter a value'; msgDiv.classList.remove('hidden'); }}
        input.focus();
        return;
      }}
      cleanup();
      await onOk(value);
    }}
    function cancelHandler() {{ cleanup(); }}
    function keyHandler(e) {{
      if (e.key === 'Escape') return cancelHandler();
      if (e.key === 'Enter') {{
        e.preventDefault();
        okHandler();
      }}
    }}
    function backdropHandler(e) {{
      if (e.target === modal) cancelHandler();
    }}
    okBtn.addEventListener('click', okHandler);
    cancelBtn.addEventListener('click', cancelHandler);
    input.addEventListener('keydown', keyHandler);
    modal.addEventListener('click', backdropHandler);
  }}

  function openConfirmModal(title, msg, onOk) {{
    const modal = document.getElementById('lego-modal');
    document.getElementById('lego-modal-title').textContent = title;
    const input = document.getElementById('lego-modal-input');
    const msgDiv = document.getElementById('lego-modal-msg');
    input.style.display = 'none';
    if (msgDiv) {{ msgDiv.textContent = msg; msgDiv.classList.remove('hidden'); }}
    modal.style.display = 'flex';
    function cleanup() {{
      modal.style.display = 'none';
      okBtn.removeEventListener('click', okHandler);
      cancelBtn.removeEventListener('click', cancelHandler);
      modal.removeEventListener('click', backdropHandler);
      input.style.display = '';
    }}
    const okBtn = document.getElementById('lego-modal-ok');
    const cancelBtn = document.getElementById('lego-modal-cancel');
    async function okHandler() {{
      cleanup();
      await onOk();
    }}
    function cancelHandler() {{ cleanup(); }}
    function backdropHandler(e) {{
      if (e.target === modal) cancelHandler();
    }}
    okBtn.addEventListener('click', okHandler);
    cancelBtn.addEventListener('click', cancelHandler);
    modal.addEventListener('click', backdropHandler);
  }}

  function openFormModal(title, formHTML, onOk, collect) {{
    const modal = document.getElementById('lego-modal');
    document.getElementById('lego-modal-title').textContent = title;
    const msgDiv = document.getElementById('lego-modal-msg');
    const input = document.getElementById('lego-modal-input');
    const selectEl = document.getElementById('lego-modal-select');
    const formDiv = document.getElementById('lego-modal-form');
    // Hide text/select; show form
    input.classList.add('hidden');
    selectEl.classList.add('hidden');
    if (msgDiv) {{ msgDiv.textContent = ''; msgDiv.classList.add('hidden'); }}
    formDiv.classList.remove('hidden');
    formDiv.innerHTML = formHTML;
    modal.style.display = 'flex';
    setTimeout(() => {{ const f = formDiv.querySelector('input,select,textarea'); if (f) f.focus(); }}, 0);

    function cleanup() {{
      modal.style.display = 'none';
      okBtn.removeEventListener('click', okHandler);
      cancelBtn.removeEventListener('click', cancelHandler);
      modal.removeEventListener('click', backdropHandler);
      formDiv.classList.add('hidden');
      input.classList.remove('hidden');
    }}
    const okBtn = document.getElementById('lego-modal-ok');
    const cancelBtn = document.getElementById('lego-modal-cancel');
    async function okHandler() {{
      try {{
        const values = typeof collect === 'function' ? collect(formDiv) : null;
        cleanup();
        await onOk(values);
      }} catch (e) {{
        cleanup();
        toast('Invalid input');
      }}
    }}
    function cancelHandler() {{ cleanup(); }}
    function backdropHandler(e) {{ if (e.target === modal) cancelHandler(); }}
    okBtn.addEventListener('click', okHandler);
    cancelBtn.addEventListener('click', cancelHandler);
    modal.addEventListener('click', backdropHandler);
  }}

  function openEditDrawerModal(id, current) {{
    const form = `
      <div class="row">
        <div><label>Name<br><input id="f-name" value="${{current.name || ''}}" /></label></div>
      </div>
      <div><label>Description<br><input id="f-desc" value="${{current.desc || ''}}" /></label></div>
      <div class="row">
        <div><label>Cols<br><input id="f-cols" type="number" min="0" value="${{current.cols || ''}}" /></label></div>
        <div><label>Rows<br><input id="f-rows" type="number" min="0" value="${{current.rows || ''}}" /></label></div>
      </div>`;
    openFormModal('Edit Drawer', form, async (vals) => {{
      const payload = {{ name: vals.name.trim() }};
      if (vals.desc !== undefined) payload.description = vals.desc.trim();
      if (vals.cols !== undefined && vals.cols !== '') payload.cols = parseInt(vals.cols, 10);
      if (vals.rows !== undefined && vals.rows !== '') payload.rows = parseInt(vals.rows, 10);
      const r = await api('PUT', `/api/drawers/${{id}}`, payload);
      if (r.ok) {{ location.reload(); }} else {{ toast(r.json?.error || 'Failed to update drawer'); }}
    }}, function (formDiv) {{
      return {{
        name: formDiv.querySelector('#f-name').value,
        desc: formDiv.querySelector('#f-desc').value,
        rows: formDiv.querySelector('#f-rows').value,
        cols: formDiv.querySelector('#f-cols').value,
      }};
    }});
  }}

  function openEditContainerModal(id, current) {{
    const form = `
      <div class="row">
        <div><label>Label<br><input id="f-name" value="${{current.name || ''}}" /></label></div>
      </div>
      <div><label>Description<br><input id="f-desc" value="${{current.desc || ''}}" /></label></div>
      <div class="row">
        <div><label>Row<br><input id="f-row" type="number" value="${{current.row || ''}}" /></label></div>
        <div><label>Col<br><input id="f-col" type="number" value="${{current.col || ''}}" /></label></div>
      </div>`;
    openFormModal('Edit Container', form, async (vals) => {{
      const payload = {{ name: vals.name.trim() }};
      if (vals.desc !== undefined) payload.description = vals.desc.trim();
      if (vals.row !== undefined && vals.row !== '') payload.row_index = parseInt(vals.row, 10);
      if (vals.col !== undefined && vals.col !== '') payload.col_index = parseInt(vals.col, 10);
      const r = await api('PUT', `/api/containers/${{id}}`, payload);
      if (r.ok) {{ location.reload(); }}
      else if (r.status === 409) {{ toast('Duplicate label in this drawer'); }}
      else {{ toast(r.json?.error || 'Failed to update container'); }}
    }}, function (formDiv) {{
      return {{
        name: formDiv.querySelector('#f-name').value,
        desc: formDiv.querySelector('#f-desc').value,
        row: formDiv.querySelector('#f-row').value,
        col: formDiv.querySelector('#f-col').value,
      }};
    }});
  }}

  function openSelectModal(title, options, onOk) {{
    const modal = document.getElementById('lego-modal');
    const titleEl = document.getElementById('lego-modal-title');
    const input = document.getElementById('lego-modal-input');
    const selectEl = document.getElementById('lego-modal-select');
    const msgDiv = document.getElementById('lego-modal-msg');
    titleEl.textContent = title;
    // prepare UI
    input.classList.add('hidden');
    if (msgDiv) {{ msgDiv.textContent = ''; msgDiv.classList.add('hidden'); }}
    selectEl.classList.remove('hidden');
    // populate options
    selectEl.innerHTML = '';
    (options || []).forEach(function (opt) {{
      const o = document.createElement('option');
      o.value = String(opt.value);
      o.textContent = opt.label;
      selectEl.appendChild(o);
    }});
    modal.style.display = 'flex';
    setTimeout(() => selectEl.focus(), 0);

    function cleanup() {{
      modal.style.display = 'none';
      okBtn.removeEventListener('click', okHandler);
      cancelBtn.removeEventListener('click', cancelHandler);
      modal.removeEventListener('click', backdropHandler);
      selectEl.classList.add('hidden');
      input.classList.remove('hidden');
    }}
    const okBtn = document.getElementById('lego-modal-ok');
    const cancelBtn = document.getElementById('lego-modal-cancel');
    async function okHandler() {{
      const val = parseInt(selectEl.value || '0', 10);
      if (!val) {{ toast('Please choose an option'); return; }}
      cleanup();
      await onOk(val);
    }}
    function cancelHandler() {{ cleanup(); }}
    function backdropHandler(e) {{ if (e.target === modal) cancelHandler(); }}

    okBtn.addEventListener('click', okHandler);
    cancelBtn.addEventListener('click', cancelHandler);
    modal.addEventListener('click', backdropHandler);
  }}

  async function openSelectDrawerModal(onOk) {{
    try {{
      const r = await api('GET', '/api/drawers');
      if (!r.ok) {{ return toast(r.json?.error || 'Failed to load drawers'); }}
      const options = (r.json || []).map(function (d) {{
        const name = (d.name || '').toString();
        const containers = d.container_count || 0;
        const label = containers ? `${{name}} (containers: ${{containers}})` : name;
        return {{ value: d.id, label }};
      }});
      if (!options.length) {{ return toast('No drawers available'); }}
      openSelectModal('Move Container – Choose Drawer', options, onOk);
    }} catch (e) {{
      toast('Failed to load drawers');
    }}
  }}

  async function openSelectContainerInDrawer(drawerId, onOk) {{
    try {{
      const r = await api('GET', `/api/containers?drawer_id=${{drawerId}}`);
      if (!r.ok) {{ return toast(r.json?.error || 'Failed to load containers'); }}
      const options = (r.json || []).map(function (c) {{
        const name = (c.name || '').toString();
        const parts = c.part_count || 0;
        const label = parts ? `${{name}} (id: ${{c.id}}, parts: ${{parts}})` : `${{name}} (id: ${{c.id}})`;
        return {{ value: c.id, label }};
      }});
      if (!options.length) {{ return toast('No containers in that drawer'); }}
      openSelectModal('Merge/Move Inventory – Choose Target Container', options, onOk);
    }} catch (e) {{
      toast('Failed to load containers');
    }}
  }}  

  async function moveContainer(id) {{
    openSelectDrawerModal(async (drawerId) => {{
      const r = await api('PUT', `/api/containers/${{id}}`, {{ drawer_id: drawerId }});
      if (r.ok) {{ location.reload(); }}
      else if (r.status === 409) {{ toast('Duplicate label in the target drawer'); }}
      else {{ toast(r.json?.error || 'Failed to move container'); }}
    }});
  }}

  async function deleteContainer(id, drawerId) {{
    // Pre-check: ask the server if merge/move is required without mutating
    const pre = await api('DELETE', `/api/containers/${{id}}?check=1`);
    if (pre.status === 409 && (pre.json?.needed === 'merge_move')) {{
      // If we know the current drawer, go straight to container selection in that drawer; otherwise pick drawer first
      if (drawerId) {{
        openSelectContainerInDrawer(drawerId, async (target) => {{
          const m = await api('POST', `/api/containers/${{id}}/merge_move`, {{ target_container_id: target }});
          if (m.ok) {{ location.href = '/drawers'; }} else {{ toast(m.json?.error || 'Merge/move failed'); }}
        }});
      }} else {{
        openSelectDrawerModal(async (did) => {{
          openSelectContainerInDrawer(did, async (target) => {{
            const m = await api('POST', `/api/containers/${{id}}/merge_move`, {{ target_container_id: target }});
            if (m.ok) {{ location.href = '/drawers'; }} else {{ toast(m.json?.error || 'Merge/move failed'); }}
          }});
        }});
      }}
      return;
    }}

    if (pre.ok || pre.status === 204) {{
      // No inventory: ask for confirmation, then perform the actual delete
      openConfirmModal('Delete Container', 'Soft delete this container?', async () => {{
        const r = await api('DELETE', `/api/containers/${{id}}`);
        if (r.ok) {{ location.href = '/drawers'; }}
        else if (r.status === 409 && (r.json?.needed === 'merge_move')) {{
          // Race condition: inventory appeared; fall back to the picker flow
          if (drawerId) {{
            openSelectContainerInDrawer(drawerId, async (target) => {{
              const m = await api('POST', `/api/containers/${{id}}/merge_move`, {{ target_container_id: target }});
              if (m.ok) {{ location.href = '/drawers'; }} else {{ toast(m.json?.error || 'Merge/move failed'); }}
            }});
          }} else {{
            openSelectDrawerModal(async (did) => {{
              openSelectContainerInDrawer(did, async (target) => {{
                const m = await api('POST', `/api/containers/${{id}}/merge_move`, {{ target_container_id: target }});
                if (m.ok) {{ location.href = '/drawers'; }} else {{ toast(m.json?.error || 'Merge/move failed'); }}
              }});
            }});
          }}
        }} else {{
          toast(r.json?.error || 'Failed to delete container');
        }}
      }});
    }} else {{
      toast(pre.json?.error || 'Failed to check delete');
    }}
  }}

  async function restoreContainer(id) {{
    const r = await api('POST', `/api/containers/${{id}}/restore`);
    if (r.ok) {{ location.reload(); }} else {{ toast(r.json?.error || 'Failed to restore container'); }}
  }}

  // Expose helpers globally for inline onclick
  window.api = api;
  window.toast = toast;
  window.createDrawer = createDrawer;
  window.renameDrawer = renameDrawer;
  window.deleteDrawer = deleteDrawer;
  window.restoreDrawer = restoreDrawer;
  window.addContainer = addContainer;
  window.renameContainer = renameContainer;
  window.moveContainer = moveContainer;
  window.deleteContainer = deleteContainer;
  window.restoreContainer = restoreContainer;
  window.openTextModal = openTextModal;
  window.openConfirmModal = openConfirmModal;
  window.openSelectDrawerModal = openSelectDrawerModal;
  window.openFormModal = openFormModal;
  window.openEditDrawerModal = openEditDrawerModal;
  window.openEditContainerModal = openEditContainerModal;
  window.openSelectContainerInDrawer = openSelectContainerInDrawer;
</script>
</body></html>"""
    return html_str


def _make_color_cell(name: str, hex_code: str) -> str:
    fg = "#000" if sum(int(hex_code[i : i + 2], 16) for i in (0, 2, 4)) > 382 else "#fff"
    return f'<td style="background: #{hex_code}; color:{fg}">{html.escape(name)}</td>'


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
    return STATUS_DISPLAY_NAMES.get(status, "Loose")


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
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Internal error:\n{exc}".encode())

    # ------------------------------ JSON helpers
    def _send_json(self, status: int, payload) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        body = self.rfile.read(length) if length else b""
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

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
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Static error: {e}".encode())

    # ------------------------------ API GET router
    def _handle_api_get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        try:
            if path == "/api/drawers":
                # Active drawers via db.list_drawers(); include_deleted not yet supported here
                rows = db.list_drawers()
                return self._send_json(200, rows)

            if path == "/api/containers":
                drawer_id = qs.get("drawer_id", [None])[0]
                if drawer_id is None:
                    return self._send_json(400, {"error": "drawer_id is required"})
                rows = db.list_containers_for_drawer(int(drawer_id))
                return self._send_json(200, rows)
        except Exception as e:
            return self._send_json(500, {"error": str(e)})

        return self._send_json(404, {"error": "Not Found"})

    # ------------------------------ API write methods
    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/api/"):
            return self._not_found()
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        try:
            # Create drawer
            if path == "/api/drawers":
                name = (data.get("name") or "").strip()
                if not name:
                    return self._send_json(400, {"error": "name is required"})
                try:
                    with db._connect() as conn:  # pylint: disable=protected-access
                        did = db.create_drawer(
                            conn,
                            name=name,
                            description=data.get("description"),
                            kind=data.get("kind"),
                            cols=data.get("cols"),
                            rows=data.get("rows"),
                        )
                    return self._send_json(201, {"id": did})
                except sqlite3.IntegrityError:
                    return self._send_json(409, {"error": "Duplicate drawer name"})

            # Create container
            if path == "/api/containers":
                if "drawer_id" not in data or "name" not in data:
                    return self._send_json(400, {"error": "drawer_id and name are required"})
                with db._connect() as conn:  # pylint: disable=protected-access
                    try:
                        cid = db.create_container(
                            conn,
                            drawer_id=int(data["drawer_id"]),
                            name=str(data["name"]).strip(),
                            description=data.get("description"),
                            row_index=data.get("row_index"),
                            col_index=data.get("col_index"),
                        )
                        return self._send_json(201, {"id": cid})
                    except db.DuplicateLabelError as e:  # type: ignore[attr-defined]
                        return self._send_json(
                            409, {"error": str(e) or "Duplicate label in this drawer"}
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
                    return self._send_json(400, {"error": "target_container_id is required"})
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

            return self._send_json(404, {"error": "Not Found"})
        except Exception as e:  # pylint: disable=broad-except
            return self._send_json(500, {"error": str(e)})

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
                    return self._send_json(409, {"error": "Duplicate drawer name"})

            # Update container
            m = re.match(r"^/api/containers/(\d+)$", path)
            if m:
                cid = int(m.group(1))
                with db._connect() as conn:  # pylint: disable=protected-access
                    try:
                        db.update_container(conn, cid, **data)
                        return self._send_json(200, {"updated": cid})
                    except db.DuplicateLabelError as e:  # type: ignore[attr-defined]
                        return self._send_json(
                            409, {"error": str(e) or "Duplicate label in this drawer"}
                        )

            return self._send_json(404, {"error": "Not Found"})
        except Exception as e:
            return self._send_json(500, {"error": str(e)})

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
                        return self._send_json(409, {"error": str(e)})

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
                        return self._send_json(
                            409,
                            {
                                "error": "Container has inventory; merge/move required",
                                "needed": "merge_move",
                            },
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
                        return self._send_json(
                            409,
                            {
                                "error": "Container has inventory; merge/move required",
                                "needed": "merge_move",
                            },
                        )

                    # Otherwise proceed with soft delete
                    try:
                        db.soft_delete_container(conn, cid)
                        return self._send_json(200, {"deleted": cid})
                    except db.InventoryConstraintError as e:  # type: ignore[attr-defined]
                        # Fallback: if helper enforces the rule, surface the same signal
                        return self._send_json(409, {"error": str(e), "needed": "merge_move"})

            return self._send_json(404, {"error": "Not Found"})
        except Exception as e:
            return self._send_json(500, {"error": str(e)})

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

        body = [
            f"<h1>Sets ({total_sets})</h1>",
            """<table id="sets_table" data-tablekey="sets" data-context="{}">
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
<tbody>""",
        ]

        for r in rows:
            body.append("<tr>")
            # Set Number, Name, Year, Status, Rebrickable Link, Image
            # Make set number a link to /sets/<set_num>
            body.append(
                f"<td><a href='/sets/{html.escape(r['set_num'])}'>{html.escape(r['set_num'])}</a></td>"
            )
            body.append(f"<td>{html.escape(r['name'])}</td>")
            body.append(f"<td>{r['year']}</td>")
            body.append(f"<td>{html.escape(_display_status(r['status']))}</td>")
            body.append(
                f"<td><a href='{html.escape(r['rebrickable_url'])}' target='_blank'>View</a></td>"
            )
            body.append(
                f"<td><img src='{html.escape(r['image_url'])}' alt='Set image' style='height: 48px;'></td>"
            )
            body.append("</tr>")

        body.append("</tbody></table>")
        self._send_ok(_html_page("EB's Bricks - Sets", "".join(body), total_qty=None))

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
                    (set_num,),
                ).fetchall()
                # Convert to list of dicts
                parts = []
                for r in rows:
                    parts.append(
                        {
                            "design_id": r["design_id"],
                            "name": r["name"],
                            "color_name": r["color_name"],
                            "hex": r["hex"],
                            "quantity": r["quantity"],
                            "part_url": r["part_url"],
                            "part_img_url": r["part_img_url"],
                        }
                    )

        # Compute total quantity for the set
        total_qty = sum(p.get("quantity", 0) for p in parts)
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
            design_id = html.escape(str(part.get("design_id", "")))
            # Part ID cell: hyperlink to part page
            table_body.append(f'<td><a href="/parts/{design_id}">{design_id}</a></td>')
            # Part Name cell: plain text
            table_body.append(f"<td>{html.escape(str(part.get('name', '')))}</td>")
            color_name = str(part.get("color_name", ""))
            hex_code = part.get("hex")
            if hex_code:
                table_body.append(_make_color_cell(color_name, hex_code))
            else:
                table_body.append(f"<td>{html.escape(color_name)}</td>")
            table_body.append(f"<td>{part.get('quantity', 0)}</td>")
            link = part.get("part_url") or (
                f"https://rebrickable.com/parts/{part.get('design_id','')}/"
            )
            img = part.get("part_img_url") or "https://rebrickable.com/static/img/nil.png"
            table_body.append(f"<td><a href='{html.escape(link)}' target='_blank'>View</a></td>")
            table_body.append(
                f"<td><img src='{html.escape(img)}' alt='Part image' style='height: 32px;'></td>"
            )
            table_body.append("</tr>")

        if not table_body:
            table_body.append("<tr><td colspan='6'>No matching parts found</td></tr>")

        table_html = (
            "<table><thead><tr>"
            "<th>Part ID</th><th>Part Name</th><th>Color</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th>"
            "</tr></thead><tbody>" + "".join(table_body) + "</tbody>"
            f"<tfoot><tr><th colspan='3'>Total</th><th>{total_qty:,}</th><th colspan='2'></th></tr></tfoot>"
            "</table>"
        )

        # Use _html_page for consistent look, pass None for total_qty to use combined totals in the header
        self._send_ok(
            _html_page(f"EB's Bricks - Set {set_num}", header_html + table_html, total_qty=None)
        )

    def _send_html(self, html_doc: str, status: int = 200):
        html_bytes = html_doc.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

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
                loc_html = f"<a href='/containers/{int(container_id)}'>{html.escape(loc_label)}</a>"
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
        rows = _query_master_rows()
        total_qty = sum(r["qty"] for r in rows)
        body = [
            "<h1>Loose Parts</h1>",
            "<table id='master_table' data-tablekey='inventory_master' data-context='{}'><thead><tr>",
            "<th>ID</th><th>Name</th><th>Color</th>"
            "<th>Drawer</th><th>Container</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>",
        ]
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
            link = r["part_url"] or f"https://rebrickable.com/parts/{r['design_id']}/"
            img = r["part_img_url"] or "https://rebrickable.com/static/img/nil.png"
            body.append(f"<td><a href='{html.escape(link)}' target='_blank'>View</a></td>")
            body.append(
                f"<td><img src='{html.escape(img)}' alt='Part image' style='height: 32px;'></td>"
            )
            body.append("</tr>")
        body.append("</tbody>")
        body.append(
            f"<tfoot><tr><th colspan='6'>Total</th><th colspan='2'>{total_qty:,}</th></tr></tfoot>"
        )
        body.append("</table>")
        self._send_ok(_html_page("EB's Bricks - Loose Parts", "".join(body), total_qty=None))

    def _serve_part(self, design_id: str):
        # Resolve part meta
        part = db.get_part(design_id) or {
            "design_id": design_id,
            "name": "Unknown part",
            "part_url": None,
            "part_img_url": None,
        }

        # Data for the two sections
        sets_rows = db.sets_for_part(design_id)
        # Resolve loose inventory via relational join (containers/drawers), with legacy fallback
        with db._connect() as conn:  # pylint: disable=protected-access
            rows = conn.execute(
                """
                SELECT
                    COALESCE(d.name, i.drawer)   AS drawer,
                    COALESCE(c2.name, i.container) AS container,
                    col.name AS color_name,
                    col.hex  AS hex,
                    SUM(i.quantity) AS quantity
                FROM inventory i
                JOIN colors col ON col.id = i.color_id
                LEFT JOIN containers c2 ON c2.id = i.container_id
                LEFT JOIN drawers    d  ON d.id  = c2.drawer_id
                WHERE i.status = 'loose' AND i.design_id = ?
                GROUP BY COALESCE(d.name, i.drawer), COALESCE(c2.name, i.container), col.id
                ORDER BY COALESCE(d.name, i.drawer), COALESCE(c2.name, i.container), col.id
                """,
                (design_id,),
            ).fetchall()
            loose_rows = [dict(r) for r in rows]

        # Totals for this part
        part_total = sum(r.get("quantity", 0) for r in sets_rows) + sum(
            r.get("quantity", 0) for r in loose_rows
        )

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
            hex_val = r.get("hex")
            if isinstance(hex_val, str) and hex_val:
                color_cell = _make_color_cell(r["color_name"], hex_val)
            else:
                color_cell = f"<td>{html.escape(r['color_name'])}</td>"
            sets_body.append("<tr>")
            sets_body.append(
                f"<td><a href='/sets/{html.escape(r['set_num'])}'>{html.escape(r['set_num'])}</a> – {html.escape(r['set_name'])}</td>"
            )
            sets_body.append(color_cell)
            sets_body.append(f"<td>{r['quantity']}</td>")
            sets_body.append("</tr>")
        if not sets_body:
            sets_body.append(
                "<tr><td colspan='3'>This part is not currently in any sets.</td></tr>"
            )
        sets_table = (
            "<h2>In Sets</h2>"
            "<table><thead><tr><th>Set</th><th>Color</th><th>Qty</th></tr></thead><tbody>"
            + "".join(sets_body)
            + "</tbody></table>"
        )

        # Loose Parts table
        loose_body = []
        for r in loose_rows:
            hex_val = r.get("hex")
            if isinstance(hex_val, str) and hex_val:
                color_cell = _make_color_cell(r["color_name"], hex_val)
            else:
                color_cell = f"<td>{html.escape(r['color_name'])}</td>"
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
            + "".join(loose_body)
            + "</tbody></table>"
        )

        self._send_ok(
            _html_page(
                f"EB's Bricks - Part {design_id}",
                header_html + sets_table + loose_table,
                total_qty=None,
            )
        )

    # The _serve_locations method has been removed.

    def _serve_drawers(self):
        rows = db.list_drawers()
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
            drawer_link = f"<a href='/drawers/{d['id']}'>{html.escape(d['name'])}</a>"
            actions = (
                f"<button type='button' data-action=\"rename-drawer\" "
                f"data-id=\"{d['id']}\" data-name=\"{html.escape(d['name'])}\" "
                f"data-desc=\"{html.escape(d.get('description') or '')}\" "
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
        containers = db.list_containers_for_drawer(drawer_id)
        total_unique = sum(c.get("unique_parts", 0) for c in containers)
        total_pieces = sum(c.get("part_count", 0) for c in containers)
        header = f"<h1>Drawer: {html.escape(d['name'])}</h1>"
        if d.get("description"):
            header += f"<p>{html.escape(d['description'])}</p>"
        controls = (
            "<div id='container-controls' style='margin: .5rem 0 1rem 0; display:flex; gap:.5rem; align-items:flex-end;'>"
            "  <div><label>Label<br><input id='new-container-name' placeholder='e.g., A1' /></label></div>"
            "  <div><label>Row<br><input id='new-container-row' type='number' style='width:6em' /></label></div>"
            "  <div><label>Col<br><input id='new-container-col' type='number' style='width:6em' /></label></div>"
            "  <div><label>Description<br><input id='new-container-desc' style='width:18em' /></label></div>"
            f'  <div><button type=\'button\' data-action="add-container" data-drawer-id="{drawer_id}">Add Container</button></div>'
            f"  <div style='margin-left:auto'><button type='button' data-action=\"rename-drawer\" data-id=\"{drawer_id}\" data-name=\"{html.escape(d.get('name') or '')}\" data-desc=\"{html.escape(d.get('description') or '')}\" data-cols=\"{html.escape(str(d.get('cols') or ''))}\" data-rows=\"{html.escape(str(d.get('rows') or ''))}\">Rename Drawer</button>"
            f'<button type=\'button\' data-action="delete-drawer" data-id="{drawer_id}">Delete Drawer</button></div>'
            "</div>"
        )
        body = [
            header,
            "<p><a href='/drawers'>&larr; All drawers</a></p>",
            controls,
            "<table id='containers_table'>",
            "<thead><tr><th>Pos</th><th>Name</th><th>Description</th><th>Unique Parts</th><th>Total Pieces</th><th>Actions</th></tr></thead><tbody>",
        ]
        for c in containers:
            pos = ""
            if c.get("row_index") is not None and c.get("col_index") is not None:
                pos = f"r{c['row_index']} c{c['col_index']}"
            raw_cname = c.get("name", "")
            name = html.escape(raw_cname)
            desc = html.escape(c.get("description") or "")
            uniq = c.get("unique_parts", 0)
            pieces = c.get("part_count", 0)
            actions = (
                f"<button type='button' data-action=\"rename-container\" data-id=\"{c['id']}\" "
                f"data-name=\"{html.escape(raw_cname)}\" data-desc=\"{html.escape(c.get('description') or '')}\" "
                f"data-row=\"{html.escape(str(c.get('row_index') or ''))}\" data-col=\"{html.escape(str(c.get('col_index') or ''))}\" "
                f'data-drawer-id="{drawer_id}">Rename</button> '
                f"<button type='button' data-action=\"move-container\" data-id=\"{c['id']}\" data-drawer-id=\"{drawer_id}\">Move</button> "
                f"<button type='button' data-action=\"delete-container\" data-id=\"{c['id']}\" data-drawer-id=\"{drawer_id}\">Delete</button>"
            )
            body.append(
                f"<tr><td>{pos}</td><td><a href='/containers/{c['id']}'>{name}</a></td><td>{desc}</td><td>{uniq}</td><td>{pieces:,}</td><td>{actions}</td></tr>"
            )
        body.append("</tbody>")
        body.append(
            f"<tfoot><tr><th colspan='3' style='text-align:right'>Totals</th><th>{total_unique}</th><th>{total_pieces:,}</th><th></th></tr></tfoot>"
        )
        body.append("</table>")
        self._send_ok(
            _html_page(f"EB's Bricks - Drawer {d['name']}", "".join(body), total_qty=None)
        )

    def _serve_container_detail(self, container_id: int):
        c = db.get_container(container_id)
        if not c:
            self._not_found()
            return
        parts = db.list_parts_in_container(container_id)
        total_qty = sum(p.get("qty", 0) for p in parts)

        header = (
            f"<h1>Container: {html.escape(c['name'])}</h1>"
            f"<p>Drawer: <a href='/drawers/{c['drawer_id']}'>{html.escape(c.get('drawer_name',''))}</a></p>"
        )
        page_title = f"Container {c['name']}"
        actions_html = (
            f"<div style='margin:.5rem 0 1rem 0'>"
            f'  <button type=\'button\' data-action="rename-container" data-id="{container_id}" '
            f"data-name=\"{html.escape(c.get('name') or '')}\" data-desc=\"{html.escape(c.get('description') or '')}\" "
            f"data-row=\"{html.escape(str(c.get('row_index') or ''))}\" data-col=\"{html.escape(str(c.get('col_index') or ''))}\" "
            f"data-drawer-id=\"{c['drawer_id']}\">Rename</button> "
            f"  <button type='button' data-action=\"move-container\" data-id=\"{container_id}\" data-drawer-id=\"{c['drawer_id']}\">Move</button> "
            f"  <button type='button' data-action=\"delete-container\" data-id=\"{container_id}\" data-drawer-id=\"{c['drawer_id']}\">Delete</button>"
            f"</div>"
        )
        header = header + actions_html
        body = [
            header,
            f"<table id='container_parts' data-tablekey='container_parts' data-context='{{\"container_id\": {container_id}}}'>",
            "<thead><tr><th>Design ID</th><th>Part</th><th>Color</th><th>Qty</th><th>Rebrickable Link</th><th>Image</th></tr></thead><tbody>",
        ]
        for p in parts:
            design_id = html.escape(str(p.get("design_id", "")))
            part_name = html.escape(str(p.get("part_name", "")))
            color_name = str(p.get("color_name", ""))
            hex_code = p.get("hex")
            color_td = (
                _make_color_cell(color_name, hex_code)
                if hex_code
                else f"<td>{html.escape(color_name)}</td>"
            )
            qty = p.get("qty", 0)
            link = f"https://rebrickable.com/parts/{p.get('design_id','')}/"
            part_meta = db.get_part(p.get("design_id", "")) or {}
            img = part_meta.get("part_img_url") or "https://rebrickable.com/static/img/nil.png"
            body.append(
                f"<tr><td><a href='/parts/{design_id}'>{design_id}</a></td><td>{part_name}</td>{color_td}<td>{qty}</td>"
                f"<td><a href='{html.escape(link)}' target='_blank'>View</a></td><td><img src='{html.escape(img)}' alt='Part image' style='height: 32px;'></td></tr>"
            )
        if not parts:
            body.append("<tr><td colspan='6'>(empty)</td></tr>")
        body.append("</tbody>")
        body.append(
            f"<tfoot><tr><th colspan='3' style='text-align:right'>Total</th><th>{total_qty:,}</th><th colspan='2'></th></tr></tfoot>"
        )
        body.append("</table>")
        self._send_ok(_html_page(f"EB's Bricks - {page_title}", "".join(body), total_qty=None))

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
            link = r["part_url"] or f"https://rebrickable.com/parts/{design_id}/"
            img = r["part_img_url"] or "https://rebrickable.com/static/img/nil.png"

            cell_id = f"<a href='/parts/{html.escape(design_id)}'>{html.escape(design_id)}</a>"
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
                    JOIN sets s ON s.set_num = sp.set_num
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
            part_url = r["part_url"] or f"https://rebrickable.com/parts/{design_id}/"
            rb_color_url = (
                f"https://rebrickable.com/parts/{design_id}/{int(color_id)}/"
                if color_id is not None
                else part_url
            )
            img_url = r["part_img_url"] or "https://rebrickable.com/static/img/nil.png"

            # Cells
            cell_id = f"<a href='/parts/{html.escape(design_id)}'>{html.escape(design_id)}</a>"
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
        if table_key == "sets":
            with db._connect() as conn:
                rs = conn.execute(
                    """
                    SELECT set_num, name, year, status, rebrickable_url, image_url
                    FROM sets
                    ORDER BY added_at DESC
                    """
                ).fetchall()
            rows = [
                {
                    "Set Number": r["set_num"],
                    "Name": r["name"],
                    "Year": r["year"],
                    "Status": _display_status(r["status"]),
                    "Rebrickable Link": r["rebrickable_url"],
                    "Image": r["image_url"],
                }
                for r in rs
            ]
            columns = ["Set Number", "Name", "Year", "Status", "Rebrickable Link", "Image"]
            return rows, columns

        if table_key == "drawers":
            rows = []
            for r in db.list_drawers():
                rows.append(
                    {
                        "Name": r.get("name", ""),
                        "Description": r.get("description") or "",
                        "Containers": r.get("container_count", 0),
                        "Total Pieces": r.get("part_count", 0),
                    }
                )
            columns = ["Name", "Description", "Containers", "Total Pieces"]
            return rows, columns

        if table_key == "container_parts":
            container_id = int(ctx.get("container_id", 0))
            parts = db.list_parts_in_container(container_id)
            rows = []
            for p in parts:
                part_meta = db.get_part(p.get("design_id", "")) or {}
                rows.append(
                    {
                        "Design ID": p.get("design_id", ""),
                        "Part": p.get("part_name", ""),
                        "Color": p.get("color_name", ""),
                        "Qty": p.get("qty", 0),
                        "Rebrickable Link": f"https://rebrickable.com/parts/{p.get('design_id','')}/",
                        "Image": part_meta.get("part_img_url")
                        or "https://rebrickable.com/static/img/nil.png",
                    }
                )
            columns = ["Design ID", "Part", "Color", "Qty", "Rebrickable Link", "Image"]
            return rows, columns

        if table_key == "inventory_master":
            rows_raw = _query_master_rows()
            rows = []
            for r in rows_raw:
                rows.append(
                    {
                        "ID": r["design_id"],
                        "Name": r["part_name"],
                        "Color": r["color_name"],
                        "Drawer": r.get("drawer") or "",
                        "Container": r.get("container") or "",
                        "Qty": r["qty"],
                        "Rebrickable Link": r.get("part_url")
                        or f"https://rebrickable.com/parts/{r['design_id']}/",
                        "Image": r.get("part_img_url")
                        or "https://rebrickable.com/static/img/nil.png",
                    }
                )
            columns = [
                "ID",
                "Name",
                "Color",
                "Drawer",
                "Container",
                "Qty",
                "Rebrickable Link",
                "Image",
            ]
            return rows, columns

        if table_key == "part_counts":
            with db._connect() as conn:
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
                    "Part ID": r["design_id"],
                    "Name": r["part_name"],
                    "Total Quantity": r["total_qty"],
                    "Rebrickable Link": r["part_url"]
                    or f"https://rebrickable.com/parts/{r['design_id']}/",
                    "Image": r["part_img_url"] or "https://rebrickable.com/static/img/nil.png",
                }
                for r in rs
            ]
            columns = ["Part ID", "Name", "Total Quantity", "Rebrickable Link", "Image"]
            return rows, columns

        if table_key == "part_color_counts":
            with db._connect() as conn:
                rs = conn.execute(
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

                        -- Parts in sets
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
            rows = [
                {
                    "Part ID": r["design_id"],
                    "Name": r["part_name"],
                    "Color": r["color_name"],
                    "Total Quantity": r["total_qty"],
                    "Rebrickable Link": r["part_url"]
                    or f"https://rebrickable.com/parts/{r['design_id']}/",
                    "Image": r["part_img_url"] or "https://rebrickable.com/static/img/nil.png",
                }
                for r in rs
            ]
            columns = ["Part ID", "Name", "Color", "Total Quantity", "Rebrickable Link", "Image"]
            return rows, columns

        if table_key == "location_counts":
            with db._connect() as conn:  # pylint: disable=protected-access
                rows = conn.execute(
                    """
                    SELECT
                        COALESCE(d.name, i.drawer)     AS drawer,
                        COALESCE(c2.name, i.container) AS container,
                        SUM(i.quantity)                AS total_qty
                    FROM inventory i
                    LEFT JOIN containers c2 ON c2.id = i.container_id
                    LEFT JOIN drawers    d  ON d.id  = c2.drawer_id
                    WHERE i.status NOT IN ('built', 'wip', 'in_box', 'teardown')
                    GROUP BY COALESCE(d.name, i.drawer), COALESCE(c2.name, i.container)
                    """
                ).fetchall()
            out = []
            for r in rows:
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
                out.append({"Location": loc, "Total Quantity": int(r["total_qty"] or 0)})
            # Sort by quantity desc to match page view
            out.sort(key=lambda x: x["Total Quantity"], reverse=True)
            return out, ["Location", "Total Quantity"]

        if table_key == "part_counts":
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
            out = []
            for r in rows:
                design_id = str(r["design_id"]) if r["design_id"] is not None else ""
                name = r["part_name"] or ""
                qty = int(r["total_qty"] or 0)
                link = r["part_url"] or f"https://rebrickable.com/parts/{design_id}/"
                img = r["part_img_url"] or "https://rebrickable.com/static/img/nil.png"
                out.append(
                    {
                        "Part ID": design_id,
                        "Name": name,
                        "Total Quantity": qty,
                        "Rebrickable Link": link,
                        "Image": img,
                    }
                )
            return out, ["Part ID", "Name", "Total Quantity", "Rebrickable Link", "Image"]

        if table_key == "part_color_counts":
            with db._connect() as conn:  # pylint: disable=protected-access
                rows = conn.execute(
                    """
                    SELECT
                        pc.design_id,
                        p.name        AS part_name,
                        pc.color_id,
                        c.name        AS color_name,
                        SUM(pc.total_qty) AS total_qty
                    FROM (
                        SELECT i.design_id, i.color_id, SUM(i.quantity) AS total_qty
                        FROM inventory i
                        WHERE i.status = 'loose'
                        GROUP BY i.design_id, i.color_id
                        UNION ALL
                        SELECT sp.design_id, sp.color_id, SUM(sp.quantity) AS total_qty
                        FROM set_parts sp
                        JOIN sets s ON s.set_num = sp.set_num
                        WHERE s.status IN ('built','wip','in_box','teardown')
                        GROUP BY sp.design_id, sp.color_id
                    ) pc
                    JOIN parts  p ON p.design_id = pc.design_id
                    LEFT JOIN colors c ON c.id = pc.color_id
                    GROUP BY pc.design_id, p.name, pc.color_id, c.name
                    ORDER BY total_qty DESC
                    """
                ).fetchall()
            out = []
            for r in rows:
                design_id = str(r["design_id"]) if r["design_id"] is not None else ""
                name = r["part_name"] or ""
                color_name = r["color_name"] or "(unknown)"
                qty = int(r["total_qty"] or 0)
                out.append(
                    {
                        "Part ID": design_id,
                        "Name": name,
                        "Color": color_name,
                        "Total Quantity": qty,
                    }
                )
            return out, ["Part ID", "Name", "Color", "Total Quantity"]

        raise ValueError(f"Unsupported table key: {table_key}")

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
