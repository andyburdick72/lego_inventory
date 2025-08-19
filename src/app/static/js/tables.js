(function () {
    function prepOrthogonal($table) {
        // For DOM-sourced cells, set data-order/data-search so sorting/filtering use clean text
        $table.find('tbody tr').each(function () {
            var $cells = $(this).children('td');
            if ($cells.length === 0) return;

            // Column 0: Drawer name (anchor) -> use text for search & sort
            if ($cells.length > 0) {
                var $name = $cells.eq(0);
                var nameText = $name.text().trim();
                $name.attr('data-order', nameText).attr('data-search', nameText);
            }
            // Column 1: Containers -> numeric order
            if ($cells.length > 1) {
                var $count = $cells.eq(1);
                var n = parseFloat(($count.text() || '').replace(/[^0-9.-]/g, '')) || 0;
                $count.attr('data-order', n);
            }
        });
    }

    function addFilterRow($table, api, nonSearchable) {
        var $thead = $table.find('thead');
        if ($thead.find('tr.dt-filters').length) return; // already added

        var $orig = $thead.find('tr').first();
        var $filter = $('<tr class="dt-filters" role="row"></tr>');

        $orig.find('th').each(function (i) {
            var $th = $('<th></th>');
            if (nonSearchable.indexOf(i) === -1) {
                $('<input type="text" placeholder="Search…" style="width:100%; box-sizing:border-box;">')
                    .appendTo($th)
                    .on('keyup change clear', function () {
                        if (api.column(i).search() !== this.value) {
                            api.column(i).search(this.value).draw();
                        }
                    });
            }
            $filter.append($th);
        });

        $thead.append($filter);
    }

    function already(table) {
        try { if ($.fn.dataTable && $.fn.dataTable.isDataTable(table)) return true; } catch (_) { }
        try { if (window.DataTable && window.DataTable.isDataTable && window.DataTable.isDataTable(table)) return true; } catch (_) { }
        return false;
    }

    function initOne(table) {
        if (already(table)) return;

        var $table = $(table);
        var nonSearchable = [];
        try { nonSearchable = JSON.parse($table.attr('data-nonsearchable') || '[]'); } catch (_) { }

        // Prepare orthogonal data BEFORE DT reads the DOM
        prepOrthogonal($table);

        var colCount = $table.find('thead th').length;

        var dt = $table.DataTable({
            pageLength: 25,
            paging: true,
            pagingType: 'full_numbers',
            ordering: true,
            order: [], // no default order
            // Keep Actions (and other listed) non-searchable/orderable; mark Containers numeric
            columnDefs: (function () {
                var defs = [];
                if (nonSearchable.length) {
                    defs.push({ targets: nonSearchable, searchable: false });
                }

                // Auto-detect an Actions column and make it not orderable/searchable
                var actionsIdx = -1;
                $table.find('thead th').each(function (i) {
                    var t = (this.textContent || '').trim().toLowerCase();
                    if (t === 'actions') { actionsIdx = i; }
                });
                if (actionsIdx !== -1) {
                    defs.push({ targets: actionsIdx, orderable: false, searchable: false });
                }
                if (colCount > 1) defs.push({ targets: 1, type: 'num' });
                return defs;
            })(),
            orderCellsTop: true,
            initComplete: function () {
                var api = this.api();
                addFilterRow($table, api, nonSearchable);

                // Export CSV button next to global filter
                var btn = $('<button type="button" class="export-csv" style="margin: 8px 8px 8px 0;">Export CSV</button>');
                var wrapper = $table.closest('.dataTables_wrapper');
                var filter = wrapper.find('.dataTables_filter');
                if (filter.length) { filter.prepend(btn); } else { $table.before(btn); }

                btn.on('click', function () {
                    var columns = api.settings()[0].aoColumns.map(function (col) {
                        var idx = col.idx;
                        return { data: col.mData || col.sName || col.sTitle || idx, name: col.sName || null, search: { value: api.column(idx).search() || '' } };
                    });
                    var order = (api.order() || []).map(function (pair) { return { column: pair[0], dir: pair[1] }; });
                    var state = { columns: columns, search: { value: api.search() || '' }, order: order };
                    var tableKey = $table.attr('data-tablekey') || '';
                    var contextJson = $table.attr('data-context') || '{}';
                    var url = new URL('/export', window.location.origin);
                    url.searchParams.set('table', tableKey);
                    url.searchParams.set('dt', JSON.stringify(state));
                    url.searchParams.set('ctx', contextJson);
                    window.location.href = url.toString();
                });
            }
        });
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