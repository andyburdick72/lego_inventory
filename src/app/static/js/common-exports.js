// Common CSV export helper for DataTables-backed pages.
//
// Usage per page:
//   hookCsvExport('#export-sets', 'sets', '#sets-table');
//   hookCsvExport('#export-drawers', 'drawers', '#drawers-table');
//   hookCsvExport('#export-containers', 'containers', '#containers-table');

(function () {
    function getColumnKeysInOrder(dt) {
        // DataTables 1.10+ API: columns().dataSrc() returns array of data keys (or functions)
        // We only keep string keys (ignore function columns like action buttons).
        const sources = dt.columns().dataSrc().toArray();
        return sources.filter(s => typeof s === 'string' && s.trim().length > 0);
    }

    function buildExportUrl(tableName, columnKeys) {
        const cols = encodeURIComponent(columnKeys.join(','));
        return `/export?table=${encodeURIComponent(tableName)}&columns=${cols}`;
    }

    window.hookCsvExport = function (buttonSelector, tableName, tableSelector) {
        const btn = document.querySelector(buttonSelector);
        if (!btn) return;

        btn.addEventListener('click', function () {
            // jQuery DataTable instance
            const dt = $(tableSelector).DataTable();
            const cols = getColumnKeysInOrder(dt);
            // Fallback: if nothing detected (unlikely), let server use defaults.
            const url = cols.length
                ? buildExportUrl(tableName, cols)
                : `/export?table=${encodeURIComponent(tableName)}`;
            // Trigger download
            window.location.assign(url);
        });
    };
})();