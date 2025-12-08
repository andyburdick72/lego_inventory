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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { handleApiError } from '@/lib/api';
import {
  SetPart,
  SetPartWithLocations,
  useSet,
  useSetParts,
  useSetPartsWithLocations,
  useUpdateSetStatus,
} from '@/lib/hooks/use-sets';
import { formatNumber, getStatusLabel, isLightColor } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, ExternalLink, LayoutGrid, Table as TableIcon } from 'lucide-react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

type ViewMode = 'cards' | 'table';

// Status options matching backend enum
const STATUS_OPTIONS = [
  { value: 'built', label: 'Built' },
  { value: 'in_box', label: 'In Box' },
  { value: 'wip', label: 'Work in Progress' },
  { value: 'loose_parts', label: 'Loose' },
  { value: 'teardown', label: 'Teardown' },
];

export default function SetDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const setNumber = params.setNumber as string;
  const [backLink, setBackLink] = useState<{ href: string; label: string }>({
    href: '/sets',
    label: 'Sets',
  });

  // Determine back navigation based on referrer or query param
  useEffect(() => {
    // Check for explicit 'from' query parameter first
    const fromParam = searchParams.get('from');
    if (fromParam) {
      const fromMap: Record<string, { href: string; label: string }> = {
        'sets': { href: '/sets', label: 'Sets' },
        'parts': {
          href: searchParams.get('design_id') ? `/parts/${searchParams.get('design_id')}` : '/loose-parts',
          label: 'Part',
        },
        'part-counts': { href: '/part-counts', label: 'Part Counts' },
        'part-color-counts': { href: '/part-color-counts', label: 'Element Counts' },
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
      } else if (pathname.includes('/parts/')) {
        // Extract part design_id from referrer if possible
        const partMatch = pathname.match(/\/parts\/([^/]+)/);
        if (partMatch) {
          setBackLink({ href: `/parts/${partMatch[1]}`, label: 'Part' });
        } else {
          setBackLink({ href: '/loose-parts', label: 'Loose Parts' });
        }
      } else if (pathname.includes('/sets')) {
        setBackLink({ href: '/sets', label: 'Sets' });
      }
      // Default is already set to sets
    }
  }, [searchParams]);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const [editStatusDialogOpen, setEditStatusDialogOpen] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState<string>('');

  const { data: set, isLoading: setLoading } = useSet(setNumber);
  const { data: parts, isLoading: partsLoading } = useSetParts(setNumber);
  const { data: partsWithLocations, isLoading: partsWithLocationsLoading } =
    useSetPartsWithLocations(setNumber);
  const updateStatus = useUpdateSetStatus();

  // Check if set status is loose_parts or teardown
  const showPartLocationsTab = useMemo(() => {
    return set?.status === 'loose_parts' || set?.status === 'teardown';
  }, [set?.status]);

  // Calculate total parts from parts data since API doesn't include it
  const totalParts = useMemo(() => {
    if (!parts) return 0;
    return parts.reduce((sum, part) => sum + part.quantity, 0);
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

  // Sort parts with locations by required quantity descending for card view
  const sortedPartsWithLocations = useMemo(() => {
    if (!partsWithLocations) return [];
    return [...partsWithLocations].sort((a, b) => b.required_quantity - a.required_quantity);
  }, [partsWithLocations]);

  // Paginate cards for parts with locations
  const paginatedPartsWithLocations = useMemo(() => {
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return sortedPartsWithLocations.slice(startIndex, endIndex);
  }, [sortedPartsWithLocations, cardPageIndex, cardPageSize]);

  const totalPagesWithLocations = Math.ceil(sortedPartsWithLocations.length / cardPageSize);

  const columns: ColumnDef<SetPart>[] = [
    {
      accessorKey: 'design_id',
      header: 'Part ID',
      cell: ({ row }) => {
        const part = row.original;
        return (
          <Link
            href={`/parts/${part.design_id}?from=sets&set_number=${setNumber}`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {part.design_id}
          </Link>
        );
      },
    },
    {
      accessorKey: 'name',
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
            alt={part.name}
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
            className="text-blue-600 hover:text-blue-800 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            View
          </a>
        );
      },
    },
  ];

  const partLocationsColumns: ColumnDef<SetPartWithLocations>[] = [
    {
      accessorKey: 'design_id',
      header: 'Part ID',
      cell: ({ row }) => {
        const part = row.original;
        return (
          <Link
            href={`/parts/${part.design_id}?from=sets&set_number=${setNumber}`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {part.design_id}
          </Link>
        );
      },
    },
    {
      accessorKey: 'name',
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
            alt={part.name}
            className="h-12 w-auto"
            onClick={(e) => e.stopPropagation()}
          />
        );
      },
    },
    {
      accessorKey: 'required_quantity',
      header: 'Required',
      cell: ({ row }) => {
        return (
          <div className="text-right">
            {formatNumber(row.original.required_quantity)}
          </div>
        );
      },
    },
    {
      accessorKey: 'available_quantity',
      header: 'Available',
      cell: ({ row }) => {
        const part = row.original;
        const hasEnough = part.available_quantity >= part.required_quantity;
        return (
          <div className={`text-right ${hasEnough ? '' : 'text-orange-600 font-medium'}`}>
            {formatNumber(part.available_quantity)}
          </div>
        );
      },
    },
    {
      id: 'locations',
      header: 'Location(s)',
      cell: ({ row }) => {
        const part = row.original;
        if (part.locations.length === 0) {
          return <span className="text-muted-foreground">Not in inventory</span>;
        }
        if (part.locations.length === 1) {
          const loc = part.locations[0];
          const drawerLink = loc.drawer_id ? (
            <Link
              href={`/drawers/${loc.drawer_id}?from=sets&set_number=${setNumber}`}
              className="text-blue-600 hover:text-blue-800 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {loc.drawer_name || 'Unknown'}
            </Link>
          ) : (
            <span>{loc.drawer_name || ''}</span>
          );
          const containerLink = loc.container_id ? (
            <Link
              href={`/containers/${loc.container_id}?from=sets&set_number=${setNumber}`}
              className="text-blue-600 hover:text-blue-800 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {loc.container_name || 'Unknown'}
            </Link>
          ) : (
            <span>{loc.container_name || ''}</span>
          );
          
          if (loc.drawer_name && loc.container_name) {
            return (
              <div className="text-sm">
                {drawerLink} / {containerLink} ({formatNumber(loc.quantity)})
              </div>
            );
          }
          return (
            <div className="text-sm">
              {drawerLink}
              {loc.drawer_name && loc.container_name ? ' / ' : ''}
              {containerLink}
              {loc.drawer_name || loc.container_name ? ` (${formatNumber(loc.quantity)})` : '(unknown)'}
            </div>
          );
        }
        return (
          <ul className="list-disc list-inside space-y-0.5">
            {part.locations.map((loc, idx) => {
              const drawerLink = loc.drawer_id ? (
                <Link
                  href={`/drawers/${loc.drawer_id}?from=sets&set_number=${setNumber}`}
                  className="text-blue-600 hover:text-blue-800 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {loc.drawer_name || 'Unknown'}
                </Link>
              ) : (
                <span>{loc.drawer_name || ''}</span>
              );
              const containerLink = loc.container_id ? (
                <Link
                  href={`/containers/${loc.container_id}?from=sets&set_number=${setNumber}`}
                  className="text-blue-600 hover:text-blue-800 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {loc.container_name || 'Unknown'}
                </Link>
              ) : (
                <span>{loc.container_name || ''}</span>
              );
              
              return (
                <li key={idx} className="text-sm">
                  {loc.drawer_name && loc.container_name ? (
                    <>
                      {drawerLink} / {containerLink} ({formatNumber(loc.quantity)})
                    </>
                  ) : (
                    <>
                      {drawerLink}
                      {loc.drawer_name && loc.container_name ? ' / ' : ''}
                      {containerLink}
                      {loc.drawer_name || loc.container_name ? ` (${formatNumber(loc.quantity)})` : '(unknown)'}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        );
      },
    },
  ];

  if (setLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-muted-foreground">Loading set...</div>
      </div>
    );
  }

  if (!set) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-destructive">Set not found.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href={backLink.href}>← Back to {backLink.label}</Link>
        </Button>
        <div className="flex gap-6 items-start">
          {set.image_url && (
            <img
              src={set.image_url}
              alt={set.name}
              className="w-48 h-48 object-contain rounded"
            />
          )}
          <div className="flex-1">
            <h1 className="text-3xl font-bold">{set.set_number}</h1>
            <h2 className="text-xl text-muted-foreground mt-2">{set.name}</h2>
            <div className="flex gap-4 mt-4 text-sm">
              {set.year && (
                <div>
                  <span className="text-muted-foreground">Year: </span>
                  <span className="font-medium">{set.year}</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Status: </span>
                <span className="font-medium">
                  {getStatusLabel(set.status)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSelectedStatus(set.status);
                    setEditStatusDialogOpen(true);
                  }}
                >
                  Edit
                </Button>
              </div>
              <div>
                <span className="text-muted-foreground">Parts: </span>
                <span className="font-medium">
                  {partsLoading ? '...' : formatNumber(totalParts)}
                </span>
              </div>
            </div>
            {set.rebrickable_url && (
              <Button className="mt-4" variant="outline" asChild>
                <a
                  href={set.rebrickable_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1"
                >
                  View on Rebrickable <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="mb-4">
        {showPartLocationsTab ? (
          <Tabs defaultValue="parts" className="w-full">
            <div className="flex items-center justify-between mb-4">
              <TabsList>
                <TabsTrigger value="parts">Parts</TabsTrigger>
                <TabsTrigger value="locations">Pick List</TabsTrigger>
              </TabsList>
              <div className="flex items-center border rounded-md">
                <Button
                  variant={viewMode === 'table' ? 'default' : 'ghost'}
                  size="sm"
                  className="rounded-r-none"
                  onClick={() => {
                    setViewMode('table');
                    setCardPageIndex(0);
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
                    setCardPageIndex(0);
                  }}
                >
                  <LayoutGrid className="h-4 w-4 mr-2" />
                  Cards
                </Button>
              </div>
            </div>
            <TabsContent value="parts" className="mt-4">
              {partsLoading ? (
                <div className="text-muted-foreground">Loading parts...</div>
              ) : parts && parts.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No parts found for this set.
                </div>
              ) : viewMode === 'table' ? (
                <DataTable
                  columns={columns}
                  data={parts || []}
                  searchKeys={['design_id', 'name', 'color', 'color_name']}
                  searchPlaceholder="Search by part ID, name, or color..."
                  exportFilename={`set-${setNumber}-parts`}
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
                              href={`/parts/${part.design_id}?from=sets&set_number=${setNumber}`}
                              className="text-blue-600 hover:text-blue-800 hover:underline"
                            >
                              {part.design_id}
                            </Link>
                          </CardTitle>
                          <CardDescription className="text-xs">{part.name}</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {part.part_img_url && (
                              <div className="flex justify-center">
                                <img
                                  src={part.part_img_url}
                                  alt={part.name}
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
                                    className="inline-flex items-center gap-1"
                                  >
                                    View on Rebrickable <ExternalLink className="h-3 w-3" />
                                  </a>
                                </Button>
                              )}
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
            </TabsContent>
            <TabsContent value="locations" className="mt-4">
              {partsWithLocationsLoading ? (
                <div className="text-muted-foreground">Loading part locations...</div>
              ) : partsWithLocations && partsWithLocations.length > 0 ? (
                viewMode === 'table' ? (
                <DataTable
                  columns={partLocationsColumns}
                  data={partsWithLocations}
                  searchKeys={['design_id', 'name', 'color', 'color_name', 'locations']}
                  searchPlaceholder="Search by part ID, name, color, or location..."
                  exportFilename={`set-${setNumber}-part-locations`}
                  defaultSorting={[{ id: 'required_quantity', desc: true }]}
                  numericColumns={['required_quantity', 'available_quantity']}
                  defaultPageSize={20}
                />
                ) : (
                  <>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {paginatedPartsWithLocations.map((part, index) => (
                        <Card key={`${part.design_id}-${part.color_id}-${index}`}>
                          <CardHeader>
                            <CardTitle className="text-sm">
                              <Link
                                href={`/parts/${part.design_id}?from=sets&set_number=${setNumber}`}
                                className="text-blue-600 hover:text-blue-800 hover:underline"
                              >
                                {part.design_id}
                              </Link>
                            </CardTitle>
                            <CardDescription className="text-xs">{part.name}</CardDescription>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-3">
                              {part.part_img_url && (
                                <div className="flex justify-center">
                                  <img
                                    src={part.part_img_url}
                                    alt={part.name}
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
                                  <span className="text-muted-foreground">Required:</span>
                                  <span className="font-medium">
                                    {formatNumber(part.required_quantity)}
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Available:</span>
                                  <span
                                    className={`font-medium ${
                                      part.available_quantity >= part.required_quantity
                                        ? ''
                                        : 'text-orange-600'
                                    }`}
                                  >
                                    {formatNumber(part.available_quantity)}
                                  </span>
                                </div>
                                {part.locations.length > 0 && (
                                  <div className="space-y-1 pt-2 border-t">
                                    <span className="text-muted-foreground text-xs">
                                      {part.locations.length === 1 ? 'Location:' : 'Locations:'}
                                    </span>
                                    {part.locations.length === 1 ? (
                                      <div className="text-xs">
                                        {(() => {
                                          const loc = part.locations[0];
                                          const drawerLink = loc.drawer_id ? (
                                            <Link
                                              href={`/drawers/${loc.drawer_id}?from=sets&set_number=${setNumber}`}
                                              className="text-blue-600 hover:text-blue-800 hover:underline"
                                            >
                                              {loc.drawer_name || 'Unknown'}
                                            </Link>
                                          ) : (
                                            <span>{loc.drawer_name || ''}</span>
                                          );
                                          const containerLink = loc.container_id ? (
                                            <Link
                                              href={`/containers/${loc.container_id}?from=sets&set_number=${setNumber}`}
                                              className="text-blue-600 hover:text-blue-800 hover:underline"
                                            >
                                              {loc.container_name || 'Unknown'}
                                            </Link>
                                          ) : (
                                            <span>{loc.container_name || ''}</span>
                                          );
                                          
                                          if (loc.drawer_name && loc.container_name) {
                                            return (
                                              <>
                                                {drawerLink} / {containerLink} ({formatNumber(loc.quantity)})
                                              </>
                                            );
                                          }
                                          return (
                                            <>
                                              {drawerLink}
                                              {loc.drawer_name && loc.container_name ? ' / ' : ''}
                                              {containerLink}
                                              {loc.drawer_name || loc.container_name ? ` (${formatNumber(loc.quantity)})` : '(unknown)'}
                                            </>
                                          );
                                        })()}
                                      </div>
                                    ) : (
                                      <ul className="list-disc list-inside space-y-0.5">
                                        {part.locations.map((loc, idx) => {
                                          const drawerLink = loc.drawer_id ? (
                                            <Link
                                              href={`/drawers/${loc.drawer_id}?from=sets&set_number=${setNumber}`}
                                              className="text-blue-600 hover:text-blue-800 hover:underline"
                                            >
                                              {loc.drawer_name || 'Unknown'}
                                            </Link>
                                          ) : (
                                            <span>{loc.drawer_name || ''}</span>
                                          );
                                          const containerLink = loc.container_id ? (
                                            <Link
                                              href={`/containers/${loc.container_id}?from=sets&set_number=${setNumber}`}
                                              className="text-blue-600 hover:text-blue-800 hover:underline"
                                            >
                                              {loc.container_name || 'Unknown'}
                                            </Link>
                                          ) : (
                                            <span>{loc.container_name || ''}</span>
                                          );
                                          
                                          return (
                                            <li key={idx} className="text-xs">
                                              {loc.drawer_name && loc.container_name ? (
                                                <>
                                                  {drawerLink} / {containerLink} ({formatNumber(loc.quantity)})
                                                </>
                                              ) : (
                                                <>
                                                  {drawerLink}
                                                  {loc.drawer_name && loc.container_name ? ' / ' : ''}
                                                  {containerLink}
                                                  {loc.drawer_name || loc.container_name ? ` (${formatNumber(loc.quantity)})` : '(unknown)'}
                                                </>
                                              )}
                                            </li>
                                          );
                                        })}
                                      </ul>
                                    )}
                                  </div>
                                )}
                                {part.locations.length === 0 && (
                                  <div className="pt-2 border-t">
                                    <span className="text-muted-foreground text-xs">
                                      Not in inventory
                                    </span>
                                  </div>
                                )}
                                {part.part_url && (
                                  <Button variant="outline" size="sm" className="w-full" asChild>
                                    <a
                                      href={part.part_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1"
                                    >
                                      View on Rebrickable <ExternalLink className="h-3 w-3" />
                                    </a>
                                  </Button>
                                )}
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
                          {formatNumber(
                            Math.min(
                              (cardPageIndex + 1) * cardPageSize,
                              sortedPartsWithLocations.length
                            )
                          )}{' '}
                          of {formatNumber(sortedPartsWithLocations.length)} results
                        </p>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <p className="text-sm text-muted-foreground">Cards per page:</p>
                          <Select
                            value={
                              cardPageSize >= sortedPartsWithLocations.length
                                ? 'all'
                                : String(cardPageSize)
                            }
                            onValueChange={(value) => {
                              if (value === 'all') {
                                setCardPageSize(sortedPartsWithLocations.length);
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
                            {formatNumber(totalPagesWithLocations > 0 ? totalPagesWithLocations : 1)}
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setCardPageIndex((prev) =>
                                Math.min(totalPagesWithLocations - 1, prev + 1)
                              )
                            }
                            disabled={cardPageIndex >= totalPagesWithLocations - 1}
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </>
                )
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No parts found for this set.
                </div>
              )}
            </TabsContent>
          </Tabs>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-semibold">Parts</h2>
              <div className="flex items-center border rounded-md">
                <Button
                  variant={viewMode === 'table' ? 'default' : 'ghost'}
                  size="sm"
                  className="rounded-r-none"
                  onClick={() => {
                    setViewMode('table');
                    setCardPageIndex(0);
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
                    setCardPageIndex(0);
                  }}
                >
                  <LayoutGrid className="h-4 w-4 mr-2" />
                  Cards
                </Button>
              </div>
            </div>
            {partsLoading ? (
              <div className="text-muted-foreground">Loading parts...</div>
            ) : parts && parts.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No parts found for this set.
              </div>
            ) : viewMode === 'table' ? (
              <DataTable
                columns={columns}
                data={parts || []}
                searchKeys={['design_id', 'name', 'color', 'color_name']}
                searchPlaceholder="Search by part ID, name, or color..."
                exportFilename={`set-${setNumber}-parts`}
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
                            href={`/parts/${part.design_id}?from=sets&set_number=${setNumber}`}
                            className="text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            {part.design_id}
                          </Link>
                        </CardTitle>
                        <CardDescription className="text-xs">{part.name}</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          {part.part_img_url && (
                            <div className="flex justify-center">
                              <img
                                src={part.part_img_url}
                                alt={part.name}
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
                                  className="inline-flex items-center gap-1"
                                >
                                  View on Rebrickable <ExternalLink className="h-3 w-3" />
                                </a>
                              </Button>
                            )}
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
          </>
        )}
      </div>

      {/* Edit Status Dialog */}
      <Dialog open={editStatusDialogOpen} onOpenChange={setEditStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Set Status</DialogTitle>
            <DialogDescription>
              Update the status for {set.set_number}: {set.name}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="status">Status</Label>
              <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                <SelectTrigger id="status">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditStatusDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={async () => {
                try {
                  await updateStatus.mutateAsync({
                    setNumber,
                    status: selectedStatus,
                  });
                  setEditStatusDialogOpen(false);
                } catch (error) {
                  alert(handleApiError(error));
                }
              }}
              disabled={!selectedStatus || updateStatus.isPending}
            >
              {updateStatus.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

