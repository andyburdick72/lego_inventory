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
import { LEGOSet, useSets } from '@/lib/hooks/use-sets';
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
  const router = useRouter();
  const { data: sets, isLoading, error } = useSets();

  // Paginate sets for card view
  const paginatedSets = useMemo(() => {
    if (!sets) return [];
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return sets.slice(startIndex, endIndex);
  }, [sets, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((sets?.length || 0) / cardPageSize);

  const handleRowClick = (set: LEGOSet) => {
    router.push(`/sets/${set.set_number}?from=sets`);
  };

  const columns: ColumnDef<LEGOSet>[] = [
    {
      accessorKey: 'set_number',
      header: 'Set Number',
      cell: ({ row }) => {
        const set = row.original;
        return (
          <Link
            href={`/sets/${set.set_number}?from=sets`}
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
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const status = row.original.status;
        return (
          <span>{getStatusLabel(status)}</span>
        );
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

  const handleSyncSets = async () => {
    setIsRunning(true);
    try {
      const response = await api.post('/api/v1/scripts/sync-rebrickable-sets', {
        default_status: defaultStatus,
      });
      showSuccessToast(response.data.message);
      setSyncSetsDialogOpen(false);
      // Refresh sets data
      window.location.reload();
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
          {!isLoading && sets && (
            <div className="text-sm">
              <span className="text-muted-foreground">Total Sets: </span>
              <span className="font-medium">{formatNumber(sets.length)}</span>
            </div>
          )}
          {isLoading && (
            <p className="text-muted-foreground">Loading...</p>
          )}
        </div>
      </div>

      {sets && sets.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No sets found.
        </div>
      ) : viewMode === 'table' ? (
        <DataTable
          columns={columns}
          data={sets || []}
          searchKeys={['set_number', 'name', 'year', 'theme_name', 'status']}
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
              <Card key={set.set_number}>
                <CardHeader>
                  <CardTitle>
                    <Link
                      href={`/sets/${set.set_number}?from=sets`}
                      className="text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {set.set_number}
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
                {formatNumber(Math.min((cardPageIndex + 1) * cardPageSize, sets?.length || 0))}{' '}
                of {formatNumber(sets?.length || 0)} results
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <p className="text-sm text-muted-foreground">Cards per page:</p>
                <Select
                  value={cardPageSize >= (sets?.length || 0) ? 'all' : String(cardPageSize)}
                  onValueChange={(value) => {
                    if (value === 'all') {
                      setCardPageSize(sets?.length || 0);
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
      <Dialog open={syncSetsDialogOpen} onOpenChange={setSyncSetsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sync Sets from Rebrickable</DialogTitle>
            <DialogDescription>
              This will sync all sets from your Rebrickable account. New sets will be added with the selected default status.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="default-status">Default Status for New Sets</Label>
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
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSyncSetsDialogOpen(false)}
              disabled={isRunning}
            >
              Cancel
            </Button>
            <Button onClick={handleSyncSets} disabled={isRunning}>
              {isRunning ? 'Syncing...' : 'Sync Sets'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

