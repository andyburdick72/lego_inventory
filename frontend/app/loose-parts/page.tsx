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
import { LayoutGrid, Table as TableIcon, ChevronLeft, ChevronRight, ExternalLink, Edit, Move, Trash2 } from 'lucide-react';
import { formatNumber, isLightColor } from '@/lib/utils';
import Link from 'next/link';
import {
  UpdateQuantityDialog,
  MoveInventoryDialog,
  DeleteInventoryDialog,
} from '@/components/loose-parts/loose-parts-dialogs';

type ViewMode = 'cards' | 'table';

export default function LoosePartsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const [selectedPart, setSelectedPart] = useState<LoosePart | null>(null);
  const [updateQuantityOpen, setUpdateQuantityOpen] = useState(false);
  const [moveInventoryOpen, setMoveInventoryOpen] = useState(false);
  const [deleteInventoryOpen, setDeleteInventoryOpen] = useState(false);

  const { data: parts, isLoading } = useLooseParts();

  // Calculate stats
  const stats = useMemo(() => {
    if (!parts) return { uniqueParts: 0, uniquePartColors: 0, total: 0 };
    const uniqueParts = new Set(parts.map(p => p.part_id)).size;
    const uniquePartColors = parts.length;
    const total = parts.reduce((sum, p) => sum + p.quantity, 0);
    return { uniqueParts, uniquePartColors, total };
  }, [parts]);

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
            href={`/parts/${part.part_id}?from=loose-parts`}
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
      accessorFn: (row) => row.color_name || 'Unknown',
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
    {
      id: 'drawer',
      header: 'Drawer',
      accessorFn: (row) => row.drawer_name || '',
      cell: ({ row }) => {
        const part = row.original;
        if (!part.drawer_id || !part.drawer_name) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <Link
            href={`/drawers/${part.drawer_id}?from=loose-parts`}
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
      accessorFn: (row) => row.container_label || '',
      cell: ({ row }) => {
        const part = row.original;
        if (!part.container_id || !part.container_label) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <Link
            href={`/containers/${part.container_id}?from=loose-parts`}
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
              className="text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              View <ExternalLink className="h-3 w-3" />
            </a>
          );
        },
      },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const part = row.original;
        return (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedPart(part);
                setUpdateQuantityOpen(true);
              }}
              title="Update quantity"
            >
              <Edit className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedPart(part);
                setMoveInventoryOpen(true);
              }}
              title="Move parts"
            >
              <Move className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedPart(part);
                setDeleteInventoryOpen(true);
              }}
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/">← Back to Home</Link>
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Loose Parts</h1>
            {!isLoading && parts && (
              <div className="flex gap-4 mt-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Unique Parts: </span>
                  <span className="font-medium">{formatNumber(stats.uniqueParts)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Unique Elements: </span>
                  <span className="font-medium">{formatNumber(stats.uniquePartColors)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Quantity: </span>
                  <span className="font-medium">{formatNumber(stats.total)}</span>
                </div>
              </div>
            )}
            {isLoading && (
              <p className="text-muted-foreground mt-1">Loading...</p>
            )}
          </div>
          <div className="flex items-center gap-2">
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
            searchKeys={['part_id', 'part_name', 'color', 'color_name', 'drawer', 'drawer_name', 'container', 'container_label', 'container_name']}
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
                        href={`/parts/${part.part_id}?from=loose-parts`}
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
                              href={`/drawers/${part.drawer_id}?from=loose-parts`}
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
                              href={`/containers/${part.container_id}?from=loose-parts`}
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
                              className="inline-flex items-center gap-1"
                            >
                              View on Rebrickable <ExternalLink className="h-3 w-3" />
                            </a>
                          </Button>
                        )}
                        <div className="flex gap-2 pt-2 border-t">
                          <Button
                            variant="outline"
                            size="sm"
                            className="flex-1"
                            onClick={() => {
                              setSelectedPart(part);
                              setUpdateQuantityOpen(true);
                            }}
                            title="Update quantity"
                          >
                            <Edit className="h-3 w-3 mr-1" />
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="flex-1"
                            onClick={() => {
                              setSelectedPart(part);
                              setMoveInventoryOpen(true);
                            }}
                            title="Move parts"
                          >
                            <Move className="h-3 w-3 mr-1" />
                            Move
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="flex-1"
                            onClick={() => {
                              setSelectedPart(part);
                              setDeleteInventoryOpen(true);
                            }}
                            title="Delete"
                          >
                            <Trash2 className="h-3 w-3 mr-1" />
                            Delete
                          </Button>
                        </div>
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
      <UpdateQuantityDialog
        part={selectedPart}
        open={updateQuantityOpen}
        onOpenChange={setUpdateQuantityOpen}
      />
      <MoveInventoryDialog
        part={selectedPart}
        open={moveInventoryOpen}
        onOpenChange={setMoveInventoryOpen}
      />
      <DeleteInventoryDialog
        part={selectedPart}
        open={deleteInventoryOpen}
        onOpenChange={setDeleteInventoryOpen}
      />
    </div>
  );
}
