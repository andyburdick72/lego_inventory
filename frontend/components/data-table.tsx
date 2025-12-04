'use client';

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
  ColumnFiltersState,
  getFilteredRowModel,
  getPaginationRowModel,
  PaginationState,
} from '@tanstack/react-table';
import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn, formatNumber } from '@/lib/utils';

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
}: DataTableProps<TData, TValue>) {
  // Support both searchKey (legacy) and searchKeys (new)
  const searchFields = searchKeys || (searchKey ? [searchKey] : []);
  const [sorting, setSorting] = useState<SortingState>(defaultSorting);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: defaultPageSize,
  });

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    globalFilterFn: (row, columnId, filterValue) => {
      if (searchFields.length === 0) return true;
      if (!filterValue) return true;
      
      const searchTerm = filterValue.toLowerCase();
      const rowData = row.original as any;
      
      // Search across all specified fields
      return searchFields.some((key) => {
        // Try to get value from row data directly (for accessorKey fields)
        let value = rowData?.[key];
        
        // If not found, try getValue (for computed columns)
        if (value === null || value === undefined) {
          try {
            value = row.getValue(key);
          } catch {
            // Column might not exist, skip it
            return false;
          }
        }
        
        if (value === null || value === undefined) return false;
        
        // Handle different value types
        const stringValue = String(value).toLowerCase();
        return stringValue.includes(searchTerm);
      });
    },
    state: {
      sorting,
      columnFilters,
      globalFilter,
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
          const accessorKey = columnDef.accessorKey as string;
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        {searchFields.length > 0 && (
          <Input
            placeholder={searchPlaceholder}
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="max-w-sm"
          />
        )}
        <Button onClick={exportToCSV} variant="outline" size="sm">
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const isNumeric = numericColumns.includes(header.column.id);
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

