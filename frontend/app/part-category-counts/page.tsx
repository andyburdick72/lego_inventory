'use client';

import { DataTable } from '@/components/data-table';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { ViewToggle } from '@/components/view-toggle';
import { PartCategoryCount, usePartCategoryCounts } from '@/lib/hooks/use-parts';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import { formatNumber } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';

export default function PartCategoryCountsPage() {
  const [viewMode, setViewMode] = useViewMode('table', 'part-category-counts-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const router = useRouter();
  const { data: categoryCounts, isLoading, error } = usePartCategoryCounts();

  // Table columns
  const columns: ColumnDef<PartCategoryCount>[] = useMemo(
    () => [
      {
        accessorKey: 'part_category_name',
        header: 'Category',
        cell: ({ row }) => {
          const category = row.original;
          const categoryName = category.part_category_name || 'Uncategorized';
          const categoryId = category.part_category_id;

          if (categoryId) {
            return (
              <Link
                href={`/part-counts?category=${categoryId}`}
                className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                onClick={(e) => e.stopPropagation()}
              >
                {categoryName}
              </Link>
            );
          }
          return <span className="font-medium">{categoryName}</span>;
        },
      },
      {
        accessorKey: 'part_count',
        header: 'Part Count',
        cell: ({ row }) => {
          return (
            <div className="text-right">
              {formatNumber(row.original.part_count)}
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
    ],
    []
  );

  // Pagination for card view
  const paginatedCards = useMemo(() => {
    if (!categoryCounts) return [];
    const start = cardPageIndex * cardPageSize;
    const end = start + cardPageSize;
    return categoryCounts.slice(start, end);
  }, [categoryCounts, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((categoryCounts?.length || 0) / cardPageSize);

  const totalParts = useMemo(
    () => categoryCounts?.reduce((sum, c) => sum + c.part_count, 0) || 0,
    [categoryCounts]
  );

  const totalQuantity = useMemo(
    () => categoryCounts?.reduce((sum, c) => sum + c.total_qty, 0) || 0,
    [categoryCounts]
  );

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-red-600">
          Error loading part category counts: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href={APP_SAFE_MODE ? '/' : '/reporting-analytics'}>
            ← Back to {APP_SAFE_MODE ? 'Home' : 'Reporting & Analytics'}
          </Link>
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Part Category Counts</h1>
            {!isLoading && categoryCounts && (
              <div className="flex gap-4 mt-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Categories: </span>
                  <span className="font-medium">{formatNumber(categoryCounts.length)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Parts: </span>
                  <span className="font-medium">{formatNumber(totalParts)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Quantity: </span>
                  <span className="font-medium">{formatNumber(totalQuantity)}</span>
                </div>
              </div>
            )}
            {isLoading && (
              <p className="text-muted-foreground mt-1">Loading...</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <ViewToggle
              viewMode={viewMode}
              onViewModeChange={(mode) => {
                setViewMode(mode);
                setCardPageIndex(0);
              }}
            />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-muted-foreground">Loading part category counts...</div>
      ) : categoryCounts && categoryCounts.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No categories found.
        </div>
      ) : viewMode === 'table' ? (
        <DataTable
          columns={columns}
          data={categoryCounts || []}
          searchKeys={['part_category_name']}
          searchPlaceholder="Search by category name..."
          numericColumns={['part_count', 'total_qty']}
          defaultSorting={[{ id: 'total_qty', desc: true }]}
          exportFilename="part-category-counts"
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {paginatedCards.map((category, index) => {
              const categoryName = category.part_category_name || 'Uncategorized';
              const categoryId = category.part_category_id;

              return (
                <Card
                  key={`${category.part_category_id || 'uncategorized'}-${index}`}
                  className={categoryId ? "cursor-pointer hover:shadow-lg transition-shadow" : ""}
                  onClick={() => {
                    if (categoryId) {
                      router.push(`/part-counts?category=${categoryId}`);
                    }
                  }}
                >
                  <CardHeader>
                    <CardTitle className="text-lg">
                      {categoryId ? (
                        <Link
                          href={`/part-counts?category=${categoryId}`}
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {categoryName}
                        </Link>
                      ) : (
                        categoryName
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div>
                        <div className="text-sm text-muted-foreground">Part Count</div>
                        <div className="text-xl font-bold">
                          {formatNumber(category.part_count)}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">Total Quantity</div>
                        <div className="text-xl font-bold">
                          {formatNumber(category.total_qty)}
                        </div>
                      </div>
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
                {Math.min((cardPageIndex + 1) * cardPageSize, categoryCounts?.length || 0)} of{' '}
                {formatNumber(categoryCounts?.length || 0)} categories
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
