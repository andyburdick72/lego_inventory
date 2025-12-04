'use client';

import { useState, useMemo } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { useLooseParts, LoosePart } from '@/lib/hooks/use-inventory';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { DataTable } from '@/components/data-table';
import { LayoutGrid, Table as TableIcon, ChevronLeft, ChevronRight } from 'lucide-react';
import { formatNumber, isLightColor } from '@/lib/utils';
import Link from 'next/link';

type ViewMode = 'cards' | 'table';

export default function LoosePartsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);

  const { data: parts, isLoading } = useLooseParts();

  // Sort parts by quantity descending for card view
  const sortedParts = useMemo(() => {
    if (!parts) return [];
    return [...parts].sort((a, b) => b.quantity - a.quantity);
  }, [parts]);

  // Paginate cards
  const paginatedCards = useMemo(() => {
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return sortedParts.slice(startIndex, endIndex);
  }, [sortedParts, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil(sortedParts.length / cardPageSize);

  const columns: ColumnDef<LoosePart>[] = [
    {
      accessorKey: 'part_id',
      header: 'Part ID',
      cell: ({ row }) => {
        const part = row.original;
        return (
          <Link
            href={`/parts/${part.part_id}`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {part.part_id}
          </Link>
        );
      },
    },
    {
      accessorKey: 'part_name',
      header: 'Part Name',
    },
    {
      id: 'color',
      header: 'Color',
      cell: ({ row }) => {
        const part = row.original;
        const bgColor = part.color_hex ? `#${part.color_hex}` : '#ffffff';
        const textColor = isLightColor(part.color_hex) ? '#000000' : '#ffffff';
        
        return (
          <div
            className="inline-flex items-center px-2 py-1 rounded border"
            style={{
              backgroundColor: bgColor,
              color: textColor,
            }}
          >
            {part.color_name || 'Unknown'}
          </div>
        );
      },
    },
    {
      id: 'drawer',
      header: 'Drawer',
      cell: ({ row }) => {
        const part = row.original;
        if (!part.drawer_id || !part.drawer_name) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <Link
            href={`/drawers/${part.drawer_id}`}
            className="text-blue-600 hover:text-blue-800 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {part.drawer_name}
          </Link>
        );
      },
    },
    {
      id: 'container',
      header: 'Container',
      cell: ({ row }) => {
        const part = row.original;
        if (!part.container_id || !part.container_label) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <Link
            href={`/containers/${part.container_id}`}
            className="text-blue-600 hover:text-blue-800 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {part.container_label}
          </Link>
        );
      },
    },
    {
      accessorKey: 'quantity',
      header: 'Quantity',
      cell: ({ row }) => {
        return (
          <div className="text-right">
            {formatNumber(row.original.quantity)}
          </div>
        );
      },
    },
    {
      id: 'rebrickable_link',
      header: 'Rebrickable',
      cell: ({ row }) => {
        const part = row.original;
        if (!part.rebrickable_url) return <span className="text-muted-foreground">—</span>;
        return (
          <a
            href={part.rebrickable_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            View
          </a>
        );
      },
    },
    {
      id: 'image',
      header: 'Image',
      cell: ({ row }) => {
        const part = row.original;
        if (!part.image_url) return <span className="text-muted-foreground">—</span>;
        return (
          <img
            src={part.image_url}
            alt={part.part_name || part.part_id}
            className="h-12 w-auto"
            onClick={(e) => e.stopPropagation()}
          />
        );
      },
    },
  ];

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Loose Parts</h1>
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-semibold">All Parts</h2>
          <div className="flex items-center border rounded-md">
            <Button
              variant={viewMode === 'table' ? 'default' : 'ghost'}
              size="sm"
              className="rounded-r-none"
              onClick={() => {
                setViewMode('table');
                setCardPageIndex(0); // Reset pagination when switching views
              }}
            >
              <TableIcon className="h-4 w-4 mr-2" />
              Table
            </Button>
            <Button
              variant={viewMode === 'cards' ? 'default' : 'ghost'}
              size="sm"
              className="rounded-l-none"
              onClick={() => {
                setViewMode('cards');
                setCardPageIndex(0); // Reset pagination when switching views
              }}
            >
              <LayoutGrid className="h-4 w-4 mr-2" />
              Cards
            </Button>
          </div>
        </div>
        {isLoading ? (
          <div className="text-muted-foreground">Loading parts...</div>
        ) : parts && parts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No loose parts found.
          </div>
        ) : viewMode === 'table' ? (
          <DataTable
            columns={columns}
            data={parts || []}
            searchKeys={['part_id', 'part_name', 'color_name', 'drawer_name', 'container_label']}
            searchPlaceholder="Search by part ID, name, color, drawer, or container..."
            exportFilename="loose-parts"
            defaultSorting={[{ id: 'quantity', desc: true }]}
            numericColumns={['quantity']}
            defaultPageSize={20}
          />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {paginatedCards.map((part, index) => (
                <Card key={`${part.part_id}-${part.color_id}-${index}`}>
                  <CardHeader>
                    <CardTitle className="text-sm">
                      <Link
                        href={`/parts/${part.part_id}`}
                        className="text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        {part.part_id}
                      </Link>
                    </CardTitle>
                    <CardDescription className="text-xs">{part.part_name}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {part.image_url && (
                        <div className="flex justify-center">
                          <img
                            src={part.image_url}
                            alt={part.part_name || part.part_id}
                            className="h-24 w-auto"
                          />
                        </div>
                      )}
                      <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Color:</span>
                          <div
                            className="inline-flex items-center px-2 py-1 rounded border"
                            style={{
                              backgroundColor: part.color_hex ? `#${part.color_hex}` : '#ffffff',
                              color: isLightColor(part.color_hex) ? '#000000' : '#ffffff',
                            }}
                          >
                            {part.color_name || 'Unknown'}
                          </div>
                        </div>
                        {part.drawer_name && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Drawer:</span>
                            <Link
                              href={`/drawers/${part.drawer_id}`}
                              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                            >
                              {part.drawer_name}
                            </Link>
                          </div>
                        )}
                        {part.container_label && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Container:</span>
                            <Link
                              href={`/containers/${part.container_id}`}
                              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                            >
                              {part.container_label}
                            </Link>
                          </div>
                        )}
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Quantity:</span>
                          <span className="font-medium">{formatNumber(part.quantity)}</span>
                        </div>
                        {part.rebrickable_url && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="w-full"
                            asChild
                          >
                            <a
                              href={part.rebrickable_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              View on Rebrickable
                            </a>
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            {/* Pagination controls for card view */}
            <div className="flex items-center justify-between mt-4">
              <div className="flex items-center gap-2">
                <p className="text-sm text-muted-foreground">
                  Showing {formatNumber(cardPageIndex * cardPageSize + 1)} to{' '}
                  {formatNumber(Math.min((cardPageIndex + 1) * cardPageSize, sortedParts.length))}{' '}
                  of {formatNumber(sortedParts.length)} results
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <p className="text-sm text-muted-foreground">Cards per page:</p>
                  <Select
                    value={cardPageSize >= sortedParts.length ? 'all' : String(cardPageSize)}
                    onValueChange={(value) => {
                      if (value === 'all') {
                        setCardPageSize(sortedParts.length);
                      } else {
                        setCardPageSize(Number(value));
                      }
                      setCardPageIndex(0); // Reset to first page when changing page size
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
                    onClick={() => setCardPageIndex((prev) => Math.max(0, prev - 1))}
                    disabled={cardPageIndex === 0}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <p className="text-sm text-muted-foreground">
                    Page {formatNumber(cardPageIndex + 1)} of{' '}
                    {formatNumber(totalPages > 0 ? totalPages : 1)}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCardPageIndex((prev) => Math.min(totalPages - 1, prev + 1))}
                    disabled={cardPageIndex >= totalPages - 1}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
