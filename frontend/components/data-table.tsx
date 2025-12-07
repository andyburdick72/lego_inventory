'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn, formatNumber, getStatusLabel } from '@/lib/utils';
import {
  ColumnDef,
  ColumnFiltersState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  PaginationState,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { useState } from 'react';

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  searchKey?: string; // Deprecated: use searchKeys instead
  searchKeys?: string[]; // Array of field keys to search across
  searchPlaceholder?: string;
  onRowClick?: (row: TData) => void;
  exportFilename?: string;
  defaultSorting?: SortingState;
  numericColumns?: string[]; // Column IDs that should be summed in totals row
  defaultPageSize?: number;
  hideTopBar?: boolean; // Hide the search and export button bar
}

export function DataTable<TData, TValue>({
  columns,
  data,
  searchKey,
  searchKeys,
  searchPlaceholder = 'Search...',
  onRowClick,
  exportFilename = 'export',
  defaultSorting = [],
  numericColumns = [],
  defaultPageSize = 20,
  hideTopBar = false,
}: DataTableProps<TData, TValue>) {
  // Support both searchKey (legacy) and searchKeys (new)
  const searchFields = searchKeys || (searchKey ? [searchKey] : []);
  const [sorting, setSorting] = useState<SortingState>(defaultSorting);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: defaultPageSize,
  });

  // Helper function to get column filter value
  const getColumnFilterValue = (columnId: string): string => {
    const filter = columnFilters.find((f) => f.id === columnId);
    return (filter?.value as string) || '';
  };

  // Helper function to set column filter value
  const setColumnFilterValue = (columnId: string, value: string) => {
    setColumnFilters((prev) => {
      const existing = prev.find((f) => f.id === columnId);
      if (existing) {
        if (value === '') {
          // Remove filter if empty
          return prev.filter((f) => f.id !== columnId);
        }
        // Update existing filter
        return prev.map((f) => (f.id === columnId ? { ...f, value } : f));
      } else {
        // Add new filter if value is not empty
        if (value === '') return prev;
        return [...prev, { id: columnId, value }];
      }
    });
    // Reset to first page when filtering
    setPagination((prev) => ({ ...prev, pageIndex: 0 }));
  };

  // Create maps for efficient lookup between column IDs and accessor keys
  const columnAccessorMap = new Map<string, string>(); // columnId -> accessorKey
  const accessorToColumnIdMap = new Map<string, string>(); // accessorKey -> columnId
  columns.forEach((col) => {
    const id = 'id' in col ? (col.id as string) : undefined;
    const accessorKey = 'accessorKey' in col ? (col.accessorKey as string) : undefined;
    if (id && accessorKey) {
      columnAccessorMap.set(id, accessorKey);
      accessorToColumnIdMap.set(accessorKey, id);
    } else if (accessorKey) {
      // If no explicit id, use accessorKey as both id and accessor
      columnAccessorMap.set(accessorKey, accessorKey);
      accessorToColumnIdMap.set(accessorKey, accessorKey);
    } else if (id) {
      // If no accessorKey but has id, use id as both
      columnAccessorMap.set(id, id);
      accessorToColumnIdMap.set(id, id);
    }
  });

  // Common column ID to data field mappings for columns without accessorKey
  const columnIdToFieldMap: Record<string, string[]> = {
    color: ['color_name', 'color'],
    drawer: ['drawer_name', 'drawer'],
    container: ['container_label', 'container_name', 'container'],
  };

  // Custom filter function for columns
  const columnFilterFn = (row: any, columnId: string, filterValue: any) => {
    if (!filterValue || (typeof filterValue === 'string' && filterValue.trim() === '')) return true;

    const searchTerm = String(filterValue).toLowerCase();
    const rowData = row.original as any;

    // Get the accessor key for this column, or use columnId as fallback
    let accessorKey = columnAccessorMap.get(columnId) || columnId;

    // Try to get value from row data using accessor key
    let value = rowData?.[accessorKey];

    // If not found and columnId has a mapping, try those fields
    if ((value === null || value === undefined) && columnIdToFieldMap[columnId]) {
      for (const field of columnIdToFieldMap[columnId]) {
        value = rowData?.[field];
        if (value !== null && value !== undefined) {
          accessorKey = field;
          break;
        }
      }
    }

    // If still not found, try getValue (for computed columns)
    if (value === null || value === undefined) {
      try {
        // Use the row's getValue method if available
        if (typeof row.getValue === 'function') {
          value = row.getValue(columnId);
        }
      } catch {
        // Column might not exist, skip it
        return false;
      }
    }

    if (value === null || value === undefined) return false;

    // Special handling for locations field: search through location objects
    if (columnId === 'locations' && Array.isArray(value)) {
      const locationStrings = value.map((loc: any) => {
        const parts: string[] = [];
        if (loc.drawer_name) parts.push(loc.drawer_name);
        if (loc.container_name) parts.push(loc.container_name);
        return parts.join(' / ');
      });
      const locationText = locationStrings.join(' ').toLowerCase();
      return locationText.includes(searchTerm);
    }

    // Handle different value types
    let stringValue = String(value).toLowerCase();

    // Special handling for status field: also search by status label
    if (columnId === 'status' && typeof value === 'string') {
      const statusLabel = getStatusLabel(value).toLowerCase();
      stringValue = `${stringValue} ${statusLabel}`;
    }

    return stringValue.includes(searchTerm);
  };

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onPaginationChange: setPagination,
    filterFns: {
      customFilter: columnFilterFn,
    },
    defaultColumn: {
      filterFn: 'customFilter',
    },
    state: {
      sorting,
      columnFilters,
      pagination,
    },
  });

  // Calculate totals for numeric columns
  const calculateTotals = () => {
    const totals: Record<string, number> = {};
    const filteredRows = table.getFilteredRowModel().rows;

    numericColumns.forEach((columnId) => {
      let sum = 0;
      filteredRows.forEach((row) => {
        const value = row.getValue(columnId);
        if (typeof value === 'number') {
          sum += value;
        } else if (typeof value === 'string') {
          // Try to parse string numbers (e.g., "1,234" -> 1234)
          const parsed = parseFloat(value.replace(/,/g, ''));
          if (!isNaN(parsed)) {
            sum += parsed;
          }
        }
      });
      totals[columnId] = sum;
    });
    return totals;
  };

  const totals = calculateTotals();

  const exportToCSV = () => {
    // Get headers from table columns
    const headers = table
      .getHeaderGroups()[0]
      .headers.filter((header) => header.id !== 'actions')
      .map((header) => {
        const headerValue = header.column.columnDef.header;
        if (typeof headerValue === 'string') return headerValue;
        // Try to get a readable name from the column id
        const id = header.column.id;
        return id
          .replace(/_/g, ' ')
          .replace(/([A-Z])/g, ' $1')
          .trim()
          .split(' ')
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' ');
      });

    // Get data rows - use accessorKey to get raw data values
    const rows = table.getFilteredRowModel().rows.map((row) => {
      return table
        .getHeaderGroups()[0]
        .headers.filter((header) => header.id !== 'actions')
        .map((header) => {
          const columnDef = header.column.columnDef;
          // Check if accessorKey exists in the column definition
          const accessorKey = 'accessorKey' in columnDef ? (columnDef.accessorKey as string) : undefined;
          if (accessorKey) {
            // Get raw value from the row data
            const rawValue = (row.original as any)[accessorKey];
            if (rawValue === null || rawValue === undefined) return '';
            return String(rawValue).replace(/"/g, '""');
          }
          // Fallback to getValue if no accessorKey
          const cellValue = row.getValue(header.column.id);
          if (cellValue === null || cellValue === undefined) return '';
          return String(cellValue).replace(/"/g, '""');
        });
    });

    const csvContent = [
      headers.map((h) => `"${h}"`).join(','),
      ...rows.map((row) => row.map((cell) => `"${cell}"`).join(',')),
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${exportFilename}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Check if a column is searchable based on its accessorKey or id
  const isColumnSearchable = (columnId: string, accessorKey?: string): boolean => {
    // Check if columnId or accessorKey is in searchFields
    // TanStack Table uses the column's id, which may be the accessorKey if no explicit id is set
    if (searchFields.includes(columnId)) return true;
    if (accessorKey && searchFields.includes(accessorKey)) return true;
    // Also check the mapped accessorKey from columnAccessorMap
    const mappedAccessorKey = columnAccessorMap.get(columnId);
    if (mappedAccessorKey && searchFields.includes(mappedAccessorKey)) return true;
    return false;
  };

  // Get column header labels for filter placeholders
  const getColumnHeaderLabel = (columnId: string): string => {
    const column = columns.find((col) => {
      const id = 'id' in col ? (col.id as string) : undefined;
      const accessorKey = 'accessorKey' in col ? (col.accessorKey as string) : undefined;
      return id === columnId || accessorKey === columnId;
    });
    if (!column) return columnId;
    const header = column.header;
    if (typeof header === 'string') return header;
    // Try to format the column ID as a readable label
    return columnId
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .trim()
      .split(' ')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <div className="space-y-4">
      {!hideTopBar && (
        <div className="flex items-center justify-end">
          <Button onClick={exportToCSV} variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      )}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const isNumeric = numericColumns.includes(header.column.id);
                  const columnId = header.column.id;
                  const isSearchable = searchFields.length > 0 && searchFields.includes(columnId);
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        header.column.getCanSort() && 'cursor-pointer select-none hover:bg-muted/50',
                        isNumeric && 'text-right'
                      )}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <div className={cn('flex items-center gap-2', isNumeric && 'justify-end')}>
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getCanSort() && (
                          <span className="text-xs">
                            {{
                              asc: '↑',
                              desc: '↓',
                            }[header.column.getIsSorted() as string] ?? '⇅'}
                          </span>
                        )}
                      </div>
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
            {/* Filter row */}
            {searchFields.length > 0 && (
              <TableRow>
                {table.getHeaderGroups()[0].headers.map((header) => {
                  const columnId = header.column.id;
                  const columnDef = header.column.columnDef;
                  const accessorKey = 'accessorKey' in columnDef ? (columnDef.accessorKey as string) : undefined;
                  // Check if this column is searchable (by columnId or accessorKey)
                  const isSearchable = isColumnSearchable(columnId, accessorKey);
                  const isNumeric = numericColumns.includes(columnId);
                  // Use columnId for the filter (TanStack Table uses column.id for filtering)
                  return (
                    <TableHead key={`filter-${header.id}`} className={cn(isNumeric && 'text-right')}>
                      {isSearchable ? (
                        <Input
                          placeholder={`Filter ${getColumnHeaderLabel(columnId)}...`}
                          value={getColumnFilterValue(columnId)}
                          onChange={(e) => setColumnFilterValue(columnId, e.target.value)}
                          className="h-8 w-full"
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <div className="h-8" />
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            )}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              <>
                {table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.id}
                    data-state={row.getIsSelected() && 'selected'}
                    className={cn(onRowClick && 'cursor-pointer hover:bg-muted/50')}
                    onClick={() => onRowClick?.(row.original)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
                {/* Totals row */}
                {numericColumns.length > 0 && (
                  <TableRow className="bg-muted/50 font-medium">
                    {table.getHeaderGroups()[0].headers.map((header, index) => {
                      const columnId = header.column.id;
                      if (columnId === 'actions') {
                        return <TableCell key={header.id}></TableCell>;
                      }
                      if (numericColumns.includes(columnId)) {
                        const total = totals[columnId] || 0;
                        return (
                          <TableCell key={header.id} className="font-semibold">
                            <div className="text-right">{total.toLocaleString()}</div>
                          </TableCell>
                        );
                      }
                      if (index === 0) {
                        return (
                          <TableCell key={header.id} className="font-semibold">
                            Total
                          </TableCell>
                        );
                      }
                      return <TableCell key={header.id}></TableCell>;
                    })}
                  </TableRow>
                )}
              </>
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {/* Pagination controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">
            Showing {formatNumber(table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1)} to{' '}
            {formatNumber(
              Math.min(
                (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
                table.getFilteredRowModel().rows.length
              )
            )}{' '}
            of {formatNumber(table.getFilteredRowModel().rows.length)} results
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <p className="text-sm text-muted-foreground">Rows per page:</p>
            <Select
              value={
                table.getState().pagination.pageSize >= table.getFilteredRowModel().rows.length
                  ? 'all'
                  : String(table.getState().pagination.pageSize)
              }
              onValueChange={(value) => {
                if (value === 'all') {
                  table.setPageSize(table.getFilteredRowModel().rows.length);
                } else {
                  table.setPageSize(Number(value));
                }
                table.setPageIndex(0); // Reset to first page when changing page size
              }}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
                <SelectItem value="all">All</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <p className="text-sm text-muted-foreground">
              Page {formatNumber(table.getState().pagination.pageIndex + 1)} of{' '}
              {formatNumber(table.getPageCount() > 0 ? table.getPageCount() : 1)}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

