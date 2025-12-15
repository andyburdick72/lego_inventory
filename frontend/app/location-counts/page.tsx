'use client';

import { useState, useMemo, ReactNode } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { useLocationCounts, LocationCount } from '@/lib/hooks/use-parts';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { DataTable } from '@/components/data-table';
import { ViewToggle } from '@/components/view-toggle';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { formatNumber } from '@/lib/utils';
import Link from 'next/link';

export default function LocationCountsPage() {
  const [viewMode, setViewMode] = useViewMode('table', 'location-counts-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const { data: locationCounts, isLoading, error } = useLocationCounts();

  // Table columns
  const columns: ColumnDef<LocationCount>[] = useMemo(
    () => [
      {
        accessorKey: 'location',
        header: 'Location',
        cell: ({ row }) => {
          const item = row.original;
          const parts: ReactNode[] = [];
          
          if (item.drawer_id && item.drawer_name) {
            parts.push(
              <Link
                key="drawer"
                href={`/drawers/${item.drawer_id}?from=location-counts`}
                className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                onClick={(e) => e.stopPropagation()}
              >
                {item.drawer_name}
              </Link>
            );
          } else if (item.drawer_name) {
            parts.push(<span key="drawer">{item.drawer_name}</span>);
          }
          
          if (item.container_id && item.container_name) {
            if (parts.length > 0) {
              parts.push(<span key="separator"> / </span>);
            }
            parts.push(
              <Link
                key="container"
                href={`/containers/${item.container_id}?from=location-counts`}
                className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                onClick={(e) => e.stopPropagation()}
              >
                {item.container_name}
              </Link>
            );
          } else if (item.container_name) {
            if (parts.length > 0) {
              parts.push(<span key="separator"> / </span>);
            }
            parts.push(<span key="container">{item.container_name}</span>);
          }
          
          if (parts.length === 0) {
            return <span className="text-muted-foreground">(unknown)</span>;
          }
          
          return <span className="font-medium">{parts}</span>;
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
    if (!locationCounts) return [];
    const start = cardPageIndex * cardPageSize;
    const end = start + cardPageSize;
    return locationCounts.slice(start, end);
  }, [locationCounts, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((locationCounts?.length || 0) / cardPageSize);

  const totalQuantity = useMemo(
    () => locationCounts?.reduce((sum, l) => sum + l.total_qty, 0) || 0,
    [locationCounts]
  );

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-red-600">
          Error loading location counts: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/reporting-analytics">← Back to Reporting & Analytics</Link>
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Storage Location Counts</h1>
            {!isLoading && locationCounts && (
              <div className="flex gap-4 mt-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Locations: </span>
                  <span className="font-medium">{formatNumber(locationCounts.length)}</span>
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
        <div className="text-muted-foreground">Loading location counts...</div>
      ) : locationCounts && locationCounts.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No locations found.
        </div>
      ) : viewMode === 'table' ? (
        <DataTable
          columns={columns}
          data={locationCounts || []}
          searchKeys={['location']}
          searchPlaceholder="Search by location..."
          numericColumns={['total_qty']}
          defaultSorting={[{ id: 'total_qty', desc: true }]}
          exportFilename="location-counts"
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {paginatedCards.map((location, index) => {
              const locationParts: React.ReactNode[] = [];
              
              if (location.drawer_id && location.drawer_name) {
                locationParts.push(
                  <Link
                    key="drawer"
                    href={`/drawers/${location.drawer_id}?from=location-counts`}
                    className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                  >
                    {location.drawer_name}
                  </Link>
                );
              } else if (location.drawer_name) {
                locationParts.push(<span key="drawer">{location.drawer_name}</span>);
              }
              
              if (location.container_id && location.container_name) {
                if (locationParts.length > 0) {
                  locationParts.push(<span key="separator"> / </span>);
                }
                locationParts.push(
                  <Link
                    key="container"
                    href={`/containers/${location.container_id}?from=location-counts`}
                    className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                  >
                    {location.container_name}
                  </Link>
                );
              } else if (location.container_name) {
                if (locationParts.length > 0) {
                  locationParts.push(<span key="separator"> / </span>);
                }
                locationParts.push(<span key="container">{location.container_name}</span>);
              }
              
              const locationDisplay = locationParts.length > 0 
                ? locationParts 
                : <span className="text-muted-foreground">(unknown)</span>;
              
              return (
                <Card key={`${location.location}-${index}`}>
                  <CardHeader>
                    <CardTitle className="text-lg">{locationDisplay}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div>
                      <div className="text-sm text-muted-foreground">Total Quantity</div>
                      <div className="text-2xl font-bold">
                        {formatNumber(location.total_qty)}
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
                {Math.min((cardPageIndex + 1) * cardPageSize, locationCounts?.length || 0)} of{' '}
                {formatNumber(locationCounts?.length || 0)} locations
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
