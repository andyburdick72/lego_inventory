(function () {
    function parseNonSearchable(attr) {
        if (!attr) return [];
        try { return JSON.parse(attr); } catch (_) { return []; }
    }

    function initOne(table) {
        if ($.fn.DataTable.isDataTable(table)) return; // guard against re-init

        const $table = $(table);
        const nonSearchable = parseNonSearchable($table.data('nonsearchable')); // e.g. "[4,5]"
        const defaultOpts = {
            columnDefs: nonSearchable.length ? [{ targets: nonSearchable, searchable: false }] : [],
            pageLength: 25,
            deferRender: true
        };

        $table.DataTable(defaultOpts);
    }

    function initAll() {
        document.querySelectorAll('table[data-tablekey]').forEach(initOne);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();