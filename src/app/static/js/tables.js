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
    function applyTdStyles($table) {
        $table.find('tbody td[data-td-style]').each(function () {
            var s = this.getAttribute('data-td-style');
            if (s) {
                this.setAttribute('style', s);
                this.removeAttribute('data-td-style');
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

        // Auto-detect columns that should never be searchable across the site
        // Rule: any header exactly "Total Quantity" or "Qty"
        var autoNon = [];
        $table.find('thead th').each(function (i) {
            var t = (this.textContent || '').trim().toLowerCase();
            if (t === 'total quantity' || t === 'qty') autoNon.push(i);
        });
        // Merge & dedupe with per-table nonsearchable indices
        nonSearchable = Array.from(new Set([].concat(nonSearchable, autoNon)));

        // Prepare orthogonal data BEFORE DT reads the DOM
        prepOrthogonal($table);
        applyTdStyles($table);

        var colCount = $table.find('thead th').length;

        // Per-table default ordering
        var defaultOrder = [];
        var tableId = $table.attr('id') || '';
        if (tableId === 'master_table') {
            // Qty is column index 5
            defaultOrder = [[5, 'desc']];
        } else if (tableId === 'set_parts_table') {
            // Qty is column index 3
            defaultOrder = [[3, 'desc']];
        } else if (tableId === 'container_parts_table') {
            // Qty is column index 3
            defaultOrder = [[3, 'desc']];
        }

        // Ensure the table has a <tfoot>; if missing, clone header row and clear cells
        if ($table.find('tfoot').length === 0) {
            var $tfoot = $('<tfoot></tfoot>');
            var $theadRow = $table.find('thead tr').first();
            var $tfootRow = $theadRow.clone();
            $tfootRow.find('th').each(function () {
                $(this).text('');
            });
            $tfoot.append($tfootRow);
            $table.append($tfoot);
        }

        var dt = $table.DataTable({
            pageLength: 25,
            paging: true,
            pagingType: 'full_numbers',
            ordering: true,
            order: defaultOrder,
            // Keep Actions (and other listed) non-searchable/orderable; mark Containers numeric
            columnDefs: (function () {
                var defs = [];

                // Respect per-table non-searchable indices (search disabled, sorting still allowed)
                if (nonSearchable.length) {
                    defs.push({ targets: nonSearchable, searchable: false });
                }

                // Build a header map once
                var headers = [];
                $table.find('thead th').each(function (i) {
                    headers[i] = (this.textContent || '').trim().toLowerCase();
                });

                // Auto-detect an Actions column and make it not orderable/searchable
                var actionsIdx = headers.indexOf('actions');
                if (actionsIdx !== -1) {
                    defs.push({ targets: actionsIdx, orderable: false, searchable: false });
                }

                // Auto-disable sorting/searching for any column that looks like a link or image
                headers.forEach(function (t, i) {
                    if (t.includes('link') || t.includes('image') || t === 'img') {
                        defs.push({ targets: i, orderable: false, searchable: false });
                    }
                });

                // Ensure numeric sorting for any column titled Total Quantity or Qty
                headers.forEach(function (t, i) {
                    if (t === 'total quantity' || t === 'qty') {
                        defs.push({ targets: i, type: 'num' });
                    }
                });

                // Fallback: if table has a second column, treat it as numeric (covers common "Containers" case)
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

                // Add draw event handler to compute and render column totals in tfoot
                api.on('draw', function () {
                    var footer = $table.find('tfoot tr').first();
                    var headers = [];
                    $table.find('thead th').each(function (i) {
                        headers[i] = (this.textContent || '').trim().toLowerCase();
                    });

                    // Set first column footer cell label
                    var $firstFooterCell = footer.find('th').eq(0);
                    if ($firstFooterCell.length === 0) {
                        $firstFooterCell = footer.find('td').eq(0);
                    }
                    if ($firstFooterCell.length) {
                        $firstFooterCell.text('Grand Total');
                    }

                    var totalCols = [];
                    headers.forEach(function (t, i) {
                        if (['qty', 'total pieces', 'total quantity', 'quantity', 'total parts'].includes(t)) {
                            totalCols.push(i);
                        }
                    });

                    if (totalCols.length === 0) {
                        $table.find('tfoot').hide();
                        return;
                    } else {
                        $table.find('tfoot').show();
                    }

                    function toNumber(val) {
                        if (val == null) return 0;
                        if (typeof val !== 'string') return Number(val) || 0;
                        // strip HTML tags
                        var text = val.replace(/<[^>]*>/g, '');
                        // remove thousands separators and non-numeric chars (except dot/minus)
                        text = text.replace(/,/g, '').replace(/[^0-9.\-]/g, '');
                        var n = parseFloat(text);
                        return isNaN(n) ? 0 : n;
                    }

                    totalCols.forEach(function (colIdx) {
                        var total = api.column(colIdx, { search: 'applied' }).data().reduce(function (sum, v) {
                            return sum + toNumber(v);
                        }, 0);
                        // Format total with comma separators
                        var formatted = total.toLocaleString(undefined, { maximumFractionDigits: 2 });
                        var $cell = footer.find('th').eq(colIdx);
                        if ($cell.length === 0) {
                            // If footer cell is td instead of th
                            $cell = footer.find('td').eq(colIdx);
                        }
                        if ($cell.length) {
                            $cell.text(formatted);
                        }
                    });
                });

                // Trigger initial draw to compute totals on load
                api.draw();
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