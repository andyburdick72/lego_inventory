document.addEventListener('DOMContentLoaded', function () {
    // Guard to prevent rebinding
    if (window.__legoActionsInstalled) return;
    window.__legoActionsInstalled = true;

    // Centralized API wrapper using AppApi (from src/app/static/js/api.js)
    const Api = (window.AppApi) || {
        async api(method, path, body) {
            const res = await fetch(path, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: body != null ? JSON.stringify(body) : undefined,
            });
            let json = null; try { json = await res.json(); } catch (_) { }
            const ok = res.ok;
            const error = json && json.error ? json.error : { code: 'unknown', message: res.statusText };
            const message = (json && json.error && json.error.message) ? json.error.message : (ok ? '' : (res.statusText || 'Request failed'));
            return { ok, status: res.status, json, error, message };
        },
        toast(msg) {
            try {
                let c = document.getElementById('toast-container');
                if (!c) {
                    c = document.createElement('div');
                    c.id = 'toast-container';
                    c.style.position = 'fixed';
                    c.style.bottom = '16px';
                    c.style.right = '16px';
                    c.style.zIndex = '9999';
                    c.style.display = 'flex';
                    c.style.flexDirection = 'column';
                    c.style.gap = '8px';
                    document.body.appendChild(c);
                }
                const t = document.createElement('div');
                t.textContent = String(msg ?? '');
                t.style.padding = '10px 12px';
                t.style.background = '#333';
                t.style.color = '#fff';
                t.style.borderRadius = '4px';
                t.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
                t.style.maxWidth = '320px';
                t.style.fontSize = '14px';
                c.appendChild(t);
                setTimeout(() => {
                    t.style.transition = 'opacity .3s';
                    t.style.opacity = '0';
                    setTimeout(() => t.remove(), 300);
                }, 3000);
            } catch (_) { console.warn(msg); }
        },
        humanizeApiError(err) { return (err && err.message) || 'Unexpected error'; },
    };

    // Keep function name `api` for existing call sites; convert opts to AppApi signature
    async function api(url, opts = {}) {
        const method = opts.method || 'GET';
        let payload = undefined;
        if (opts.body != null) {
            // Convert stringified JSON bodies back to objects for AppApi.api
            if (typeof opts.body === 'string') {
                try { payload = JSON.parse(opts.body); } catch { payload = opts.body; }
            } else {
                payload = opts.body;
            }
        }
        const r = await Api.api(method, url, payload);
        if (!r.ok) {
            // Throw the normalized error object so callers can humanize
            throw (r.error || { code: 'unknown', message: r.message || 'Request failed' });
        }
        return r.json;
    }

    // Event delegation for buttons with data-action
    document.body.addEventListener('click', async function (e) {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        // Find relevant row (tr) for context
        const row = btn.closest('tr');
        try {
            if (action === 'rename-container') {
                const containerId = btn.dataset.id || (row && row.dataset.id);
                if (!containerId) return;
                const currentName = btn.dataset.name || (row && row.dataset.name) || '';
                const newName = prompt('Enter new container name:', currentName);
                if (newName && newName !== currentName) {
                    await api(`/api/containers/${containerId}`, {
                        method: 'PUT',
                        body: JSON.stringify({ name: newName })
                    });
                    location.reload();
                }
            }
            else if (action === 'move-container') {
                const containerId = btn.dataset.id || (row && row.dataset.id);
                if (!containerId) return;
                const currentPos = btn.dataset.position || (row && row.dataset.position) || '';
                const newPos = prompt('Enter new position:', currentPos);
                if (newPos && newPos !== currentPos) {
                    await api(`/api/containers/${containerId}`, {
                        method: 'PUT',
                        body: JSON.stringify({ position: newPos })
                    });
                    location.reload();
                }
            }
            else if (action === 'delete-container') {
                const containerId = btn.dataset.id || (row && row.dataset.id);
                if (!containerId) return;
                if (confirm('Are you sure you want to delete this container?')) {
                    await api(`/api/containers/${containerId}`, { method: 'DELETE' });
                    location.reload();
                }
            }
            else if (action === 'rename-drawer') {
                const drawerId = btn.dataset.id || (row && row.dataset.id);
                if (!drawerId) return;
                const currentName = btn.dataset.name || (row && row.dataset.name) || '';
                const newName = prompt('Enter new drawer name:', currentName);
                if (newName && newName !== currentName) {
                    await api(`/api/drawers/${drawerId}`, {
                        method: 'PUT',
                        body: JSON.stringify({ name: newName })
                    });
                    location.reload();
                }
            }
            else if (action === 'delete-drawer') {
                const drawerId = btn.dataset.id || (row && row.dataset.id);
                if (!drawerId) return;
                if (confirm('Are you sure you want to delete this drawer?')) {
                    await api(`/api/drawers/${drawerId}`, { method: 'DELETE' });
                    location.reload();
                }
            }
            else if (action === 'add-container') {
                // Find inputs near the button for position, name, description
                // Assume inputs are in the same row or nearby
                let container = row || btn.closest('.add-container-row');
                if (!container) container = btn.parentElement;
                const findInput = (sel) => container ? container.querySelector(sel) : document.querySelector(sel);
                const position = findInput('input[name="position"]')?.value || '';
                const name = findInput('input[name="name"]')?.value || '';
                const description = findInput('input[name="description"]')?.value || '';
                const drawerId = btn.dataset.drawerId || (row && row.dataset.drawerId);
                if (!drawerId) {
                    Api.toast('Drawer ID missing!');
                    return;
                }
                if (!name) {
                    Api.toast('Container name required!');
                    return;
                }
                await api('/api/containers', {
                    method: 'POST',
                    body: JSON.stringify({
                        name,
                        position,
                        description,
                        drawer_id: drawerId
                    })
                });
                location.reload();
            }
        } catch (err) {
            const { humanizeApiError, toast } = Api;
            toast(humanizeApiError(err));
        }
    });
});