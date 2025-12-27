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
import { ViewToggle } from '@/components/view-toggle';
import { api } from '@/lib/api';
import { LEGOSetCopy, useSetCopiesList } from '@/lib/hooks/use-sets';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { formatNumber, getStatusLabel, showApiErrorToast, showErrorToast, showSuccessToast } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';

export default function SetsPage() {
  const [viewMode, setViewMode] = useViewMode('table', 'sets-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const [syncPartsDialogOpen, setSyncPartsDialogOpen] = useState(false);
  const [syncSetsDialogOpen, setSyncSetsDialogOpen] = useState(false);
  const [defaultStatus, setDefaultStatus] = useState('in_box');
  const [reloadAllSets, setReloadAllSets] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [newSets, setNewSets] = useState<Array<{
    set_num: string;
    name: string;
    year: number | null;
    theme_id: number | null;
    theme_name: string | null;
    image_url: string | null;
    rebrickable_url: string | null;
    quantity_needed: number;
    existing_count: number;
  }>>([]);
  const [setStatuses, setSetStatuses] = useState<Record<string, string>>({});
  const router = useRouter();
  const { data: setCopies, isLoading, error } = useSetCopiesList();

  const setCopiesWithLabels = useMemo(() => {
    if (!setCopies) return [];
    const grouped = new Map<string, LEGOSetCopy[]>();
    for (const c of setCopies) {
      const arr = grouped.get(c.set_number) ?? [];
      arr.push(c);
      grouped.set(c.set_number, arr);
    }
    // Stable-ish numbering: newest (added_at/id) first => Copy #1
    const metaById = new Map<
      number,
      {
        copy_count: number;
        copy_index: number;
        copy_label: string | null;
      }
    >();
    for (const [setNumber, copies] of grouped.entries()) {
      const sorted = [...copies].sort((a, b) => {
        const aKey = a.added_at ?? '';
        const bKey = b.added_at ?? '';
        if (aKey !== bKey) return bKey.localeCompare(aKey);
        return b.id - a.id;
      });
      const copyCount = sorted.length;
      sorted.forEach((copy, idx) => {
        metaById.set(copy.id, {
          copy_count: copyCount,
          copy_index: idx + 1,
          copy_label: copyCount > 1 ? `#${idx + 1}` : null,
        });
      });
    }
    return setCopies.map((c) => ({
      ...c,
      ...(metaById.get(c.id) ?? { copy_count: 1, copy_index: 1, copy_label: null }),
    }));
  }, [setCopies]);

  // Paginate sets for card view
  const paginatedSets = useMemo(() => {
    if (!setCopiesWithLabels) return [];
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return setCopiesWithLabels.slice(startIndex, endIndex);
  }, [setCopiesWithLabels, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((setCopiesWithLabels?.length || 0) / cardPageSize);

  const handleRowClick = (copy: LEGOSetCopy & { copy_count: number; copy_index: number; copy_label: string | null }) => {
    const href =
      copy.copy_count > 1
        ? `/sets/${copy.set_number}?from=sets&copy_id=${copy.id}`
        : `/sets/${copy.set_number}?from=sets`;
    router.push(href);
  };

  const columns: ColumnDef<
    LEGOSetCopy & { copy_count: number; copy_index: number; copy_label: string | null }
  >[] = [
      {
        accessorKey: 'set_number',
        header: 'Set Number',
        cell: ({ row }) => {
          const set = row.original;
          const href =
            set.copy_count > 1
              ? `/sets/${set.set_number}?from=sets&copy_id=${set.id}`
              : `/sets/${set.set_number}?from=sets`;
          return (
            <Link
              href={href}
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              {set.set_number}
            </Link>
          );
        },
      },
      {
        id: 'image',
        header: 'Image',
        cell: ({ row }) => {
          const set = row.original;
          if (!set.image_url) return <span className="text-muted-foreground">—</span>;
          return (
            <img
              src={set.image_url}
              alt={set.name}
              className="h-16 w-auto"
              onClick={(e) => e.stopPropagation()}
            />
          );
        },
      },
      {
        accessorKey: 'name',
        header: 'Name',
      },
      {
        accessorKey: 'year',
        header: 'Year',
        cell: ({ row }) => {
          const year = row.original.year;
          return <span className="text-muted-foreground">{year || '—'}</span>;
        },
      },
      {
        accessorKey: 'theme_name',
        header: 'Theme',
        cell: ({ row }) => {
          const theme = row.original.theme_name;
          return <span className="text-muted-foreground">{theme || '—'}</span>;
        },
      },
      {
        accessorKey: 'total_parts',
        header: 'Parts',
        cell: ({ row }) => {
          return (
            <div className="text-right">
              {formatNumber(row.original.total_parts)}
            </div>
          );
        },
      },
      {
        id: 'rebrickable_link',
        header: 'Rebrickable',
        cell: ({ row }) => {
          const set = row.original;
          if (!set.rebrickable_url) return <span className="text-muted-foreground">—</span>;
          return (
            <a
              href={set.rebrickable_url}
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
        id: 'copy',
        header: 'Copy',
        accessorFn: (row) => row.copy_label ?? '',
        cell: ({ row }) => {
          const copy = row.original;
          if (copy.copy_count <= 1) return <span className="text-muted-foreground">—</span>;
          return <span className="font-medium">{copy.copy_label}</span>;
        },
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const status = row.original.status;
          return <span>{getStatusLabel(status)}</span>;
        },
      },
    ];

  if (isLoading) {
    return (
      <div className="container mx-auto py-4 md:py-8">
        <h1 className="text-2xl md:text-3xl font-bold mb-4 md:mb-6">Sets</h1>
        <div className="text-muted-foreground">Loading sets...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-4 md:py-8">
        <h1 className="text-2xl md:text-3xl font-bold mb-4 md:mb-6">Sets</h1>
        <div className="text-destructive">Error loading sets. Please try again.</div>
      </div>
    );
  }

  const handleSyncParts = async () => {
    setIsRunning(true);
    try {
      const response = await api.post('/api/v1/scripts/sync-rebrickable-parts', {
        all_sets: reloadAllSets,
      });
      if (response.data.success) {
        showSuccessToast(response.data.message);
        setSyncPartsDialogOpen(false);
        setReloadAllSets(false);
        // Refresh sets data
        window.location.reload();
      } else {
        // Show error with output details
        const errorMsg = response.data.output
          ? `${response.data.message}\n\n${response.data.output}`
          : response.data.message;
        showErrorToast(errorMsg);
      }
    } catch (error) {
      showApiErrorToast(error);
    } finally {
      setIsRunning(false);
    }
  };

  const handleDiscoverSets = async () => {
    setIsRunning(true);
    try {
      const response = await api.post('/api/v1/scripts/sync-rebrickable-sets/discover', {
        update_themes: false,
      });
      if (response.data.success) {
        const sets = response.data.new_sets || [];
        setNewSets(sets);
        // Initialize statuses with default
        const initialStatuses: Record<string, string> = {};
        sets.forEach((set: typeof sets[0]) => {
          initialStatuses[set.set_num] = defaultStatus;
        });
        setSetStatuses(initialStatuses);
        if (sets.length === 0) {
          showSuccessToast('No new sets found. All sets are already synced.');
          setSyncSetsDialogOpen(false);
        }
      } else {
        showErrorToast(response.data.message || 'Failed to discover sets');
      }
    } catch (error) {
      showApiErrorToast(error);
    } finally {
      setIsRunning(false);
    }
  };

  const handleApplyStatusAssignments = async () => {
    setIsRunning(true);
    try {
      const assignments = newSets.map((set) => ({
        set_num: set.set_num,
        status: setStatuses[set.set_num] || defaultStatus,
        quantity: set.quantity_needed,
      }));

      const response = await api.post('/api/v1/scripts/sync-rebrickable-sets/apply-status', {
        assignments,
      });
      if (response.data.success) {
        showSuccessToast(response.data.message);
        setSyncSetsDialogOpen(false);
        setNewSets([]);
        setSetStatuses({});
        // Refresh sets data
        window.location.reload();
      } else {
        showErrorToast(response.data.message || 'Failed to sync sets');
      }
    } catch (error) {
      showApiErrorToast(error);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="container mx-auto py-4 md:py-8">
      <div className="mb-4 md:mb-6">
        <Button variant="outline" asChild className="mb-4 min-h-[44px]">
          <Link href="/">← Back to Home</Link>
        </Button>
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <h1 className="text-2xl md:text-3xl font-bold">Sets</h1>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                onClick={() => setSyncPartsDialogOpen(true)}
                disabled={isRunning}
                className="min-h-[44px]"
              >
                Sync Parts
              </Button>
              <Button
                variant="outline"
                onClick={() => setSyncSetsDialogOpen(true)}
                disabled={isRunning}
                className="min-h-[44px]"
              >
                Sync Sets
              </Button>
              <ViewToggle
                viewMode={viewMode}
                onViewModeChange={(mode) => {
                  setViewMode(mode);
                  setCardPageIndex(0);
                }}
              />
            </div>
          </div>
          {!isLoading && setCopiesWithLabels && (
            <div className="text-sm">
              <span className="text-muted-foreground">Total Set Copies: </span>
              <span className="font-medium">{formatNumber(setCopiesWithLabels.length)}</span>
            </div>
          )}
          {isLoading && (
            <p className="text-muted-foreground">Loading...</p>
          )}
        </div>
      </div>

      {setCopiesWithLabels && setCopiesWithLabels.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No sets found.
        </div>
      ) : viewMode === 'table' ? (
        <DataTable
          columns={columns}
          data={setCopiesWithLabels || []}
          searchKeys={['copy_label', 'set_number', 'name', 'year', 'theme_name', 'status']}
          searchPlaceholder="Search by set number, name, year, theme, or status (e.g., 'In Box', 'Work in Progress')..."
          onRowClick={handleRowClick}
          exportFilename="sets"
          numericColumns={['total_parts']}
          defaultPageSize={20}
        />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {paginatedSets.map((set) => (
              <Card key={`${set.set_number}-${set.id}`}>
                <CardHeader>
                  <CardTitle>
                    <Link
                      href={
                        set.copy_count > 1
                          ? `/sets/${set.set_number}?from=sets&copy_id=${set.id}`
                          : `/sets/${set.set_number}?from=sets`
                      }
                      className="text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {set.copy_count > 1 ? `${set.set_number} ${set.copy_label}` : set.set_number}
                    </Link>
                  </CardTitle>
                  <CardDescription>{set.name}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm mb-4">
                    {set.year && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Year:</span>
                        <span className="font-medium">{set.year}</span>
                      </div>
                    )}
                    {set.theme_name && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Theme:</span>
                        <span className="font-medium">{set.theme_name}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Status:</span>
                      <span className="font-medium">
                        {getStatusLabel(set.status)}
                      </span>
                    </div>
                    {set.copy_count > 1 && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Copy:</span>
                        <span className="font-medium">{set.copy_label}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Parts:</span>
                      <span className="font-medium">{formatNumber(set.total_parts)}</span>
                    </div>
                  </div>
                  {set.image_url && (
                    <img
                      src={set.image_url}
                      alt={set.name}
                      className="w-full h-32 object-contain mb-4 rounded"
                    />
                  )}
                  {set.rebrickable_url && (
                    <Button variant="outline" className="w-full" asChild>
                      <a
                        href={set.rebrickable_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1"
                      >
                        View on Rebrickable <ExternalLink className="h-3 w-3" />
                      </a>
                    </Button>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
          {/* Pagination controls for card view */}
          <div className="flex items-center justify-between mt-4">
            <div className="flex items-center gap-2">
              <p className="text-sm text-muted-foreground">
                Showing {formatNumber(cardPageIndex * cardPageSize + 1)} to{' '}
                {formatNumber(Math.min((cardPageIndex + 1) * cardPageSize, setCopiesWithLabels?.length || 0))}{' '}
                of {formatNumber(setCopiesWithLabels?.length || 0)} results
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <p className="text-sm text-muted-foreground">Cards per page:</p>
                <Select
                  value={cardPageSize >= (setCopiesWithLabels?.length || 0) ? 'all' : String(cardPageSize)}
                  onValueChange={(value) => {
                    if (value === 'all') {
                      setCardPageSize(setCopiesWithLabels?.length || 0);
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

      {/* Sync Parts Dialog */}
      <Dialog open={syncPartsDialogOpen} onOpenChange={setSyncPartsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sync Parts from Rebrickable</DialogTitle>
            <DialogDescription>
              By default, this will only load parts for sets that don't have parts yet.
              Check "Reload all sets" to refresh parts for all sets.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="reload-all-sets"
                checked={reloadAllSets}
                onChange={(e) => setReloadAllSets(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-2 focus:ring-primary"
              />
              <Label htmlFor="reload-all-sets" className="text-sm font-normal cursor-pointer">
                Reload all sets (even if they already have parts)
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSyncPartsDialogOpen(false)}
              disabled={isRunning}
            >
              Cancel
            </Button>
            <Button onClick={handleSyncParts} disabled={isRunning}>
              {isRunning ? 'Syncing...' : 'Sync Parts'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync Sets Dialog */}
      <Dialog open={syncSetsDialogOpen} onOpenChange={(open) => {
        setSyncSetsDialogOpen(open);
        if (!open) {
          setNewSets([]);
          setSetStatuses({});
        }
      }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Sync Sets from Rebrickable</DialogTitle>
            <DialogDescription>
              {newSets.length === 0
                ? 'This will discover new sets from your Rebrickable account. You can then set the status for each new set individually.'
                : `Found ${newSets.length} new set(s). Set the status for each set below.`}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {newSets.length === 0 ? (
              <div className="grid gap-2">
                <Label htmlFor="default-status">Default Status for New Sets (can be changed per set)</Label>
                <Select value={defaultStatus} onValueChange={setDefaultStatus}>
                  <SelectTrigger id="default-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="in_box">In Box</SelectItem>
                    <SelectItem value="built">Built</SelectItem>
                    <SelectItem value="wip">Work in Progress</SelectItem>
                    <SelectItem value="loose_parts">Loose</SelectItem>
                    <SelectItem value="teardown">Teardown</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="text-sm text-muted-foreground">
                  Set the status for each new set. You can set different statuses for different sets.
                </div>
                <div className="space-y-3 max-h-[400px] overflow-y-auto">
                  {newSets.map((set) => (
                    <div key={set.set_num} className="flex items-start gap-4 p-3 border rounded-lg">
                      {set.image_url && (
                        <img
                          src={set.image_url}
                          alt={set.name}
                          className="w-16 h-16 object-contain rounded shrink-0"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="font-medium">{set.set_num}</div>
                        <div className="text-sm text-muted-foreground truncate">{set.name}</div>
                        {set.year && (
                          <div className="text-xs text-muted-foreground">Year: {set.year}</div>
                        )}
                        {set.theme_name && (
                          <div className="text-xs text-muted-foreground">Theme: {set.theme_name}</div>
                        )}
                        <div className="text-xs text-muted-foreground mt-1">
                          Quantity needed: {set.quantity_needed} {set.existing_count > 0 && `(already have ${set.existing_count})`}
                        </div>
                      </div>
                      <div className="w-48 shrink-0">
                        <Label htmlFor={`status-${set.set_num}`} className="text-xs">
                          Status
                        </Label>
                        <Select
                          value={setStatuses[set.set_num] || defaultStatus}
                          onValueChange={(value) => {
                            setSetStatuses((prev) => ({
                              ...prev,
                              [set.set_num]: value,
                            }));
                          }}
                        >
                          <SelectTrigger id={`status-${set.set_num}`} className="h-9">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="in_box">In Box</SelectItem>
                            <SelectItem value="built">Built</SelectItem>
                            <SelectItem value="wip">Work in Progress</SelectItem>
                            <SelectItem value="loose_parts">Loose</SelectItem>
                            <SelectItem value="teardown">Teardown</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setSyncSetsDialogOpen(false);
                setNewSets([]);
                setSetStatuses({});
              }}
              disabled={isRunning}
            >
              Cancel
            </Button>
            {newSets.length === 0 ? (
              <Button onClick={handleDiscoverSets} disabled={isRunning}>
                {isRunning ? 'Discovering...' : 'Discover New Sets'}
              </Button>
            ) : (
              <Button onClick={handleApplyStatusAssignments} disabled={isRunning}>
                {isRunning ? 'Syncing...' : 'Sync Sets'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

