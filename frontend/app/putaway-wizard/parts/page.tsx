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
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ViewToggle } from '@/components/view-toggle';
import { PutawayPartWithSuggestion, usePutawayPartsFromSet, usePutawayPartsInBin } from '@/lib/hooks/use-putaway';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { formatNumber, isLightColor } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useMemo, useState } from 'react';

export default function PutawayWizardPartsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const source = searchParams.get('source');
  const setNumber = searchParams.get('setNumber');
  const search = searchParams.get('search') || '';

  const [viewMode, setViewMode] = useViewMode('table', 'putaway-wizard-parts-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const [selectedParts, setSelectedParts] = useState<Set<string>>(new Set());

  const { data: partsFromSet } = usePutawayPartsFromSet(setNumber || '');
  const { data: partsInBin } = usePutawayPartsInBin(search || undefined);

  const parts = useMemo(() => {
    if (source === 'set') {
      return partsFromSet || [];
    } else {
      return partsInBin || [];
    }
  }, [source, partsFromSet, partsInBin]);

  // Track parts keys to detect when parts list changes
  const partsKeys = useMemo(
    () => parts.map((p) => `${p.design_id}-${p.color_id}`).sort().join(','),
    [parts]
  );

  // Initialize selected parts when parts load (all selected by default)
  // Reset selection when parts list changes
  useMemo(() => {
    if (parts.length > 0) {
      const allKeys = new Set(parts.map((p) => `${p.design_id}-${p.color_id}`));
      setSelectedParts(allKeys);
    } else {
      setSelectedParts(new Set());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partsKeys]);

  const togglePartSelection = (key: string) => {
    const newSelected = new Set(selectedParts);
    if (newSelected.has(key)) {
      newSelected.delete(key);
    } else {
      newSelected.add(key);
    }
    setSelectedParts(newSelected);
  };

  const selectAllParts = () => {
    const allKeys = new Set(parts.map((p) => `${p.design_id}-${p.color_id}`));
    setSelectedParts(allKeys);
  };

  const deselectAllParts = () => {
    setSelectedParts(new Set());
  };

  // Filter parts to only show selected ones
  const selectedPartsList = useMemo(() => {
    return parts.filter((part) => {
      const key = `${part.design_id}-${part.color_id}`;
      return selectedParts.has(key);
    });
  }, [parts, selectedParts]);

  // Sort parts by quantity descending for card view
  const sortedParts = useMemo(() => {
    return [...parts].sort((a, b) => b.quantity - a.quantity);
  }, [parts]);

  // Paginate cards
  const paginatedCards = useMemo(() => {
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return sortedParts.slice(startIndex, endIndex);
  }, [sortedParts, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil(sortedParts.length / cardPageSize);

  const handleNext = () => {
    // Build params for next step, including selected parts
    const params = new URLSearchParams();
    if (source) params.set('source', source);
    if (setNumber) params.set('setNumber', setNumber);
    if (search) params.set('search', search);
    // Encode selected parts as comma-separated design_id-color_id pairs
    const selectedKeys = Array.from(selectedParts);
    if (selectedKeys.length > 0) {
      params.set('selected', selectedKeys.join(','));
    }
    router.push(`/putaway-wizard/assign?${params.toString()}`);
  };

  const getConfidenceColor = (confidence?: string) => {
    switch (confidence) {
      case 'high':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'medium':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'low':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const columns: ColumnDef<PutawayPartWithSuggestion>[] = [
    {
      id: 'select',
      header: () => (
        <div className="flex items-center gap-2">
          <Checkbox
            checked={selectedParts.size === parts.length && parts.length > 0}
            onCheckedChange={(checked) => {
              if (checked) {
                selectAllParts();
              } else {
                deselectAllParts();
              }
            }}
            className="h-4 w-4"
          />
        </div>
      ),
      cell: ({ row }) => {
        const part = row.original;
        const key = `${part.design_id}-${part.color_id}`;
        const isSelected = selectedParts.has(key);
        return (
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => togglePartSelection(key)}
            className="h-4 w-4"
          />
        );
      },
      enableSorting: false,
      enableHiding: false,
    },
    {
      accessorKey: 'design_id',
      header: 'Part ID',
      cell: ({ row }) => {
        const part = row.original;
        return (
          <Link
            href={`/parts/${part.design_id}?from=putaway-wizard`}
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
      id: 'confidence',
      header: 'Confidence',
      accessorFn: (row) => row.suggestion?.confidence || 'none',
      sortingFn: (rowA, rowB, columnId) => {
        const confidenceOrder: Record<string, number> = {
          'high': 0,
          'medium': 1,
          'low': 2,
          'none': 3,
        };
        const a = rowA.getValue(columnId) as string || 'none';
        const b = rowB.getValue(columnId) as string || 'none';
        return (confidenceOrder[a] ?? 99) - (confidenceOrder[b] ?? 99);
      },
      cell: ({ row }) => {
        const part = row.original;
        const suggestion = part.suggestion;
        if (!suggestion) {
          return <span className="text-muted-foreground">No suggestion</span>;
        }
        return (
          <div className={`text-xs px-2 py-1 rounded border inline-block ${getConfidenceColor(suggestion.confidence)}`}>
            {suggestion.confidence.toUpperCase()}
          </div>
        );
      },
    },
    {
      id: 'suggestion',
      header: 'Suggested Location',
      cell: ({ row }) => {
        const part = row.original;
        const suggestion = part.suggestion;
        if (!suggestion) {
          return <span className="text-muted-foreground">—</span>;
        }
        const drawerLink = suggestion.drawer_id ? (
          <Link
            href={`/drawers/${suggestion.drawer_id}?from=putaway-wizard`}
            className="text-blue-600 hover:text-blue-800 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {suggestion.drawer_name}
          </Link>
        ) : (
          <span>{suggestion.drawer_name || '—'}</span>
        );
        const containerLink = suggestion.container_id ? (
          <Link
            href={`/containers/${suggestion.container_id}?from=putaway-wizard`}
            className="text-blue-600 hover:text-blue-800 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {suggestion.container_name}
          </Link>
        ) : (
          <span>{suggestion.container_name || '—'}</span>
        );
        return (
          <div className="font-medium">
            {drawerLink} / {containerLink}
          </div>
        );
      },
    },
    {
      id: 'reason',
      header: 'Reason',
      accessorFn: (row) => row.suggestion?.reason || '',
      cell: ({ row }) => {
        const part = row.original;
        return (
          <div className="text-sm text-muted-foreground max-w-md">
            {part.suggestion?.reason || '—'}
          </div>
        );
      },
    },
  ];

  return (
    <div className="container mx-auto py-4 md:py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/putaway-wizard">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Link>
        </Button>
        <h1 className="text-3xl font-bold mb-2">Parts to Put Away</h1>
        <p className="text-muted-foreground">
          Review parts and their suggested storage locations
        </p>
      </div>

      <div className="mb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
          <div className="text-sm text-muted-foreground">
            {formatNumber(parts.length)} {parts.length === 1 ? 'element' : 'elements'} found
            {selectedParts.size > 0 && (
              <span className="ml-2">
                ({formatNumber(selectedParts.size)} selected)
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {parts.length > 0 && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={selectAllParts}
                  disabled={selectedParts.size === parts.length}
                >
                  Check All
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={deselectAllParts}
                  disabled={selectedParts.size === 0}
                >
                  Check None
                </Button>
              </div>
            )}
            <ViewToggle
              viewMode={viewMode}
              onViewModeChange={(mode) => {
                setViewMode(mode);
                setCardPageIndex(0);
              }}
            />
          </div>
        </div>

        {parts.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No elements found
            </CardContent>
          </Card>
        ) : viewMode === 'table' ? (
          <DataTable
            columns={columns}
            data={parts}
            searchKeys={['part_name', 'color_name', 'design_id']}
            searchPlaceholder="Search by part name, color, or design ID..."
            exportFilename={`putaway-parts-${source}-${setNumber || 'bin'}`}
            defaultSorting={[{ id: 'quantity', desc: true }]}
            numericColumns={['quantity']}
            defaultPageSize={20}
          />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {paginatedCards.map((part) => {
                const suggestion = part.suggestion;
                const confidenceClass = getConfidenceColor(suggestion?.confidence);

                const key = `${part.design_id}-${part.color_id}`;
                const isSelected = selectedParts.has(key);

                return (
                  <Card
                    key={key}
                    className={isSelected ? 'border-primary border-2' : 'border'}
                  >
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <CardTitle className="text-sm">
                            <Link
                              href={`/parts/${part.design_id}?from=putaway-wizard`}
                              className="text-blue-600 hover:text-blue-800 hover:underline"
                            >
                              {part.design_id}
                            </Link>
                          </CardTitle>
                          <CardDescription className="text-xs">{part.part_name}</CardDescription>
                        </div>
                        <div className="shrink-0 pt-1">
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={() => togglePartSelection(key)}
                            className="h-5 w-5"
                          />
                        </div>
                      </div>
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
                                backgroundColor: part.color_hex ? `#${part.color_hex}` : '#ffffff',
                                color: isLightColor(part.color_hex) ? '#000000' : '#ffffff',
                              }}
                            >
                              {part.color_name}
                            </div>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Quantity:</span>
                            <span className="font-medium">{formatNumber(part.quantity)}</span>
                          </div>
                          {suggestion && (
                            <div className="space-y-2 pt-2 border-t">
                              <div>
                                <div className="text-xs text-muted-foreground mb-1">Confidence:</div>
                                <div className={`text-xs px-2 py-1 rounded border inline-block ${confidenceClass}`}>
                                  {suggestion.confidence.toUpperCase()}
                                </div>
                              </div>
                              <div>
                                <div className="text-xs text-muted-foreground mb-1">Suggested:</div>
                                <div className="font-medium text-sm">
                                  {suggestion.drawer_id ? (
                                    <Link
                                      href={`/drawers/${suggestion.drawer_id}?from=putaway-wizard`}
                                      className="text-blue-600 hover:text-blue-800 hover:underline"
                                    >
                                      {suggestion.drawer_name}
                                    </Link>
                                  ) : (
                                    <span>{suggestion.drawer_name || '—'}</span>
                                  )}{' '}
                                  /{' '}
                                  {suggestion.container_id ? (
                                    <Link
                                      href={`/containers/${suggestion.container_id}?from=putaway-wizard`}
                                      className="text-blue-600 hover:text-blue-800 hover:underline"
                                    >
                                      {suggestion.container_name}
                                    </Link>
                                  ) : (
                                    <span>{suggestion.container_name || '—'}</span>
                                  )}
                                </div>
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {suggestion.reason}
                              </div>
                            </div>
                          )}
                          {!suggestion && (
                            <div className="pt-2 border-t text-xs text-muted-foreground">
                              No suggestion available
                            </div>
                          )}
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
                <div className="text-sm text-muted-foreground">
                  Showing {formatNumber(cardPageIndex * cardPageSize + 1)} to{' '}
                  {formatNumber(Math.min((cardPageIndex + 1) * cardPageSize, sortedParts.length))}{' '}
                  of {formatNumber(sortedParts.length)} results
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
                      <SelectTrigger className="w-[100px] min-h-[44px]">
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
                      className="min-h-[44px] min-w-[44px]"
                    >
                      <ChevronLeft className="h-4 w-4" />
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
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button variant="outline" asChild>
          <Link href="/putaway-wizard">Back</Link>
        </Button>
        <Button onClick={handleNext} disabled={parts.length === 0 || selectedParts.size === 0}>
          Continue to Assignment ({selectedParts.size}) <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

