// src/app/static/js/drawers.js
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

    // ---- Actions ----
    async function createDrawer() {
        const name = (document.getElementById('new-drawer-name') || {}).value?.trim();
        const desc = (document.getElementById('new-drawer-desc') || {}).value?.trim() || '';
        const cols = parseInt((document.getElementById('new-drawer-cols') || {}).value || '0', 10) || null;
        const rows = parseInt((document.getElementById('new-drawer-rows') || {}).value || '0', 10) || null;
        if (!name) { toast('Please enter a drawer name.'); return; }

        const r = await api('POST', '/api/drawers', { name, description: desc, cols, rows });
        if (r.ok) location.reload();
        else toast(r.json?.error || 'Failed to create drawer');
    }

    async function renameDrawer(btn) {
        var id = parseInt(btn.getAttribute('data-drawer-id') || '0', 10) || 0;
        var name = btn.getAttribute('data-name') || '';
        var desc = btn.getAttribute('data-description') || '';
        var cols = btn.getAttribute('data-cols') || '';
        var rows = btn.getAttribute('data-rows') || '';

        var modal = document.getElementById('lego-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'lego-modal';
            modal.innerHTML = '<div class="panel">\
      <h3>Edit Drawer</h3>\
      <div class="msg"></div>\
      <form id="lego-modal-form">\
        <div class="row">\
          <div><label>Name<br><input name="name"></label></div>\
          <div><label>Description<br><input name="desc"></label></div>\
        </div>\
        <div class="row" style="margin-top:.5rem;">\
          <div><label>Rows<br><input name="rows" type="number" min="0"></label></div>\
          <div><label>Columns<br><input name="cols" type="number" min="0"></label></div>\
        </div>\
      </form>\
      <div class="actions">\
        <button type="button" data-act="cancel">Cancel</button>\
        <button type="button" data-act="save">Save</button>\
      </div>\
    </div>';
            document.body.appendChild(modal);
        }

        function show() { modal.style.display = 'flex'; }
        function hide() { modal.style.display = 'none'; }

        var form = modal.querySelector('#lego-modal-form');
        form.name.value = name;
        form.desc.value = desc;
        form.cols.value = cols;
        form.rows.value = rows;

        show();

        function onClick(e) {
            var actBtn = e.target.closest('button[data-act]');
            if (!actBtn) return;
            var act = actBtn.getAttribute('data-act');
            if (act === 'cancel') { cleanup(); hide(); }
            if (act === 'save') { save(); }
        }

        async function save() {
            var payload = { name: form.name.value.trim() };
            var d = form.desc.value.trim(); if (d !== '') payload.description = d;
            var c = form.cols.value.trim(); if (c !== '') payload.cols = parseInt(c, 10);
            var r = form.rows.value.trim(); if (r !== '') payload.rows = parseInt(r, 10);

            const res = await api('PUT', '/api/drawers/' + id, payload);
            cleanup(); hide();
            if (res.ok) location.reload();
            else toast(res.json && res.json.error ? res.json.error : 'Failed to update drawer');
        }

        function cleanup() { modal.removeEventListener('click', onClick); }
        modal.addEventListener('click', onClick);
    }

    async function deleteDrawer(btn) {
        const id = parseInt(
            btn.getAttribute('data-id') ||
            btn.getAttribute('data-drawer-id') ||
            '0', 10
        ) || 0;
        if (!id) { toast('Missing drawer id'); return; }

        const name = btn.getAttribute('data-name') || '';
        const msg = `Soft delete this drawer${name ? ` "${name}"` : ''}? (must be empty)`;
        if (!confirm(msg)) return;

        // Use action-style endpoint to align with new server routes
        const r = await api('POST', '/api/drawers/delete', { id });
        if (r.ok) location.reload();
        else toast(r.json?.error || 'Failed to delete drawer');
    }

    async function moveDrawer(btn) {
        const id = parseInt(btn.getAttribute('data-id') || btn.getAttribute('data-drawer-id') || '0', 10) || 0;
        if (!id) { toast('Missing drawer id'); return; }
        const current = parseInt(btn.getAttribute('data-sort-index') || '0', 10) || '';
        const input = prompt('New position (sort index):', current);
        if (input === null) return; // user cancelled
        const new_sort_index = input.trim() === '' ? null : parseInt(input, 10);
        if (Number.isNaN(new_sort_index) && input.trim() !== '') { toast('Please enter a number'); return; }
        const r = await api('POST', '/api/drawers/move', { id, new_sort_index });
        if (r.ok) location.reload();
        else toast(r.json?.error || 'Failed to move drawer');
    }

    // ---- Event delegation ----
    document.addEventListener('click', function (e) {
        const el = e.target.closest('button[data-action]');
        if (!el) return;
        const action = el.getAttribute('data-action');

        // Block default and any legacy handlers before they can run (prevents double prompts)
        if (
            action === 'create-drawer' ||
            action === 'rename-drawer' ||
            action === 'move-drawer' ||
            action === 'delete-drawer'
        ) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
        }

        if (action === 'create-drawer') { createDrawer(); return; }
        if (action === 'rename-drawer') { renameDrawer(el); return; }
        if (action === 'move-drawer') { moveDrawer(el); return; }
        if (action === 'delete-drawer') { deleteDrawer(el); return; }
    }, true); // capture phase
})();