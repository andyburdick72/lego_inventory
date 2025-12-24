'use client';

import { DataTable } from '@/components/data-table';
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
import { ViewToggle } from '@/components/view-toggle';
import { PartCount, usePartCounts } from '@/lib/hooks/use-parts';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import { formatNumber } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

export default function PartCountsPage() {
  const searchParams = useSearchParams();
  const [viewMode, setViewMode] = useViewMode('table', 'part-counts-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const categoryFromUrl = searchParams.get('category');
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>(
    categoryFromUrl || 'all'
  );
  const router = useRouter();
  const { data: partCounts, isLoading, error } = usePartCounts();

  // Update selected category when URL parameter changes
  useEffect(() => {
    if (categoryFromUrl) {
      setSelectedCategoryId(categoryFromUrl);
    }
  }, [categoryFromUrl]);

  // Extract unique categories for filter dropdown
  const categories = useMemo(() => {
    if (!partCounts) return [];
    const categoryMap = new Map<number, string>();
    partCounts.forEach((part) => {
      if (part.part_category_id && part.part_category_name) {
        categoryMap.set(part.part_category_id, part.part_category_name);
      }
    });
    return Array.from(categoryMap.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [partCounts]);

  // Filter parts by selected category
  const filteredPartCounts = useMemo(() => {
    if (!partCounts) return [];
    if (selectedCategoryId === 'all') return partCounts;
    const categoryId = parseInt(selectedCategoryId, 10);
    return partCounts.filter((part) => part.part_category_id === categoryId);
  }, [partCounts, selectedCategoryId]);

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
        accessorKey: 'part_category_name',
        header: 'Category',
        cell: ({ row }) => {
          const category = row.original.part_category_name;
          return (
            <span className={category ? '' : 'text-muted-foreground'}>
              {category || '—'}
            </span>
          );
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

  // Pagination for card view (using filtered data)
  const paginatedCards = useMemo(() => {
    if (!filteredPartCounts) return [];
    const start = cardPageIndex * cardPageSize;
    const end = start + cardPageSize;
    return filteredPartCounts.slice(start, end);
  }, [filteredPartCounts, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((filteredPartCounts?.length || 0) / cardPageSize);

  // Reset to first page when filter changes
  useEffect(() => {
    setCardPageIndex(0);
  }, [selectedCategoryId]);

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
    () => filteredPartCounts?.reduce((sum, p) => sum + p.total_qty, 0) || 0,
    [filteredPartCounts]
  );

  return (
    <div className="container mx-auto py-4 md:py-8">
      <div className="mb-4 md:mb-6 space-y-4">
        <Button variant="outline" asChild className="min-h-[44px]">
          <Link href={APP_SAFE_MODE ? '/' : '/reporting-analytics'}>
            ← Back to {APP_SAFE_MODE ? 'Home' : 'Reporting & Analytics'}
          </Link>
        </Button>

        {/* Header Section - Better mobile layout */}
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <h1 className="text-2xl md:text-3xl font-bold">Part Counts</h1>
            <ViewToggle
              viewMode={viewMode}
              onViewModeChange={(mode) => {
                setViewMode(mode);
                setCardPageIndex(0);
              }}
            />
          </div>

          {/* Stats - One per line on mobile */}
          {!isLoading && partCounts && (
            <div className="flex flex-col gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Parts: </span>
                <span className="font-medium">{formatNumber(filteredPartCounts.length)}</span>
                {selectedCategoryId !== 'all' && (
                  <span className="text-muted-foreground ml-1">
                    (of {formatNumber(partCounts.length)})
                  </span>
                )}
              </div>
              <div>
                <span className="text-muted-foreground">Total Quantity: </span>
                <span className="font-medium">{formatNumber(totalParts)}</span>
              </div>
            </div>
          )}
          {isLoading && (
            <p className="text-muted-foreground">Loading...</p>
          )}

          {/* Category Filter - Full width on mobile */}
          {categories.length > 0 && (
            <div>
              <Select value={selectedCategoryId} onValueChange={setSelectedCategoryId}>
                <SelectTrigger className="w-full sm:w-[200px] min-h-[44px]">
                  <SelectValue placeholder="Filter by category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map((cat) => (
                    <SelectItem key={cat.id} value={cat.id.toString()}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
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
          data={filteredPartCounts || []}
          searchKeys={['design_id', 'part_name', 'part_category_name']}
          searchPlaceholder="Search by part ID, name, or category..."
          numericColumns={['total_qty']}
          defaultSorting={[{ id: 'total_qty', desc: true }]}
          onRowClick={(row) => {
            router.push(`/parts/${row.design_id}?from=part-counts`);
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
                      {part.part_category_name && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          {part.part_category_name}
                        </div>
                      )}
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
                {Math.min((cardPageIndex + 1) * cardPageSize, filteredPartCounts?.length || 0)} of{' '}
                {formatNumber(filteredPartCounts?.length || 0)} parts
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
