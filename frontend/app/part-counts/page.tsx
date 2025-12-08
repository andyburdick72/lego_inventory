'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ColumnDef } from '@tanstack/react-table';
import { usePartCounts, PartCount } from '@/lib/hooks/use-parts';
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
import { formatNumber } from '@/lib/utils';
import Link from 'next/link';

type ViewMode = 'cards' | 'table';

export default function PartCountsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const router = useRouter();
  const { data: partCounts, isLoading, error } = usePartCounts();

  // Table columns
  const columns: ColumnDef<PartCount>[] = useMemo(
    () => [
      {
        accessorKey: 'design_id',
        header: 'Part ID',
        cell: ({ row }) => {
          const part = row.original;
          return (
            <Link
              href={`/parts/${part.design_id}?from=part-counts`}
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              {part.design_id}
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
        id: 'image',
        header: 'Image',
        cell: ({ row }) => {
          const part = row.original;
          if (!part.part_img_url) {
            return <span className="text-muted-foreground">—</span>;
          }
          return (
            <img
              src={part.part_img_url}
              alt={part.part_name}
              className="h-16 w-auto"
              onClick={(e) => e.stopPropagation()}
            />
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
          const part = row.original;
          const url = part.part_url || `https://rebrickable.com/parts/${part.design_id}/`;
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
    ],
    []
  );

  // Pagination for card view
  const paginatedCards = useMemo(() => {
    if (!partCounts) return [];
    const start = cardPageIndex * cardPageSize;
    const end = start + cardPageSize;
    return partCounts.slice(start, end);
  }, [partCounts, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((partCounts?.length || 0) / cardPageSize);

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-red-600">
          Error loading part counts: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    );
  }

  const totalParts = useMemo(
    () => partCounts?.reduce((sum, p) => sum + p.total_qty, 0) || 0,
    [partCounts]
  );

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/reporting-analytics">← Back to Reporting & Analytics</Link>
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Part Counts</h1>
            {!isLoading && partCounts && (
              <div className="flex gap-4 mt-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Parts: </span>
                  <span className="font-medium">{formatNumber(partCounts.length)}</span>
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
        <div className="text-muted-foreground">Loading part counts...</div>
      ) : partCounts && partCounts.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No parts found.
        </div>
      ) : viewMode === 'table' ? (
        <DataTable
          columns={columns}
          data={partCounts || []}
          searchKeys={['design_id', 'part_name']}
          searchPlaceholder="Search by part ID or name..."
          numericColumns={['total_qty']}
          defaultSorting={[{ id: 'total_qty', desc: true }]}
          onRowClick={(row) => {
            router.push(`/parts/${row.original.design_id}?from=part-counts`);
          }}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {paginatedCards.map((part) => (
              <Card
                key={part.design_id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => router.push(`/parts/${part.design_id}?from=part-counts`)}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg">
                        <Link
                          href={`/parts/${part.design_id}?from=part-counts`}
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {part.design_id}
                        </Link>
                      </CardTitle>
                      <CardDescription className="mt-1 line-clamp-2">
                        {part.part_name}
                      </CardDescription>
                    </div>
                    {part.part_img_url && (
                      <img
                        src={part.part_img_url}
                        alt={part.part_name}
                        className="h-12 w-auto ml-2"
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm text-muted-foreground">Total Quantity</div>
                      <div className="text-2xl font-bold">
                        {formatNumber(part.total_qty)}
                      </div>
                    </div>
                    {part.part_url && (
                      <a
                        href={part.part_url}
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
            ))}
          </div>

          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <div className="text-sm text-muted-foreground">
                Showing {cardPageIndex * cardPageSize + 1} to{' '}
                {Math.min((cardPageIndex + 1) * cardPageSize, partCounts?.length || 0)} of{' '}
                {formatNumber(partCounts?.length || 0)} parts
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
