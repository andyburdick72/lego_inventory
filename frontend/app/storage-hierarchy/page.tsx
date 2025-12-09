'use client';

import { useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Button } from '@/components/ui/button';
import { DataTable } from '@/components/data-table';
import { formatNumber, isLightColor } from '@/lib/utils';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
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

export default function StorageHierarchyPage() {
  const { data: strategies, isLoading: strategiesLoading } = useElementStorageStrategies();
  const [strategyFilter, setStrategyFilter] = useState<string>('all');

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
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Link>
        </Button>
      </div>

      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Storage Hierarchy Rules</h1>
        <p className="text-muted-foreground">
          How each element (part + color) is stored, based on container and drawer naming patterns.
          This analysis determines the storage strategy by examining container names for part numbers
          and color descriptions, and drawer names for "Really Useful" patterns.
        </p>
        {strategies && (
          <p className="text-sm text-muted-foreground mt-2">
            Showing {formatNumber(filteredStrategies.length)} of {formatNumber(strategies.length)} elements
          </p>
        )}
      </div>

      <div className="mb-4 flex items-center justify-end gap-2">
        <span className="text-sm text-muted-foreground">Filter by Strategy:</span>
        <Select value={strategyFilter} onValueChange={setStrategyFilter}>
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Strategies</SelectItem>
                  {uniqueStrategies.map((strategy) => {
                    const displayName = strategy === 'by_category_size' 
                      ? 'By Category + Size'
                      : strategy === 'in_putaway_bin'
                      ? 'In Putaway Bin'
                      : strategy.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    return (
                      <SelectItem key={strategy} value={strategy}>
                        {displayName}
                      </SelectItem>
                    );
                  })}
          </SelectContent>
        </Select>
      </div>

      {strategiesLoading ? (
        <div className="text-muted-foreground">Loading strategies...</div>
      ) : filteredStrategies && filteredStrategies.length > 0 ? (
        <DataTable
          columns={strategyColumns}
          data={filteredStrategies}
          searchKeys={['design_id', 'part_name', 'color', 'color_name', 'drawer_name', 'container_name']}
          searchPlaceholder="Search by part ID, name, color, drawer, or container..."
          exportFilename="storage-strategies"
          defaultSorting={[{ id: 'storage_strategy', desc: false }, { id: 'design_id', desc: false }]}
          numericColumns={['quantity']}
        />
      ) : (
        <div className="text-muted-foreground">No storage strategies found.</div>
      )}
    </div>
  );
}

