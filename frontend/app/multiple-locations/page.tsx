'use client';

import { useState, useMemo } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { useMultipleLocationsElements, MultipleLocationsElement } from '@/lib/hooks/use-inventory';
import { ViewToggle } from '@/components/view-toggle';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { DataTable } from '@/components/data-table';
import { ExternalLink, ChevronDown, ChevronLeft, ChevronRight, Move, ArrowLeft, Edit, Trash2 } from 'lucide-react';
import { formatNumber, isLightColor } from '@/lib/utils';
import Link from 'next/link';
import {
  MoveInventoryDialog,
  UpdateQuantityDialog,
  DeleteInventoryDialog,
} from '@/components/loose-parts/loose-parts-dialogs';
import { LoosePart } from '@/lib/hooks/use-inventory';

export default function MultipleLocationsPage() {
  const { data: elements, isLoading, error } = useMultipleLocationsElements();
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedPartForMove, setSelectedPartForMove] = useState<LoosePart | null>(null);
  const [selectedPartForEdit, setSelectedPartForEdit] = useState<LoosePart | null>(null);
  const [selectedPartForDelete, setSelectedPartForDelete] = useState<LoosePart | null>(null);
  const [viewMode, setViewMode] = useViewMode('table', 'multiple-locations-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize] = useState(20);

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

  // Sort items for card view
  const sortedItems = useMemo(() => {
    return [...tableData].sort((a, b) => b.total_quantity - a.total_quantity);
  }, [tableData]);

  // Paginate cards
  const paginatedCards = useMemo(() => {
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return sortedItems.slice(startIndex, endIndex);
  }, [sortedItems, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil(sortedItems.length / cardPageSize);

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
    <div className="container mx-auto py-4 md:py-8">
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
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <CardTitle>Elements in Multiple Locations</CardTitle>
              <CardDescription>
                {viewMode === 'table' ? 'Click the arrow to expand and see all locations for each element' : 'Elements that exist in multiple locations'}
              </CardDescription>
            </div>
            <ViewToggle
              viewMode={viewMode}
              onViewModeChange={(mode) => {
                setViewMode(mode);
                setCardPageIndex(0);
              }}
            />
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : viewMode === 'table' ? (
            <DataTable
              columns={columns}
              data={tableData}
              searchKey="part_name"
              searchPlaceholder="Search by part name..."
              numericColumns={['location_count', 'total_quantity']}
            />
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {paginatedCards.map((element) => {
                  const bgColor = element.color_hex ? `#${element.color_hex}` : '#ffffff';
                  const textColor = isLightColor(element.color_hex) ? '#000000' : '#ffffff';
                  const key = `${element.design_id}-${element.color_id}`;
                  const isExpanded = expandedRows.has(key);
                  
                  return (
                    <Card key={key}>
                      <CardHeader>
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <CardTitle className="text-sm">
                              <Link
                                href={`/parts/${element.design_id}?from=multiple-locations`}
                                className="text-blue-600 hover:text-blue-800 hover:underline"
                              >
                                {element.design_id}
                              </Link>
                            </CardTitle>
                            <CardDescription className="text-xs mt-1">
                              {element.part_name}
                            </CardDescription>
                          </div>
                          {element.part_img_url && (
                            <img
                              src={element.part_img_url}
                              alt={element.part_name}
                              className="w-12 h-12 object-contain ml-2"
                            />
                          )}
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">Color:</span>
                          <div
                            className="inline-flex items-center px-2 py-1 rounded border text-xs"
                            style={{
                              backgroundColor: bgColor,
                              color: textColor,
                            }}
                          >
                            {element.color_name || 'Unknown'}
                          </div>
                        </div>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Locations:</span>
                            <span className="font-medium">{formatNumber(element.location_count)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Total Quantity:</span>
                            <span className="font-medium">{formatNumber(element.total_quantity)}</span>
                          </div>
                        </div>
                        {element.part_url && (
                          <div>
                            <a
                              href={element.part_url || `https://rebrickable.com/parts/${element.design_id}/`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1"
                            >
                              View on Rebrickable <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleRow(key)}
                          className="w-full min-h-[44px]"
                        >
                          {isExpanded ? (
                            <>
                              <ChevronDown className="h-4 w-4 mr-2" />
                              Hide Locations
                            </>
                          ) : (
                            <>
                              <ChevronRight className="h-4 w-4 mr-2" />
                              Show Locations ({element.locations.length})
                            </>
                          )}
                        </Button>
                        {isExpanded && element.locations.length > 0 && (
                          <div className="pt-2 border-t space-y-2">
                            <div className="text-xs font-medium text-muted-foreground mb-2">Locations:</div>
                            {element.locations.map((loc, idx) => {
                              const createLoosePart = (): LoosePart | null => {
                                if (!loc.inventory_id) return null;
                                return {
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
                              };

                              return (
                                <div key={idx} className="p-2 border rounded text-xs space-y-2">
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
                                    <span className="ml-auto font-medium">{formatNumber(loc.quantity)}</span>
                                  </div>
                                  {loc.inventory_id && (
                                    <div className="flex items-center gap-2 pt-1 border-t">
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                          const part = createLoosePart();
                                          if (part) {
                                            setSelectedPartForEdit(part);
                                            setEditDialogOpen(true);
                                          }
                                        }}
                                        className="flex-1 h-8 text-xs"
                                      >
                                        <Edit className="h-3 w-3 mr-1" />
                                        Edit
                                      </Button>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                          const part = createLoosePart();
                                          if (part) {
                                            setSelectedPartForMove(part);
                                            setMoveDialogOpen(true);
                                          }
                                        }}
                                        className="flex-1 h-8 text-xs"
                                      >
                                        <Move className="h-3 w-3 mr-1" />
                                        Move
                                      </Button>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                          const part = createLoosePart();
                                          if (part) {
                                            setSelectedPartForDelete(part);
                                            setDeleteDialogOpen(true);
                                          }
                                        }}
                                        className="flex-1 h-8 text-xs text-destructive hover:text-destructive"
                                      >
                                        <Trash2 className="h-3 w-3 mr-1" />
                                        Delete
                                      </Button>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
              {totalPages > 1 && (
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-4">
                  <div className="text-sm text-muted-foreground">
                    Showing {cardPageIndex * cardPageSize + 1} to{' '}
                    {Math.min((cardPageIndex + 1) * cardPageSize, sortedItems.length)} of{' '}
                    {sortedItems.length} items
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCardPageIndex(Math.max(0, cardPageIndex - 1))}
                      disabled={cardPageIndex === 0}
                      className="min-h-[44px] min-w-[44px]"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm whitespace-nowrap">
                      Page {cardPageIndex + 1} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCardPageIndex(Math.min(totalPages - 1, cardPageIndex + 1))}
                      disabled={cardPageIndex >= totalPages - 1}
                      className="min-h-[44px] min-w-[44px]"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
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
                  // Helper function to create a LoosePart object from location data
                  const createLoosePart = (): LoosePart | null => {
                    if (!loc.inventory_id) return null;
                    return {
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
                  };

                  const handleMove = () => {
                    const part = createLoosePart();
                    if (part) {
                      setSelectedPartForMove(part);
                      setMoveDialogOpen(true);
                    }
                  };

                  const handleEdit = () => {
                    const part = createLoosePart();
                    if (part) {
                      setSelectedPartForEdit(part);
                      setEditDialogOpen(true);
                    }
                  };

                  const handleDelete = () => {
                    const part = createLoosePart();
                    if (part) {
                      setSelectedPartForDelete(part);
                      setDeleteDialogOpen(true);
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
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleEdit}
                              className="flex items-center gap-1"
                            >
                              <Edit className="h-4 w-4" />
                              Edit
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleMove}
                              className="flex items-center gap-1"
                            >
                              <Move className="h-4 w-4" />
                              Move
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleDelete}
                              className="flex items-center gap-1 text-destructive hover:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                              Delete
                            </Button>
                          </div>
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
      <UpdateQuantityDialog
        part={selectedPartForEdit}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
      />
      <DeleteInventoryDialog
        part={selectedPartForDelete}
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
      />
    </div>
  );
}

