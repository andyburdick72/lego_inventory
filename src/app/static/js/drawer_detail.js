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

        const r = await api('POST', '/api/containers', payload);
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
                <h3>Edit Container</h3>
                <div class="msg"></div>
                <form id="lego-modal-form">
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

    // Event delegation
    document.addEventListener('click', function (e) {
        const el = e.target.closest('button[data-action]');
        if (!el) return;
        // Prevent default submit behavior and stop legacy inline handlers/prompt()
        e.preventDefault();
        e.stopPropagation();
        const action = el.getAttribute('data-action');
        if (action === 'create-container') { createContainer(); return; }
        if (action === 'rename-container') { renameContainer(el); return; }
    });
})();