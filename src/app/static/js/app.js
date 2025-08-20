document.addEventListener('DOMContentLoaded', function () {
    // Guard to prevent rebinding
    if (window.__legoActionsInstalled) return;
    window.__legoActionsInstalled = true;

    // Helper for API requests
    async function api(url, opts = {}) {
        const resp = await fetch(url, {
            headers: {
                ...(opts.headers || {}),
                ...(opts.body ? { 'Content-Type': 'application/json' } : {}),
            },
            ...opts,
        });
        if (!resp.ok) {
            let msg = 'Error';
            try {
                const err = await resp.json();
                msg = err.message || JSON.stringify(err);
            } catch (e) {
                msg = resp.statusText;
            }
            throw new Error(msg);
        }
        // Try to parse JSON, fallback to text
        try {
            return await resp.json();
        } catch {
            return await resp.text();
        }
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
                    alert('Drawer ID missing!');
                    return;
                }
                if (!name) {
                    alert('Container name required!');
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
            alert('Error: ' + err.message);
        }
    });
});