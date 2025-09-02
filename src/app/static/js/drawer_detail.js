(function () {
    async function api(method, path, body) {
        const res = await fetch(path, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined
        });
        let json = null;
        try { json = await res.json(); } catch (_) { }
        return { ok: res.ok, status: res.status, json };
    }

    function toast(msg) { alert(msg); }

    async function createContainer() {
        const name = (document.getElementById('new-container-name') || {}).value?.trim();
        const desc = (document.getElementById('new-container-desc') || {}).value?.trim() || '';
        const rowV = (document.getElementById('new-container-row') || {}).value || '';
        const colV = (document.getElementById('new-container-col') || {}).value || '';

        if (!name) { toast('Please enter a container name.'); return; }

        const drawer_id = parseInt(document.body.dataset.drawerId || '0', 10) || 0;
        if (!drawer_id) { toast('Missing drawer id.'); return; }

        const payload = { drawer_id, name };
        if (desc) payload.description = desc;
        if (rowV !== '') payload.row_index = parseInt(rowV, 10);
        if (colV !== '') payload.col_index = parseInt(colV, 10);

        const r = await api('POST', '/api/containers/create', payload);
        if (r.ok) location.reload();
        else toast(r.json?.error || 'Failed to create container');
    }

    function renameContainer(buttonEl) {
        // Expect data-* attributes on the button for prefill
        const dataset = buttonEl?.dataset || {};
        const containerId = dataset.containerId || dataset.id;
        const name = dataset.name || '';
        const description = dataset.description || '';
        const rowIndex = dataset.rowIndex || '';
        const colIndex = dataset.colIndex || '';

        let dlg = document.getElementById('edit-container-dialog')
            || document.getElementById('container-edit-dialog')
            || document.querySelector('dialog[data-role="edit-container"]');
        if (!dlg) {
            // If no dialog exists, create one dynamically
            dlg = document.createElement('dialog');
            dlg.id = 'edit-container-dialog';
            dlg.innerHTML = `
                <style>
                  .ib-dialog .row { display:grid; grid-template-columns: 1fr 1fr; gap: .5rem 1rem; }
                  .ib-dialog .actions { margin-top:.75rem; display:flex; gap:.5rem; justify-content:flex-end; }
                </style>
                <h3>Edit Container</h3>
                <div class="msg"></div>
                <form id="lego-modal-form" class="ib-dialog">
                  <div class="row">
                    <div><label>Name<br><input id="edit-container-name" name="name" type="text"></label></div>
                    <div><label>Description<br><input id="edit-container-desc" name="desc" type="text"></label></div>
                  </div>
                  <div class="row" style="margin-top:.5rem;">
                    <div><label>Row<br><input id="edit-container-row" name="row_index" type="number" min="0"></label></div>
                    <div><label>Column<br><input id="edit-container-col" name="col_index" type="number" min="0"></label></div>
                  </div>
                </form>
                <div class="actions">
                  <button type="button" data-act="cancel">Cancel</button>
                  <button type="button" data-act="save">Save</button>
                </div>`;
            document.body.appendChild(dlg);

            // Wire up cancel/save buttons
            dlg.querySelector('[data-act="cancel"]').addEventListener('click', () => {
                dlg.close();
            });
            dlg.querySelector('[data-act="save"]').addEventListener('click', async (ev) => {
                ev.preventDefault();
                const cid = dlg.dataset.containerId;
                const payload = {
                    name: document.getElementById('edit-container-name').value.trim(),
                    description: document.getElementById('edit-container-desc').value.trim(),
                    row_index: parseInt(document.getElementById('edit-container-row').value || '0', 10),
                    col_index: parseInt(document.getElementById('edit-container-col').value || '0', 10),
                };
                const r = await api('PUT', `/api/containers/${cid}`, payload);
                if (r.ok) location.reload();
                else toast(r.json?.error || 'Failed to update container');
            });
        }

        // Stash the id on the dialog for whoever saves
        dlg.dataset.containerId = containerId || '';

        // Pre-fill inputs if present
        const nameEl = document.getElementById('edit-container-name');
        const descEl = document.getElementById('edit-container-desc');
        const rowEl = document.getElementById('edit-container-row');
        const colEl = document.getElementById('edit-container-col');

        if (nameEl) nameEl.value = name;
        if (descEl) descEl.value = description;
        if (rowEl) rowEl.value = rowIndex;
        if (colEl) colEl.value = colIndex;

        // Open single, full dialog
        if (typeof dlg.showModal === 'function') {
            dlg.showModal();
        } else {
            dlg.open = true; // fallback
        }
    }

    async function deleteContainer(buttonEl) {
        const dataset = buttonEl?.dataset || {};
        const containerId = parseInt(dataset.containerId || dataset.id || '0', 10) || 0;
        const name = dataset.name || '';
        if (!containerId) { toast('Missing container id.'); return; }
        if (!confirm(`Delete container${name ? ` \"${name}\"` : ''}? This cannot be undone.`)) return;
        const r = await api('POST', '/api/containers/delete', { id: containerId });
        if (r.ok) location.reload();
        else toast(r.json?.error || 'Failed to delete container');
    }

    async function moveContainer(buttonEl) {
        const dataset = buttonEl?.dataset || {};
        const containerId = parseInt(dataset.containerId || dataset.id || '0', 10) || 0;
        if (!containerId) { toast('Missing container id.'); return; }

        // 1) Fetch drawers for dropdown (id + name)
        const drawersRes = await fetch('/api/drawers');
        let drawers = [];
        try { drawers = await drawersRes.json(); } catch (_) { drawers = []; }
        // Normalize to [{id, name}] if API returns a wrapper
        if (drawers && drawers.items) drawers = drawers.items;

        // Pre-fill values from data attributes if present
        const initial = {
            new_drawer_id: dataset.targetDrawerId || String(document.body.dataset.drawerId || ''),
            row_index: dataset.rowIndex || '',
            col_index: dataset.colIndex || '',
            sort_index: dataset.sortIndex || ''
        };

        const options = (Array.isArray(drawers) ? drawers : []).map(d => {
            const id = d.id ?? d.ID ?? d.Id;
            const name = (d.name ?? d.label ?? `Drawer ${id}`);
            const sel = String(id) === String(initial.new_drawer_id) ? 'selected' : '';
            return `<option value="${id}" ${sel}>${name} (#${id})</option>`;
        }).join('');

        // Build one dialog with all inputs
        const html = `
            <form method="dialog" class="ib-dialog">
                <h3>Move Container</h3>
                <label>Target drawer
                    <select name="new_drawer_id">${options}</select>
                </label>
                <div class="grid-3">
                    <label>Row
                        <input name="row_index" type="number" inputmode="numeric" value="${String(initial.row_index)}" />
                    </label>
                    <label>Col
                        <input name="col_index" type="number" inputmode="numeric" value="${String(initial.col_index)}" />
                    </label>
                    <label>Sort
                        <input name="sort_index" type="number" inputmode="numeric" value="${String(initial.sort_index)}" />
                    </label>
                </div>
                <menu>
                    <button value="cancel">Cancel</button>
                    <button value="ok" class="primary">Move</button>
                </menu>
            </form>`;

        const result = await openFormDialog(html);
        if (!result || result._action !== 'ok') return; // cancelled

        const payload = { id: containerId };
        const toInt = (v) => (v === '' || v === null || v === undefined) ? null : Number.parseInt(String(v), 10);
        const drawerVal = toInt(result.new_drawer_id);
        if (drawerVal !== null && Number.isFinite(drawerVal)) payload.new_drawer_id = drawerVal;
        ['row_index', 'col_index', 'sort_index'].forEach(k => {
            const n = toInt(result[k]);
            if (n !== null && Number.isFinite(n)) payload[k] = n;
        });
        if (Object.keys(payload).length === 1) { toast('No fields provided'); return; }

        const r = await api('POST', '/api/containers/move', payload);
        if (r.ok) location.reload();
        else toast(r.json?.error || 'Failed to move container');
    }

    async function openFormDialog(innerHTML) {
        return new Promise((resolve) => {
            const dlg = document.createElement('dialog');
            dlg.className = 'ib-modal';
            dlg.innerHTML = innerHTML;
            document.body.appendChild(dlg);
            const form = dlg.querySelector('form');
            const onClose = () => {
                const fd = new FormData(form);
                const obj = Object.fromEntries(fd.entries());
                obj._action = dlg.returnValue || 'cancel';
                dlg.removeEventListener('close', onClose);
                dlg.remove();
                resolve(obj);
            };
            dlg.addEventListener('close', onClose);
            if (typeof dlg.showModal === 'function') dlg.showModal();
            else dlg.open = true;
        });
    }

    // Event delegation
    document.addEventListener('click', function (e) {
        const el = e.target.closest('button[data-action]');
        if (!el) return;
        // Prevent default submit behavior and stop legacy inline handlers/prompt()
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        const action = el.getAttribute('data-action');
        if (action === 'create-container') { createContainer(); return; }
        if (action === 'rename-container') { renameContainer(el); return; }
        if (action === 'move-container') { moveContainer(el); return; }
        if (action === 'delete-container') { deleteContainer(el); return; }
    }, true);
})();