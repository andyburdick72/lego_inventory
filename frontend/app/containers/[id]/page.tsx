'use client';

import { DataTable } from '@/components/data-table';
import { DisabledInSafeMode } from '@/components/disabled-in-safe-mode';
import {
  DeleteInventoryDialog,
  MoveInventoryDialog,
  UpdateQuantityDialog,
} from '@/components/loose-parts/loose-parts-dialogs';
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
import { ContainerPart, useContainer, useContainerParts } from '@/lib/hooks/use-containers';
import { LoosePart, useLooseParts } from '@/lib/hooks/use-inventory';
import { usePutAwayBin, useSetPutAwayBin } from '@/lib/hooks/use-location-reconciliation';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import { formatNumber, isLightColor } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, Edit, ExternalLink, Move, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

export default function ContainerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const containerId = parseInt(params.id as string, 10);
  const [viewMode, setViewMode] = useViewMode('table', `container-${containerId}-view-mode`);
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const [backLink, setBackLink] = useState<{ href: string; label: string }>({
    href: '/drawers',
    label: 'Drawer',
  });

  const { data: container, isLoading: containerLoading } = useContainer(containerId);
  const { data: parts, isLoading: partsLoading } = useContainerParts(containerId);
  const { data: putAwayBin } = usePutAwayBin();
  const setPutAwayBinMutation = useSetPutAwayBin();
  const { data: allLooseParts } = useLooseParts();

  const isPutAwayBin = container?.is_put_away_bin === 1;

  // Map container parts to inventory items by matching design_id, color_id, and container_id
  const inventoryMap = useMemo(() => {
    if (!allLooseParts || !containerId) return new Map<string, LoosePart>();
    const map = new Map<string, LoosePart>();
    allLooseParts
      .filter(item => item.container_id === containerId)
      .forEach(item => {
        const key = `${item.part_id}-${item.color_id}`;
        map.set(key, item);
      });
    return map;
  }, [allLooseParts, containerId]);

  const [selectedPart, setSelectedPart] = useState<LoosePart | null>(null);
  const [updateQuantityOpen, setUpdateQuantityOpen] = useState(false);
  const [moveInventoryOpen, setMoveInventoryOpen] = useState(false);
  const [deleteInventoryOpen, setDeleteInventoryOpen] = useState(false);

  // Helper to get inventory item for a container part
  const getInventoryItem = (part: ContainerPart): LoosePart | null => {
    const key = `${part.design_id}-${part.color_id}`;
    return inventoryMap.get(key) || null;
  };

  // Determine back navigation based on referrer or query param
  useEffect(() => {
    if (!container) return;

    // Check for explicit 'from' query parameter first
    const fromParam = searchParams.get('from');
    if (fromParam) {
      const fromMap: Record<string, { href: string; label: string }> = {
        'drawers': { href: `/drawers/${container.drawer_id}`, label: 'Drawer' },
        'loose-parts': { href: '/loose-parts', label: 'Loose Parts' },
        'location-counts': { href: '/location-counts', label: 'Location Counts' },
        'storage-hierarchy': { href: '/storage-hierarchy', label: 'Storage Hierarchy Rules' },
        'putaway-wizard': { href: '/putaway-wizard', label: 'Put-Away Wizard' },
        'sets': { href: `/sets/${searchParams.get('set_number') || ''}`, label: 'Set' },
        'parts': {
          href: searchParams.get('design_id') ? `/parts/${searchParams.get('design_id')}` : '/loose-parts',
          label: 'Part',
        },
      };
      if (fromMap[fromParam]) {
        setBackLink(fromMap[fromParam]);
        return;
      }
    }

    // Fall back to checking document.referrer
    if (typeof window !== 'undefined' && document.referrer) {
      const referrer = new URL(document.referrer);
      const pathname = referrer.pathname;

      if (pathname.includes('/location-counts')) {
        setBackLink({ href: '/location-counts', label: 'Location Counts' });
      } else if (pathname.includes('/loose-parts')) {
        setBackLink({ href: '/loose-parts', label: 'Loose Parts' });
      } else if (pathname.includes('/parts/')) {
        // Extract part design_id from referrer if possible
        const partMatch = pathname.match(/\/parts\/([^/]+)/);
        if (partMatch) {
          setBackLink({ href: `/parts/${partMatch[1]}`, label: 'Part' });
        } else {
          setBackLink({ href: `/drawers/${container.drawer_id}`, label: 'Drawer' });
        }
      } else if (pathname.includes('/sets/')) {
        // Extract set number from referrer if possible
        const setMatch = pathname.match(/\/sets\/([^/]+)/);
        if (setMatch) {
          setBackLink({ href: `/sets/${setMatch[1]}`, label: 'Set' });
        } else {
          setBackLink({ href: `/drawers/${container.drawer_id}`, label: 'Drawer' });
        }
      } else if (pathname.includes('/drawers/')) {
        setBackLink({ href: `/drawers/${container.drawer_id}`, label: 'Drawer' });
      } else if (pathname.includes('/storage-hierarchy')) {
        setBackLink({ href: '/storage-hierarchy', label: 'Storage Hierarchy Rules' });
      } else if (pathname.includes('/putaway-wizard')) {
        setBackLink({ href: '/putaway-wizard', label: 'Put-Away Wizard' });
      }
      // Default is already set to drawer
    } else {
      // Default to drawer if no referrer
      setBackLink({ href: `/drawers/${container.drawer_id}`, label: 'Drawer' });
    }
  }, [container, searchParams]);

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

  const columns: ColumnDef<ContainerPart>[] = [
    {
      accessorKey: 'design_id',
      header: 'Part ID',
      cell: ({ row }) => {
        const part = row.original;
        return (
          <Link
            href={`/parts/${part.design_id}?from=containers&container_id=${containerId}`}
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
    },
    {
      id: 'color',
      header: 'Color',
      accessorFn: (row) => row.color_name || '',
      cell: ({ row }) => {
        const part = row.original;
        const bgColor = part.hex ? `#${part.hex}` : '#ffffff';
        const textColor = isLightColor(part.hex) ? '#000000' : '#ffffff';

        return (
          <div
            className="inline-flex items-center px-2 py-1 rounded border"
            style={{
              backgroundColor: bgColor,
              color: textColor,
            }}
          >
            {part.color_name}
          </div>
        );
      },
    },
    {
      id: 'image',
      header: 'Image',
      cell: ({ row }) => {
        const part = row.original;
        if (!part.part_img_url) return <span className="text-muted-foreground">—</span>;
        return (
          <img
            src={part.part_img_url}
            alt={part.part_name}
            className="h-12 w-auto"
            onClick={(e) => e.stopPropagation()}
          />
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
        if (!part.part_url) return <span className="text-muted-foreground">—</span>;
        return (
          <a
            href={part.part_url}
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
        const inventoryItem = getInventoryItem(part);
        if (!inventoryItem) return <span className="text-muted-foreground">—</span>;
        return (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedPart(inventoryItem);
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
                setSelectedPart(inventoryItem);
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
                setSelectedPart(inventoryItem);
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

  if (APP_SAFE_MODE) {
    return <DisabledInSafeMode title="Container Detail" backHref="/sets" backLabel="Back to Sets" />;
  }

  if (containerLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-muted-foreground">Loading container...</div>
      </div>
    );
  }

  if (!container) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-destructive">Container not found.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href={backLink.href}>
            ← Back to {backLink.label}
          </Link>
        </Button>
        <h1 className="text-3xl font-bold">
          {container.drawer_name} - {container.name}
        </h1>
        {container.description && (
          <p className="text-muted-foreground mt-2">{container.description}</p>
        )}
        {container.row_index !== null && container.col_index !== null && (
          <p className="text-muted-foreground mt-1 font-mono text-sm">
            Position: r{container.row_index} c{container.col_index}
          </p>
        )}
        <div className="flex gap-4 mt-4 items-center">
          <div className="flex gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Parts: </span>
              <span className="font-medium">{formatNumber(parts?.length || 0)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Total Quantity: </span>
              <span className="font-medium">
                {formatNumber(parts?.reduce((sum, p) => sum + p.quantity, 0) || 0)}
              </span>
            </div>
          </div>
          <div className="ml-auto">
            <Button
              variant={isPutAwayBin ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                if (containerId) {
                  setPutAwayBinMutation.mutate(containerId);
                }
              }}
              disabled={setPutAwayBinMutation.isPending}
            >
              {isPutAwayBin ? '✓ Put Away Bin' : 'Set as Put Away Bin'}
            </Button>
          </div>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
          <h2 className="text-2xl font-semibold">Parts</h2>
          <ViewToggle
            viewMode={viewMode}
            onViewModeChange={(mode) => {
              setViewMode(mode);
              setCardPageIndex(0);
            }}
          />
        </div>
        {partsLoading ? (
          <div className="text-muted-foreground">Loading parts...</div>
        ) : parts && parts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No parts in this container.
          </div>
        ) : viewMode === 'table' ? (
          <DataTable
            columns={columns}
            data={parts || []}
            searchKeys={['design_id', 'part_name', 'color', 'color_name']}
            searchPlaceholder="Search by part ID, name, or color..."
            exportFilename={`container-${containerId}-parts`}
            defaultSorting={[{ id: 'quantity', desc: true }]}
            numericColumns={['quantity']}
            defaultPageSize={20}
          />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {paginatedCards.map((part, index) => (
                <Card key={`${part.design_id}-${part.color_id}-${index}`}>
                  <CardHeader>
                    <CardTitle className="text-sm">
                      <Link
                        href={`/parts/${part.design_id}?from=containers&container_id=${containerId}`}
                        className="text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        {part.design_id}
                      </Link>
                    </CardTitle>
                    <CardDescription className="text-xs">{part.part_name}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {part.part_img_url && (
                        <div className="flex justify-center">
                          <img
                            src={part.part_img_url}
                            alt={part.part_name}
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
                              backgroundColor: part.hex ? `#${part.hex}` : '#ffffff',
                              color: isLightColor(part.hex) ? '#000000' : '#ffffff',
                            }}
                          >
                            {part.color_name}
                          </div>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Quantity:</span>
                          <span className="font-medium">{formatNumber(part.quantity)}</span>
                        </div>
                        {part.part_url && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="w-full"
                            asChild
                          >
                            <a
                              href={part.part_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              View on Rebrickable <ExternalLink className="h-3 w-3" />
                            </a>
                          </Button>
                        )}
                        {(() => {
                          const inventoryItem = getInventoryItem(part);
                          if (!inventoryItem) return null;
                          return (
                            <div className="flex gap-2 pt-2 border-t">
                              <Button
                                variant="outline"
                                size="sm"
                                className="flex-1"
                                onClick={() => {
                                  setSelectedPart(inventoryItem);
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
                                  setSelectedPart(inventoryItem);
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
                                  setSelectedPart(inventoryItem);
                                  setDeleteInventoryOpen(true);
                                }}
                                title="Delete"
                              >
                                <Trash2 className="h-3 w-3 mr-1" />
                                Delete
                              </Button>
                            </div>
                          );
                        })()}
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
                      setCardPageIndex(0);
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
      </div>
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
