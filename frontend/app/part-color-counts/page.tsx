'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ColumnDef } from '@tanstack/react-table';
import { usePartColorCounts, PartColorCount } from '@/lib/hooks/use-parts';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { DataTable } from '@/components/data-table';
import { LayoutGrid, Table as TableIcon, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import { formatNumber, isLightColor } from '@/lib/utils';
import Link from 'next/link';

type ViewMode = 'cards' | 'table';

export default function PartColorCountsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const router = useRouter();
  const { data: partColorCounts, isLoading, error } = usePartColorCounts();

  // Table columns
  const columns: ColumnDef<PartColorCount>[] = useMemo(
    () => [
      {
        accessorKey: 'design_id',
        header: 'Part ID',
        cell: ({ row }) => {
          const item = row.original;
          return (
            <Link
              href={`/parts/${item.design_id}?from=part-color-counts`}
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              {item.design_id}
            </Link>
          );
        },
      },
      {
        accessorKey: 'part_name',
        header: 'Part Name',
        cell: ({ row }) => {
          return <span>{row.original.part_name}</span>;
        },
      },
      {
        id: 'color',
        header: 'Color',
        cell: ({ row }) => {
          const item = row.original;
          const hex = item.hex;
          const hexWithHash = hex ? (hex.startsWith('#') ? hex : `#${hex}`) : null;
          if (!hexWithHash) {
            return <span>{item.color_name || '—'}</span>;
          }
          const isLight = isLightColor(hexWithHash);
          return (
            <div
              className="inline-flex items-center gap-2 px-2 py-1 rounded text-sm font-medium"
              style={{
                backgroundColor: hexWithHash,
                color: isLight ? '#000000' : '#ffffff',
              }}
            >
              {item.color_name || '—'}
            </div>
          );
        },
      },
      {
        accessorKey: 'total_qty',
        header: 'Total Quantity',
        cell: ({ row }) => {
          return (
            <div className="text-right">
              {formatNumber(row.original.total_qty)}
            </div>
          );
        },
      },
      {
        id: 'rebrickable',
        header: 'Rebrickable',
        cell: ({ row }) => {
          const item = row.original;
          const url = item.part_url || `https://rebrickable.com/parts/${item.design_id}/${item.color_id}/`;
          return (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              View <ExternalLink className="h-3 w-3" />
            </a>
          );
        },
      },
      {
        id: 'image',
        header: 'Image',
        cell: ({ row }) => {
          const item = row.original;
          if (!item.part_img_url) {
            return <span className="text-muted-foreground">—</span>;
          }
          return (
            <img
              src={item.part_img_url}
              alt={item.part_name}
              className="h-16 w-auto"
              onClick={(e) => e.stopPropagation()}
            />
          );
        },
      },
    ],
    []
  );

  // Pagination for card view
  const paginatedCards = useMemo(() => {
    if (!partColorCounts) return [];
    const start = cardPageIndex * cardPageSize;
    const end = start + cardPageSize;
    return partColorCounts.slice(start, end);
  }, [partColorCounts, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((partColorCounts?.length || 0) / cardPageSize);

  const totalParts = useMemo(
    () => partColorCounts?.reduce((sum, p) => sum + p.total_qty, 0) || 0,
    [partColorCounts]
  );

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-red-600">
          Error loading part color counts: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/">← Back to Home</Link>
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Part + Color Counts</h1>
            {!isLoading && partColorCounts && (
              <div className="flex gap-4 mt-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Parts + Colors: </span>
                  <span className="font-medium">{formatNumber(partColorCounts.length)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Quantity: </span>
                  <span className="font-medium">{formatNumber(totalParts)}</span>
                </div>
              </div>
            )}
            {isLoading && (
              <p className="text-muted-foreground mt-1">Loading...</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={viewMode === 'table' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('table')}
            >
              <TableIcon className="h-4 w-4 mr-2" />
              Table
            </Button>
            <Button
              variant={viewMode === 'cards' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('cards')}
            >
              <LayoutGrid className="h-4 w-4 mr-2" />
              Cards
            </Button>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-muted-foreground">Loading part color counts...</div>
      ) : partColorCounts && partColorCounts.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No parts found.
        </div>
      ) : viewMode === 'table' ? (
        <DataTable
          columns={columns}
          data={partColorCounts || []}
          searchKeys={['design_id', 'part_name', 'color_name']}
          searchPlaceholder="Search by part ID, name, or color..."
          numericColumns={['total_qty']}
          defaultSorting={[{ id: 'total_qty', desc: true }]}
          onRowClick={(row) => {
            router.push(`/parts/${row.original.design_id}?from=part-color-counts`);
          }}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {paginatedCards.map((item, index) => {
              const hex = item.hex;
              const hexWithHash = hex ? (hex.startsWith('#') ? hex : `#${hex}`) : null;
              const isLight = hexWithHash ? isLightColor(hexWithHash) : false;
              
              return (
                <Card
                  key={`${item.design_id}-${item.color_id}-${index}`}
                  className="cursor-pointer hover:shadow-lg transition-shadow"
                  onClick={() => router.push(`/parts/${item.design_id}?from=part-color-counts`)}
                >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <CardTitle className="text-lg">
                          <Link
                            href={`/parts/${item.design_id}?from=part-color-counts`}
                            className="text-blue-600 hover:text-blue-800 hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {item.design_id}
                          </Link>
                        </CardTitle>
                        <CardDescription className="mt-1 line-clamp-2">
                          {item.part_name}
                        </CardDescription>
                      </div>
                      {item.part_img_url && (
                        <img
                          src={item.part_img_url}
                          alt={item.part_name}
                          className="h-12 w-auto ml-2"
                          onClick={(e) => e.stopPropagation()}
                        />
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <div className="text-sm text-muted-foreground mb-1">Color</div>
                        {hexWithHash ? (
                          <div
                            className="inline-flex items-center px-2 py-1 rounded text-sm font-medium"
                            style={{
                              backgroundColor: hexWithHash,
                              color: isLight ? '#000000' : '#ffffff',
                            }}
                          >
                            {item.color_name || '—'}
                          </div>
                        ) : (
                          <span className="text-sm">{item.color_name || '—'}</span>
                        )}
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">Total Quantity</div>
                        <div className="text-2xl font-bold">
                          {formatNumber(item.total_qty)}
                        </div>
                      </div>
                      {item.part_url && (
                        <a
                          href={item.part_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <div className="text-sm text-muted-foreground">
                Showing {cardPageIndex * cardPageSize + 1} to{' '}
                {Math.min((cardPageIndex + 1) * cardPageSize, partColorCounts?.length || 0)} of{' '}
                {formatNumber(partColorCounts?.length || 0)} parts
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCardPageIndex((prev) => Math.max(0, prev - 1))}
                  disabled={cardPageIndex === 0}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                <div className="text-sm">
                  Page {cardPageIndex + 1} of {totalPages}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setCardPageIndex((prev) => Math.min(totalPages - 1, prev + 1))
                  }
                  disabled={cardPageIndex >= totalPages - 1}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
