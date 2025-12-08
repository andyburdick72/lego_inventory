'use client';

import { useState, useMemo } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { useMultipleLocationsElements, MultipleLocationsElement } from '@/lib/hooks/use-inventory';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { DataTable } from '@/components/data-table';
import { ExternalLink, ChevronDown, ChevronRight, Move, ArrowLeft } from 'lucide-react';
import { formatNumber, isLightColor } from '@/lib/utils';
import Link from 'next/link';
import { MoveInventoryDialog } from '@/components/loose-parts/loose-parts-dialogs';
import { LoosePart } from '@/lib/hooks/use-inventory';

export default function MultipleLocationsPage() {
  const { data: elements, isLoading, error } = useMultipleLocationsElements();
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [selectedPartForMove, setSelectedPartForMove] = useState<LoosePart | null>(null);

  const toggleRow = (key: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedRows(newExpanded);
  };

  // Table columns
  const columns: ColumnDef<MultipleLocationsElement>[] = useMemo(
    () => [
      {
        id: 'expand',
        header: '',
        cell: ({ row }) => {
          const element = row.original;
          const key = `${element.design_id}-${element.color_id}`;
          const isExpanded = expandedRows.has(key);
          return (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => toggleRow(key)}
              className="h-8 w-8 p-0"
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          );
        },
      },
      {
        accessorKey: 'design_id',
        header: 'Part ID',
        cell: ({ row }) => {
          const element = row.original;
          return (
            <Link
              href={`/parts/${element.design_id}?from=multiple-locations`}
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              {element.design_id}
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
        accessorKey: 'color_name',
        accessorFn: (row) => row.color_name || 'Unknown',
        cell: ({ row }) => {
          const element = row.original;
          const bgColor = element.color_hex ? `#${element.color_hex}` : '#ffffff';
          const textColor = isLightColor(element.color_hex) ? '#000000' : '#ffffff';

          return (
            <div
              className="inline-flex items-center px-2 py-1 rounded border"
              style={{
                backgroundColor: bgColor,
                color: textColor,
              }}
            >
              {element.color_name || 'Unknown'}
            </div>
          );
        },
      },
      {
        id: 'image',
        header: 'Image',
        cell: ({ row }) => {
          const element = row.original;
          if (!element.part_img_url) {
            return <span className="text-muted-foreground">—</span>;
          }
          return (
            <img
              src={element.part_img_url}
              alt={element.part_name}
              className="h-16 w-auto"
              onClick={(e) => e.stopPropagation()}
            />
          );
        },
      },
      {
        accessorKey: 'location_count',
        header: 'Locations',
        cell: ({ row }) => {
          return (
            <div className="text-right font-medium">
              {formatNumber(row.original.location_count)}
            </div>
          );
        },
      },
      {
        accessorKey: 'total_quantity',
        header: 'Total Quantity',
        cell: ({ row }) => {
          return (
            <div className="text-right">
              {formatNumber(row.original.total_quantity)}
            </div>
          );
        },
      },
      {
        id: 'rebrickable',
        header: 'Rebrickable',
        cell: ({ row }) => {
          const element = row.original;
          const url = element.part_url || `https://rebrickable.com/parts/${element.design_id}/`;
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
    [expandedRows]
  );

  const tableData = useMemo(() => {
    return elements || [];
  }, [elements]);

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <h1 className="text-3xl font-bold mb-6">Same Element in Multiple Locations</h1>
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive">Error loading data: {String(error)}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const summary = useMemo(() => {
    if (!elements) return { total: 0, totalLocations: 0, totalQuantity: 0 };
    const total = elements.length;
    const totalLocations = elements.reduce((sum, e) => sum + e.location_count, 0);
    const totalQuantity = elements.reduce((sum, e) => sum + e.total_quantity, 0);
    return { total, totalLocations, totalQuantity };
  }, [elements]);

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/inventory-updates">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Inventory Updates
          </Link>
        </Button>
      </div>
      <h1 className="text-3xl font-bold mb-6">Same Element in Multiple Locations</h1>
      <p className="text-muted-foreground mb-8">
        Elements that exist in multiple non-put-away-bin locations.
      </p>

      <div className="grid gap-4 md:grid-cols-3 mb-8">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Total Elements</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">{formatNumber(summary.total)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Total Locations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(summary.totalLocations)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Total Quantity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(summary.totalQuantity)}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Elements in Multiple Locations</CardTitle>
          <CardDescription>
            Click the arrow to expand and see all locations for each element
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : (
            <DataTable
              columns={columns}
              data={tableData}
              searchKey="part_name"
              searchPlaceholder="Search by part name..."
              numericColumns={['location_count', 'total_quantity']}
            />
          )}
        </CardContent>
      </Card>

      {/* Expanded locations display */}
      {elements && elements.map((element) => {
        const key = `${element.design_id}-${element.color_id}`;
        if (!expandedRows.has(key)) return null;
        
        return (
          <Card key={key} className="mt-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                Locations for {element.part_name} ({element.color_name})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {element.locations.map((loc, idx) => {
                  const handleMove = () => {
                    if (loc.inventory_id) {
                      // Create a LoosePart-like object for the Move dialog
                      const partForMove: LoosePart = {
                        id: loc.inventory_id,
                        part_id: element.design_id,
                        color_id: element.color_id,
                        color_name: element.color_name,
                        color_hex: element.color_hex,
                        quantity: loc.quantity,
                        status: 'loose',
                        drawer_id: loc.drawer_id,
                        drawer_name: loc.drawer_name,
                        container_id: loc.container_id,
                        container_label: loc.container_name,
                        set_number: null,
                        set_name: null,
                        part_name: element.part_name,
                        image_url: element.part_img_url,
                        rebrickable_url: element.part_url,
                      };
                      setSelectedPartForMove(partForMove);
                      setMoveDialogOpen(true);
                    }
                  };

                  return (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 border rounded"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          {loc.drawer_id ? (
                            <Link
                              href={`/drawers/${loc.drawer_id}?from=multiple-locations`}
                              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                            >
                              {loc.drawer_name || 'Unknown'}
                            </Link>
                          ) : (
                            <span className="font-medium">{loc.drawer_name || 'Unknown'}</span>
                          )}
                          <span>/</span>
                          {loc.container_id ? (
                            <Link
                              href={`/containers/${loc.container_id}?from=multiple-locations`}
                              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                            >
                              {loc.container_name || 'Unknown'}
                            </Link>
                          ) : (
                            <span className="font-medium">{loc.container_name || 'Unknown'}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <span className="font-medium">{formatNumber(loc.quantity)}</span>
                        </div>
                        {loc.inventory_id && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleMove}
                            className="flex items-center gap-1"
                          >
                            <Move className="h-4 w-4" />
                            Move
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        );
      })}

      <MoveInventoryDialog
        part={selectedPartForMove}
        open={moveDialogOpen}
        onOpenChange={setMoveDialogOpen}
      />
    </div>
  );
}

