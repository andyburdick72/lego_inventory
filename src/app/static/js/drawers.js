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
        var id = parseInt(btn.getAttribute('data-id') || '0', 10) || 0;
        var name = btn.getAttribute('data-name') || '';
        var desc = btn.getAttribute('data-desc') || '';
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
          <div><label>Desc<br><input name="desc"></label></div>\
        </div>\
        <div class="row" style="margin-top:.5rem;">\
          <div><label>Cols<br><input name="cols" type="number" min="0"></label></div>\
          <div><label>Rows<br><input name="rows" type="number" min="0"></label></div>\
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
        const id = parseInt(btn.getAttribute('data-id') || '0', 10) || 0;
        if (!id) return;
        if (!confirm('Soft delete this drawer? (must be empty)')) return;

        const r = await api('DELETE', `/api/drawers/${id}`);
        if (r.ok) location.reload();
        else toast(r.json?.error || 'Failed to delete drawer');
    }

    // ---- Event delegation ----
    document.addEventListener('click', function (e) {
        const el = e.target.closest('button[data-action]');
        if (!el) return;
        const action = el.getAttribute('data-action');
        if (action === 'create-drawer') return createDrawer();
        if (action === 'rename-drawer') return renameDrawer(el);
        if (action === 'delete-drawer') return deleteDrawer(el);
    });
})();