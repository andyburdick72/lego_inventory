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

    // Event delegation
    document.addEventListener('click', function (e) {
        const el = e.target.closest('button[data-action]');
        if (!el) return;
        const action = el.getAttribute('data-action');
        if (action === 'create-container') return createContainer();
    });
})();