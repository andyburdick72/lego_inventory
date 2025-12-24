'use client';

import { useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
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
import { formatNumber, isLightColor } from '@/lib/utils';
import Link from 'next/link';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import { DisabledInSafeMode } from '@/components/disabled-in-safe-mode';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  useElementStorageStrategies,
  ElementStorageStrategy,
} from '@/lib/hooks/use-storage-hierarchy';

type ViewMode = 'cards' | 'table';

export default function StorageHierarchyPage() {
  const { data: strategies, isLoading: strategiesLoading } = useElementStorageStrategies();
  const [strategyFilter, setStrategyFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useViewMode('table', 'storage-hierarchy-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);

  if (APP_SAFE_MODE) {
    return (
      <DisabledInSafeMode
        title="Storage Hierarchy Rules"
        backHref="/sets"
        backLabel="Back to Sets"
      />
    );
  }

  // Get unique strategy values for filter dropdown in specific order
  const uniqueStrategies = useMemo(() => {
    if (!strategies) return [];
    const strategySet = new Set(strategies.map(s => s.storage_strategy));
    const orderedStrategies = [
      'by_element',
      'by_part',
      'by_category_size',
      'by_category',
      'unknown',
      'unassigned',
      'in_putaway_bin',
    ];
    // Return ordered strategies that exist in the data, then any others
    const result = orderedStrategies.filter(s => strategySet.has(s));
    const remaining = Array.from(strategySet).filter(s => !orderedStrategies.includes(s));
    return result.concat(remaining);
  }, [strategies]);

  // Filter strategies by selected strategy type
  const filteredStrategies = useMemo(() => {
    if (!strategies) return [];
    if (strategyFilter === 'all') return strategies;
    return strategies.filter(s => s.storage_strategy === strategyFilter);
  }, [strategies, strategyFilter]);

  // Paginate cards
  const paginatedCards = useMemo(() => {
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return filteredStrategies.slice(startIndex, endIndex);
  }, [filteredStrategies, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil(filteredStrategies.length / cardPageSize);

  // Strategy color mapping
  const getStrategyColors = (strategy: string) => {
    const colors: Record<string, { bg: string; text: string; badge: string }> = {
      by_element: { bg: 'bg-blue-100', text: 'text-blue-800', badge: 'bg-blue-100 text-blue-800' },
      by_part: { bg: 'bg-green-100', text: 'text-green-800', badge: 'bg-green-100 text-green-800' },
      by_category_size: { bg: 'bg-purple-100', text: 'text-purple-800', badge: 'bg-purple-100 text-purple-800' },
      by_category: { bg: 'bg-orange-100', text: 'text-orange-800', badge: 'bg-orange-100 text-orange-800' },
      unassigned: { bg: 'bg-red-100', text: 'text-red-800', badge: 'bg-red-100 text-red-800' },
      unknown: { bg: 'bg-gray-100', text: 'text-gray-800', badge: 'bg-gray-100 text-gray-800' },
      in_putaway_bin: { bg: 'bg-yellow-100', text: 'text-yellow-800', badge: 'bg-yellow-100 text-yellow-800' },
    };
    return colors[strategy] || colors.unknown;
  };

  const getStrategyDisplayName = (strategy: string) => {
    if (strategy === 'by_category_size') return 'By Category + Size';
    if (strategy === 'in_putaway_bin') return 'In Putaway Bin';
    return strategy.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const strategyColumns: ColumnDef<ElementStorageStrategy>[] = useMemo(
    () => [
      {
        accessorKey: 'design_id',
        header: 'Part ID',
        cell: ({ row }) => {
          const strategy = row.original;
          return (
            <Link
              href={`/parts/${strategy.design_id}?from=storage-hierarchy`}
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              {strategy.design_id}
            </Link>
          );
        },
      },
      {
        accessorKey: 'part_name',
        header: 'Part Name',
      },
      {
        accessorKey: 'part_category_name',
        header: 'Category',
        cell: ({ row }) => {
          const strategy = row.original;
          if (!strategy.part_category_name) {
            return <span className="text-muted-foreground">—</span>;
          }
          return <span>{strategy.part_category_name}</span>;
        },
      },
      {
        id: 'color',
        header: 'Color',
        accessorFn: (row) => row.color_name || 'Unknown',
        cell: ({ row }) => {
          const strategy = row.original;
          const bgColor = strategy.color_hex ? `#${strategy.color_hex}` : '#ffffff';
          const textColor = isLightColor(strategy.color_hex) ? '#000000' : '#ffffff';
          return (
            <div
              className="inline-flex items-center px-2 py-1 rounded border"
              style={{
                backgroundColor: bgColor,
                color: textColor,
              }}
            >
              {strategy.color_name}
            </div>
          );
        },
      },
      {
        id: 'image',
        header: 'Image',
        cell: ({ row }) => {
          const strategy = row.original;
          if (!strategy.part_img_url) {
            return <span className="text-muted-foreground">—</span>;
          }
          return (
            <img
              src={strategy.part_img_url}
              alt={strategy.part_name || strategy.design_id}
              className="h-12 w-auto"
              onClick={(e) => e.stopPropagation()}
            />
          );
        },
      },
      {
        accessorKey: 'storage_strategy',
        header: 'Strategy',
        cell: ({ row }) => {
          const strategy = row.original.storage_strategy;
          const colors: Record<string, { bg: string; text: string }> = {
            by_element: { bg: 'bg-blue-100', text: 'text-blue-800' },
            by_part: { bg: 'bg-green-100', text: 'text-green-800' },
            by_category_size: { bg: 'bg-purple-100', text: 'text-purple-800' },
            by_category: { bg: 'bg-orange-100', text: 'text-orange-800' },
            unassigned: { bg: 'bg-red-100', text: 'text-red-800' },
            unknown: { bg: 'bg-gray-100', text: 'text-gray-800' },
            in_putaway_bin: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
          };
          const color = colors[strategy] || colors.unknown;
          const displayName = strategy === 'by_category_size' 
            ? 'By Category + Size'
            : strategy === 'in_putaway_bin'
            ? 'In Putaway Bin'
            : strategy.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          return (
            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${color.bg} ${color.text}`}>
              {displayName}
            </span>
          );
        },
      },
      {
        accessorKey: 'drawer_name',
        header: 'Drawer',
        cell: ({ row }) => {
          const strategy = row.original;
          if (!strategy.drawer_name) {
            return <span className="text-muted-foreground">—</span>;
          }
          if (strategy.drawer_id) {
            return (
              <Link
                href={`/drawers/${strategy.drawer_id}?from=storage-hierarchy`}
                className="text-blue-600 hover:text-blue-800 hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                {strategy.drawer_name}
              </Link>
            );
          }
          return <span>{strategy.drawer_name}</span>;
        },
      },
      {
        accessorKey: 'container_name',
        header: 'Container',
        cell: ({ row }) => {
          const strategy = row.original;
          if (!strategy.container_name) {
            return <span className="text-muted-foreground">—</span>;
          }
          if (strategy.container_id) {
            return (
              <Link
                href={`/containers/${strategy.container_id}?from=storage-hierarchy`}
                className="text-blue-600 hover:text-blue-800 hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                {strategy.container_name}
              </Link>
            );
          }
          return <span>{strategy.container_name}</span>;
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
    ],
    []
  );

  return (
    <div className="container mx-auto py-4 md:py-8">
      <div className="mb-4 md:mb-6 space-y-4">
        <Button variant="outline" asChild className="min-h-[44px]">
          <Link href="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Link>
        </Button>

        {/* Header Section */}
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <h1 className="text-2xl md:text-3xl font-bold">Storage Hierarchy Rules</h1>
            <ViewToggle
              viewMode={viewMode}
              onViewModeChange={(mode) => {
                setViewMode(mode);
                setCardPageIndex(0);
              }}
            />
          </div>
          
          <p className="text-muted-foreground">
            This analysis determines the storage strategy for each element (part + color), based on container and drawer naming patterns.
          </p>
          
          {strategies && (
            <p className="text-sm text-muted-foreground">
              Showing {formatNumber(filteredStrategies.length)} of {formatNumber(strategies.length)} elements
            </p>
          )}
        </div>

        {/* Filter */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-end gap-2">
          <span className="text-sm text-muted-foreground">Filter by Strategy:</span>
          <Select value={strategyFilter} onValueChange={setStrategyFilter}>
            <SelectTrigger className="w-full sm:w-[200px] min-h-[44px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Strategies</SelectItem>
              {uniqueStrategies.map((strategy) => (
                <SelectItem key={strategy} value={strategy}>
                  {getStrategyDisplayName(strategy)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {strategiesLoading ? (
        <div className="text-muted-foreground">Loading strategies...</div>
      ) : filteredStrategies && filteredStrategies.length > 0 ? (
        viewMode === 'table' ? (
          <DataTable
            columns={strategyColumns}
            data={filteredStrategies}
            searchKeys={['design_id', 'part_name', 'part_category_name', 'color', 'color_name', 'drawer_name', 'container_name']}
            searchPlaceholder="Search by part ID, name, color, drawer, or container..."
            exportFilename="storage-strategies"
            defaultSorting={[{ id: 'storage_strategy', desc: false }, { id: 'design_id', desc: false }]}
            numericColumns={['quantity']}
          />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {paginatedCards.map((strategy, index) => {
                const strategyColors = getStrategyColors(strategy.storage_strategy);
                const bgColor = strategy.color_hex ? `#${strategy.color_hex}` : '#ffffff';
                const textColor = isLightColor(strategy.color_hex) ? '#000000' : '#ffffff';
                
                return (
                  <Card key={`${strategy.design_id}-${strategy.color_id}-${index}`}>
                    <CardHeader>
                      <CardTitle className="text-sm">
                        <Link
                          href={`/parts/${strategy.design_id}?from=storage-hierarchy`}
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {strategy.design_id}
                        </Link>
                      </CardTitle>
                      <CardDescription className="text-xs">{strategy.part_name}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {strategy.part_img_url && (
                          <div className="flex justify-center">
                            <img
                              src={strategy.part_img_url}
                              alt={strategy.part_name || strategy.design_id}
                              className="h-24 w-auto"
                            />
                          </div>
                        )}
                        <div className="space-y-2 text-sm">
                          {strategy.part_category_name && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Category:</span>
                              <span className="font-medium">{strategy.part_category_name}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">Color:</span>
                            <div
                              className="inline-flex items-center px-2 py-1 rounded border"
                              style={{
                                backgroundColor: bgColor,
                                color: textColor,
                              }}
                            >
                              {strategy.color_name}
                            </div>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Strategy:</span>
                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${strategyColors.badge}`}>
                              {getStrategyDisplayName(strategy.storage_strategy)}
                            </span>
                          </div>
                          {strategy.drawer_name && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Drawer:</span>
                              {strategy.drawer_id ? (
                                <Link
                                  href={`/drawers/${strategy.drawer_id}?from=storage-hierarchy`}
                                  className="text-blue-600 hover:text-blue-800 hover:underline font-medium text-right"
                                >
                                  {strategy.drawer_name}
                                </Link>
                              ) : (
                                <span className="font-medium">{strategy.drawer_name}</span>
                              )}
                            </div>
                          )}
                          {strategy.container_name && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Container:</span>
                              {strategy.container_id ? (
                                <Link
                                  href={`/containers/${strategy.container_id}?from=storage-hierarchy`}
                                  className="text-blue-600 hover:text-blue-800 hover:underline font-medium text-right"
                                >
                                  {strategy.container_name}
                                </Link>
                              ) : (
                                <span className="font-medium">{strategy.container_name}</span>
                              )}
                            </div>
                          )}
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Quantity:</span>
                            <span className="font-medium">{formatNumber(strategy.quantity)}</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
            {/* Pagination controls for card view */}
            {totalPages > 1 && (
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-4">
                <div className="flex items-center gap-2">
                  <p className="text-sm text-muted-foreground">
                    Showing {formatNumber(cardPageIndex * cardPageSize + 1)} to{' '}
                    {formatNumber(Math.min((cardPageIndex + 1) * cardPageSize, filteredStrategies.length))}{' '}
                    of {formatNumber(filteredStrategies.length)} results
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCardPageIndex((prev) => Math.max(0, prev - 1))}
                    disabled={cardPageIndex === 0}
                    className="min-h-[44px] min-w-[44px]"
                  >
                    ←
                  </Button>
                  <p className="text-sm text-muted-foreground whitespace-nowrap">
                    Page {formatNumber(cardPageIndex + 1)} of {formatNumber(totalPages)}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCardPageIndex((prev) => Math.min(totalPages - 1, prev + 1))}
                    disabled={cardPageIndex >= totalPages - 1}
                    className="min-h-[44px] min-w-[44px]"
                  >
                    →
                  </Button>
                </div>
              </div>
            )}
          </>
        )
      ) : (
        <div className="text-muted-foreground">No storage strategies found.</div>
      )}
    </div>
  );
}

