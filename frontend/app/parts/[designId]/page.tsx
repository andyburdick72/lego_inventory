'use client';

import { DataTable } from '@/components/data-table';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { ViewToggle } from '@/components/view-toggle';
import {
  InventoryItem,
  PartInSet,
  useLooseInventoryForPart,
  usePart,
  usePartAliases,
  useSetsForPart,
  useUpdatePart,
} from '@/lib/hooks/use-parts';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { formatNumber, getStatusLabel, isLightColor } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

export default function PartDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const designId = params.designId as string;
  const [activeTab, setActiveTab] = useState<'loose' | 'sets'>(APP_SAFE_MODE ? 'sets' : 'loose');
  const [looseViewMode, setLooseViewMode] = useViewMode('table', `part-${designId}-loose-view-mode`);
  const [setsViewMode, setSetsViewMode] = useViewMode('table', `part-${designId}-sets-view-mode`);
  const [looseCardPageIndex, setLooseCardPageIndex] = useState(0);
  const [setsCardPageIndex, setSetsCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const [backLink, setBackLink] = useState<{ href: string; label: string }>({
    href: APP_SAFE_MODE ? '/sets' : '/loose-parts',
    label: APP_SAFE_MODE ? 'Sets' : 'Loose Parts',
  });

  // Determine back navigation based on referrer or query param
  useEffect(() => {
    // Check for explicit 'from' query parameter first
    const fromParam = searchParams.get('from');
    if (fromParam) {
      const fromMap: Record<string, { href: string; label: string }> = {
        'loose-parts': { href: '/loose-parts', label: 'Loose Parts' },
        'part-counts': { href: '/part-counts', label: 'Part Counts' },
        'part-color-counts': { href: '/part-color-counts', label: 'Element Counts' },
        'location-reconciliation': { href: '/location-reconciliation', label: 'Location Reconciliation' },
        'storage-hierarchy': { href: '/storage-hierarchy', label: 'Storage Hierarchy Rules' },
        'putaway-wizard': { href: '/putaway-wizard', label: 'Put-Away Wizard' },
        'sets': {
          href: searchParams.get('set_number') ? `/sets/${searchParams.get('set_number')}` : '/sets',
          label: 'Set',
        },
        'containers': {
          href: searchParams.get('container_id') ? `/containers/${searchParams.get('container_id')}` : '/containers',
          label: 'Container',
        },
        'drawers': {
          href: searchParams.get('drawer_id') ? `/drawers/${searchParams.get('drawer_id')}` : '/drawers',
          label: 'Drawer',
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

      if (pathname.includes('/part-counts')) {
        setBackLink({ href: '/part-counts', label: 'Part Counts' });
      } else if (pathname.includes('/part-color-counts')) {
        setBackLink({ href: '/part-color-counts', label: 'Element Counts' });
      } else if (pathname.includes('/sets/')) {
        // Extract set number from referrer if possible
        const setMatch = pathname.match(/\/sets\/([^/]+)/);
        if (setMatch) {
          setBackLink({ href: `/sets/${setMatch[1]}`, label: 'Set' });
        } else {
          setBackLink({ href: '/sets', label: 'Sets' });
        }
      } else if (pathname.includes('/containers/')) {
        // Extract container ID from referrer if possible
        const containerMatch = pathname.match(/\/containers\/(\d+)/);
        if (containerMatch) {
          setBackLink({ href: `/containers/${containerMatch[1]}`, label: 'Container' });
        } else {
          setBackLink({ href: '/containers', label: 'Containers' });
        }
      } else if (pathname.includes('/drawers/')) {
        // Extract drawer ID from referrer if possible
        const drawerMatch = pathname.match(/\/drawers\/(\d+)/);
        if (drawerMatch) {
          setBackLink({ href: `/drawers/${drawerMatch[1]}`, label: 'Drawer' });
        } else {
          setBackLink({ href: '/drawers', label: 'Drawers' });
        }
      } else if (pathname.includes('/loose-parts')) {
        setBackLink({ href: '/loose-parts', label: 'Loose Parts' });
      } else if (pathname.includes('/storage-hierarchy')) {
        setBackLink({ href: '/storage-hierarchy', label: 'Storage Hierarchy Rules' });
      } else if (pathname.includes('/putaway-wizard')) {
        setBackLink({ href: '/putaway-wizard', label: 'Put-Away Wizard' });
      }
      // Default is already set to loose-parts
    }
  }, [searchParams]);

  useEffect(() => {
    // In safe mode we don't render tabs at all; ensure we never get stuck on the loose view state.
    if (APP_SAFE_MODE && activeTab !== 'sets') {
      setActiveTab('sets');
    }
  }, [activeTab]);

  const { data: part, isLoading: partLoading } = usePart(designId);
  const { data: looseInventory, isLoading: looseLoading } =
    useLooseInventoryForPart(designId);
  const { data: sets, isLoading: setsLoading } = useSetsForPart(designId);
  const { data: aliases } = usePartAliases(designId);
  const updatePartMutation = useUpdatePart(designId);

  // Calculate totals
  const totalLooseQty =
    looseInventory?.reduce((sum, item) => sum + item.quantity, 0) || 0;
  const totalInSetsQty = sets?.reduce((sum, set) => sum + set.quantity, 0) || 0;
  // Total = In Sets (not loose + in sets, since loose parts are already in sets)
  const totalQty = totalInSetsQty;

  // Sort loose inventory by quantity descending (for both table and card view)
  const sortedLoose = useMemo(() => {
    if (!looseInventory) return [];
    return [...looseInventory].sort((a, b) => b.quantity - a.quantity);
  }, [looseInventory]);

  // Sort sets by quantity descending (for both table and card view)
  const sortedSets = useMemo(() => {
    if (!sets) return [];
    return [...sets].sort((a, b) => b.quantity - a.quantity);
  }, [sets]);

  // Paginate loose cards
  const paginatedLooseCards = useMemo(() => {
    const startIndex = looseCardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return sortedLoose.slice(startIndex, endIndex);
  }, [sortedLoose, looseCardPageIndex, cardPageSize]);

  // Paginate sets cards
  const paginatedSetsCards = useMemo(() => {
    const startIndex = setsCardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return sortedSets.slice(startIndex, endIndex);
  }, [sortedSets, setsCardPageIndex, cardPageSize]);

  const looseTotalPages = Math.ceil(sortedLoose.length / cardPageSize);
  const setsTotalPages = Math.ceil(sortedSets.length / cardPageSize);

  // Loose inventory columns
  const looseColumns: ColumnDef<InventoryItem>[] = [
    {
      accessorKey: 'drawer_name',
      header: 'Drawer',
      cell: ({ row }) => {
        const item = row.original;
        const drawerName = item.drawer_name;
        const drawerId = item.drawer_id;
        if (!drawerName || !drawerId) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <Link
            href={`/drawers/${drawerId}?from=parts&design_id=${designId}`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {drawerName}
          </Link>
        );
      },
    },
    {
      accessorKey: 'container_label',
      header: 'Container',
      cell: ({ row }) => {
        const item = row.original;
        const containerLabel = item.container_label;
        const containerId = item.container_id;
        if (!containerLabel || !containerId) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <Link
            href={`/containers/${containerId}?from=parts&design_id=${designId}`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {containerLabel}
          </Link>
        );
      },
    },
    {
      accessorKey: 'color_name',
      header: 'Color',
      cell: ({ row }) => {
        const item = row.original;
        const hex = item.color_hex;
        if (!hex && !item.color_name) {
          return <span className="text-muted-foreground">—</span>;
        }
        // Ensure hex has # prefix
        const hexWithHash = hex ? (hex.startsWith('#') ? hex : `#${hex}`) : null;
        if (!hexWithHash) {
          return <span>{item.color_name || '—'}</span>;
        }
        const isLight = isLightColor(hexWithHash);
        return (
          <div
            className="inline-flex items-center gap-2 px-2 py-1 rounded text-sm font-medium"
            style={{
              backgroundColor: hexWithHash,
              color: isLight ? '#000000' : '#ffffff',
            }}
          >
            {item.color_name || '—'}
          </div>
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
  ];

  // Sets columns
  const setsColumns: ColumnDef<PartInSet>[] = [
    {
      accessorKey: 'set_number',
      header: 'Set Number',
      cell: ({ row }) => {
        const set = row.original;
        return (
          <Link
            href={`/sets/${set.set_number}?from=parts`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {set.set_number}
          </Link>
        );
      },
    },
    {
      accessorKey: 'set_name',
      header: 'Set Name',
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const status = row.original.status;
        return status ? (
          <span className="text-sm">{getStatusLabel(status)}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        );
      },
    },
    {
      accessorKey: 'color_name',
      header: 'Color',
      cell: ({ row }) => {
        const set = row.original;
        const hex = set.hex;
        if (!hex && !set.color_name) {
          return <span className="text-muted-foreground">—</span>;
        }
        // Ensure hex has # prefix
        const hexWithHash = hex ? (hex.startsWith('#') ? hex : `#${hex}`) : null;
        if (!hexWithHash) {
          return <span>{set.color_name || '—'}</span>;
        }
        const isLight = isLightColor(hexWithHash);
        return (
          <div
            className="inline-flex items-center gap-2 px-2 py-1 rounded text-sm font-medium"
            style={{
              backgroundColor: hexWithHash,
              color: isLight ? '#000000' : '#ffffff',
            }}
          >
            {set.color_name || '—'}
          </div>
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
  ];

  if (partLoading) {
    return (
      <div className="container mx-auto py-4 md:py-8">
        <div className="text-muted-foreground">Loading part...</div>
      </div>
    );
  }

  if (!part) {
    return (
      <div className="container mx-auto py-4 md:py-8">
        <div className="text-destructive">Part not found.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-4 md:py-8">
      <div className="mb-4 md:mb-6 space-y-4">
        <Button variant="outline" asChild className="min-h-[44px]">
          <Link href={backLink.href}>← Back to {backLink.label}</Link>
        </Button>

        {/* Part Header - Stack on mobile */}
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-6 items-start">
          {part.part_img_url && (
            <img
              src={part.part_img_url}
              alt={part.name}
              className="w-32 h-32 sm:w-48 sm:h-48 object-contain rounded shrink-0"
            />
          )}
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl md:text-3xl font-bold wrap-break-word">{part.name}</h1>
            <div className="mt-2 space-y-1">
              <p className="text-muted-foreground text-sm">
                <span className="font-mono">{part.design_id}</span>
                {aliases && aliases.length > 0 && (
                  <>
                    {' '}•{' '}
                    {aliases.length === 1 ? 'Alias: ' : 'Aliases: '}
                    <span className="font-mono">{aliases.join(', ')}</span>
                  </>
                )}
              </p>
              {part.part_category_name && (
                <p className="text-muted-foreground text-sm">
                  <span className="text-muted-foreground">Category: </span>
                  <span className="font-medium">{part.part_category_name}</span>
                </p>
              )}
            </div>

            {/* Stats - Stack on mobile */}
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 mt-4 text-sm">
              {!APP_SAFE_MODE && (
                <div>
                  <span className="text-muted-foreground">Loose: </span>
                  <span className="font-medium">{formatNumber(totalLooseQty)}</span>
                </div>
              )}
              <div>
                <span className="text-muted-foreground">Total: </span>
                <span className="font-medium">{formatNumber(totalQty)}</span>
              </div>
            </div>

            {/* Actions - Stack on mobile */}
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 mt-4">
              {part.part_url && (
                <Button variant="outline" asChild className="min-h-[44px]">
                  <a
                    href={part.part_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1"
                  >
                    View on Rebrickable <ExternalLink className="h-4 w-4" />
                  </a>
                </Button>
              )}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="ignore-in-inventory"
                  checked={part.ignore_in_inventory}
                  onCheckedChange={(checked) => {
                    updatePartMutation.mutate({
                      ignore_in_inventory: checked === true,
                    });
                  }}
                  disabled={updatePartMutation.isPending}
                />
                <Label
                  htmlFor="ignore-in-inventory"
                  className="text-sm font-normal cursor-pointer"
                >
                  Ignore in inventory
                </Label>
              </div>
            </div>
          </div>
        </div>
      </div>

      {APP_SAFE_MODE ? (
        <div className="mt-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
            <h2 className="text-2xl font-semibold">In Sets</h2>
            <ViewToggle
              viewMode={setsViewMode}
              onViewModeChange={setSetsViewMode}
            />
          </div>

          {setsLoading ? (
            <div className="text-muted-foreground">Loading...</div>
          ) : sets && sets.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Not in any sets.
            </div>
          ) : setsViewMode === 'table' ? (
            <DataTable
              columns={setsColumns}
              data={sortedSets}
              searchKeys={['set_number', 'set_name', 'status', 'color_name']}
              searchPlaceholder="Search by set number, name, status, or color..."
              numericColumns={['quantity']}
              defaultSorting={[{ id: 'quantity', desc: true }]}
            />
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {paginatedSetsCards.map((setItem, index) => (
                  <Card
                    key={`${setItem.set_number}-${setItem.color_id}-${index}`}
                  >
                    <CardContent className="pt-6">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium">
                            <Link
                              href={`/sets/${setItem.set_number}?from=parts`}
                              className="hover:underline text-blue-600"
                            >
                              {setItem.set_number}
                            </Link>
                          </div>
                          <div className="text-sm text-muted-foreground mt-1">
                            {setItem.set_name}
                          </div>
                          {setItem.status && (
                            <div className="text-xs text-muted-foreground mt-1">
                              Status: {getStatusLabel(setItem.status)}
                            </div>
                          )}
                          <div className="text-sm mt-1">
                            {setItem.hex ? (
                              <div
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                                style={{
                                  backgroundColor: setItem.hex.startsWith('#') ? setItem.hex : `#${setItem.hex}`,
                                  color: isLightColor(setItem.hex.startsWith('#') ? setItem.hex : `#${setItem.hex}`) ? '#000000' : '#ffffff',
                                }}
                              >
                                {setItem.color_name}
                              </div>
                            ) : (
                              <span className="text-muted-foreground">{setItem.color_name}</span>
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-lg">
                            {formatNumber(setItem.quantity)}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
              {setsTotalPages > 1 && (
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-4">
                  <div className="text-sm text-muted-foreground">
                    Showing {setsCardPageIndex * cardPageSize + 1} to{' '}
                    {Math.min(
                      (setsCardPageIndex + 1) * cardPageSize,
                      sortedSets.length
                    )}{' '}
                    of {sortedSets.length} items
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setSetsCardPageIndex(Math.max(0, setsCardPageIndex - 1))
                      }
                      disabled={setsCardPageIndex === 0}
                      className="min-h-[44px] min-w-[44px]"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm whitespace-nowrap">
                      Page {setsCardPageIndex + 1} of {setsTotalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setSetsCardPageIndex(
                          Math.min(setsTotalPages - 1, setsCardPageIndex + 1)
                        )
                      }
                      disabled={setsCardPageIndex >= setsTotalPages - 1}
                      className="min-h-[44px] min-w-[44px]"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      ) : (
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'loose' | 'sets')}>
          <TabsList>
            <TabsTrigger value="loose">Loose Parts</TabsTrigger>
            <TabsTrigger value="sets">In Sets</TabsTrigger>
          </TabsList>

          <TabsContent value="loose" className="mt-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
              <h2 className="text-2xl font-semibold">Loose Parts</h2>
              <ViewToggle
                viewMode={looseViewMode}
                onViewModeChange={setLooseViewMode}
              />
            </div>

            {looseLoading ? (
              <div className="text-muted-foreground">Loading...</div>
            ) : looseInventory && looseInventory.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No loose parts found.
              </div>
            ) : looseViewMode === 'table' ? (
              <DataTable
                columns={looseColumns}
                data={sortedLoose}
                searchKeys={['drawer_name', 'container_label', 'color_name']}
                searchPlaceholder="Search by drawer, container, or color..."
                numericColumns={['quantity']}
                defaultSorting={[{ id: 'quantity', desc: true }]}
              />
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {paginatedLooseCards.map((item, index) => (
                    <Card key={index}>
                      <CardContent className="pt-6">
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="font-medium">
                              {item.drawer_id && item.drawer_name ? (
                                <Link
                                  href={`/drawers/${item.drawer_id}?from=parts&design_id=${designId}`}
                                  className="text-blue-600 hover:text-blue-800 hover:underline"
                                >
                                  {item.drawer_name}
                                </Link>
                              ) : (
                                <span>{item.drawer_name || 'Unknown'}</span>
                              )}{' '}
                              /{' '}
                              {item.container_id && item.container_label ? (
                                <Link
                                  href={`/containers/${item.container_id}?from=parts&design_id=${designId}`}
                                  className="text-blue-600 hover:text-blue-800 hover:underline"
                                >
                                  {item.container_label}
                                </Link>
                              ) : (
                                <span>{item.container_label || 'Unknown'}</span>
                              )}
                            </div>
                            <div className="text-sm mt-1">
                              {item.color_hex ? (
                                <div
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                                  style={{
                                    backgroundColor: item.color_hex.startsWith('#')
                                      ? item.color_hex
                                      : `#${item.color_hex}`,
                                    color: isLightColor(
                                      item.color_hex.startsWith('#')
                                        ? item.color_hex
                                        : `#${item.color_hex}`
                                    )
                                      ? '#000000'
                                      : '#ffffff',
                                  }}
                                >
                                  {item.color_name || 'Unknown Color'}
                                </div>
                              ) : (
                                <span className="text-muted-foreground">
                                  {item.color_name || 'Unknown Color'}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold text-lg">
                              {formatNumber(item.quantity)}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
                {looseTotalPages > 1 && (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-4">
                    <div className="text-sm text-muted-foreground">
                      Showing {looseCardPageIndex * cardPageSize + 1} to{' '}
                      {Math.min(
                        (looseCardPageIndex + 1) * cardPageSize,
                        sortedLoose.length
                      )}{' '}
                      of {sortedLoose.length} items
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setLooseCardPageIndex(Math.max(0, looseCardPageIndex - 1))
                        }
                        disabled={looseCardPageIndex === 0}
                        className="min-h-[44px] min-w-[44px]"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <span className="text-sm whitespace-nowrap">
                        Page {looseCardPageIndex + 1} of {looseTotalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setLooseCardPageIndex(
                            Math.min(looseTotalPages - 1, looseCardPageIndex + 1)
                          )
                        }
                        disabled={looseCardPageIndex >= looseTotalPages - 1}
                        className="min-h-[44px] min-w-[44px]"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </TabsContent>

          <TabsContent value="sets" className="mt-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
              <h2 className="text-2xl font-semibold">In Sets</h2>
              <ViewToggle
                viewMode={setsViewMode}
                onViewModeChange={setSetsViewMode}
              />
            </div>

            {setsLoading ? (
              <div className="text-muted-foreground">Loading...</div>
            ) : sets && sets.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                Not in any sets.
              </div>
            ) : setsViewMode === 'table' ? (
              <DataTable
                columns={setsColumns}
                data={sortedSets}
                searchKeys={['set_number', 'set_name', 'status', 'color_name']}
                searchPlaceholder="Search by set number, name, status, or color..."
                numericColumns={['quantity']}
                defaultSorting={[{ id: 'quantity', desc: true }]}
              />
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {paginatedSetsCards.map((setItem, index) => (
                    <Card
                      key={`${setItem.set_number}-${setItem.color_id}-${index}`}
                    >
                      <CardContent className="pt-6">
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="font-medium">
                              <Link
                                href={`/sets/${setItem.set_number}?from=parts`}
                                className="hover:underline text-blue-600"
                              >
                                {setItem.set_number}
                              </Link>
                            </div>
                            <div className="text-sm text-muted-foreground mt-1">
                              {setItem.set_name}
                            </div>
                            {setItem.status && (
                              <div className="text-xs text-muted-foreground mt-1">
                                Status: {getStatusLabel(setItem.status)}
                              </div>
                            )}
                            <div className="text-sm mt-1">
                              {setItem.hex ? (
                                <div
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                                  style={{
                                    backgroundColor: setItem.hex.startsWith('#') ? setItem.hex : `#${setItem.hex}`,
                                    color: isLightColor(setItem.hex.startsWith('#') ? setItem.hex : `#${setItem.hex}`) ? '#000000' : '#ffffff',
                                  }}
                                >
                                  {setItem.color_name}
                                </div>
                              ) : (
                                <span className="text-muted-foreground">{setItem.color_name}</span>
                              )}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold text-lg">
                              {formatNumber(setItem.quantity)}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
                {setsTotalPages > 1 && (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-4">
                    <div className="text-sm text-muted-foreground">
                      Showing {setsCardPageIndex * cardPageSize + 1} to{' '}
                      {Math.min(
                        (setsCardPageIndex + 1) * cardPageSize,
                        sortedSets.length
                      )}{' '}
                      of {sortedSets.length} items
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setSetsCardPageIndex(Math.max(0, setsCardPageIndex - 1))
                        }
                        disabled={setsCardPageIndex === 0}
                        className="min-h-[44px] min-w-[44px]"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <span className="text-sm whitespace-nowrap">
                        Page {setsCardPageIndex + 1} of {setsTotalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setSetsCardPageIndex(
                            Math.min(setsTotalPages - 1, setsCardPageIndex + 1)
                          )
                        }
                        disabled={setsCardPageIndex >= setsTotalPages - 1}
                        className="min-h-[44px] min-w-[44px]"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
