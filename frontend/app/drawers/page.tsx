'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ColumnDef } from '@tanstack/react-table';
import { useDrawers, DrawerSummary } from '@/lib/hooks/use-drawers';
import { DisabledInSafeMode } from '@/components/disabled-in-safe-mode';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
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
import {
  CreateDrawerDialog,
  EditDrawerDialog,
  DeleteDrawerDialog,
} from '@/components/drawers/drawer-dialogs';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ViewToggle } from '@/components/view-toggle';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { MoreHorizontal, Plus, ChevronLeft, ChevronRight } from 'lucide-react';
import { formatNumber } from '@/lib/utils';

export default function DrawersPage() {
  const [viewMode, setViewMode] = useViewMode('table', 'drawers-view-mode');
  const [cardPageIndex, setCardPageIndex] = useState(0);
  const [cardPageSize, setCardPageSize] = useState(20);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedDrawer, setSelectedDrawer] = useState<DrawerSummary | null>(null);

  const router = useRouter();
  const { data: drawers, isLoading, error } = useDrawers();

  // Paginate drawers for card view
  const paginatedDrawers = useMemo(() => {
    if (!drawers) return [];
    const startIndex = cardPageIndex * cardPageSize;
    const endIndex = startIndex + cardPageSize;
    return drawers.slice(startIndex, endIndex);
  }, [drawers, cardPageIndex, cardPageSize]);

  const totalPages = Math.ceil((drawers?.length || 0) / cardPageSize);

  const handleRowClick = (drawer: DrawerSummary) => {
    router.push(`/drawers/${drawer.id}?from=drawers`);
  };

  const handleEdit = (drawer: DrawerSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedDrawer(drawer);
    setEditDialogOpen(true);
  };

  const handleDelete = (drawer: DrawerSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedDrawer(drawer);
    setDeleteDialogOpen(true);
  };

  const columns: ColumnDef<DrawerSummary>[] = [
    {
      accessorKey: 'name',
      header: 'Drawer',
      cell: ({ row }) => {
        const drawer = row.original;
        return (
          <Link
            href={`/drawers/${drawer.id}?from=drawers`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {drawer.name}
          </Link>
        );
      },
    },
    {
      accessorKey: 'description',
      header: 'Description',
      cell: ({ row }) => {
        const desc = row.original.description;
        return <span className="text-muted-foreground">{desc || '—'}</span>;
      },
    },
    {
      accessorKey: 'container_count',
      header: 'Containers',
      cell: ({ row }) => {
        return (
          <div className="text-right">
            {formatNumber(row.original.container_count)}
          </div>
        );
      },
    },
    {
      accessorKey: 'part_count',
      header: 'Parts',
      cell: ({ row }) => {
        return (
          <div className="text-right">
            {formatNumber(row.original.part_count)}
          </div>
        );
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const drawer = row.original;
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
                <span className="sr-only">Open menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={(e) => handleEdit(drawer, e)}>Edit</DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => handleDelete(drawer, e)}
                className="text-destructive"
              >
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];

  if (APP_SAFE_MODE) {
    return <DisabledInSafeMode title="Drawers" backHref="/sets" backLabel="Back to Sets" />;
  }

  if (isLoading) {
    return (
      <div className="container mx-auto py-4 md:py-8">
        <h1 className="text-2xl md:text-3xl font-bold mb-4 md:mb-6">Drawers</h1>
        <div className="text-muted-foreground">Loading drawers...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-4 md:py-8">
        <h1 className="text-2xl md:text-3xl font-bold mb-4 md:mb-6">Drawers</h1>
        <div className="text-destructive">Error loading drawers. Please try again.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-4 md:py-8">
      <div className="mb-4 md:mb-6">
        <Button variant="outline" asChild className="mb-4 min-h-[44px]">
          <Link href="/">← Back to Home</Link>
        </Button>
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <h1 className="text-2xl md:text-3xl font-bold">Drawers</h1>
            <div className="flex items-center gap-2">
              <ViewToggle
                viewMode={viewMode}
                onViewModeChange={(mode) => {
                  setViewMode(mode);
                  setCardPageIndex(0);
                }}
              />
              <Button onClick={() => setCreateDialogOpen(true)} className="min-h-[44px]">
                <Plus className="h-4 w-4 mr-2" />
                Add Drawer
              </Button>
            </div>
          </div>
          {!isLoading && drawers && (
            <div className="text-sm">
              <span className="text-muted-foreground">Total Drawers: </span>
              <span className="font-medium">{formatNumber(drawers.length)}</span>
            </div>
          )}
          {isLoading && (
            <p className="text-muted-foreground">Loading...</p>
          )}
        </div>
      </div>

      {drawers && drawers.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No drawers found. Create your first drawer to get started.
        </div>
      ) : viewMode === 'table' ? (
        <DataTable
          columns={columns}
          data={drawers || []}
          searchKeys={['name', 'description']}
          searchPlaceholder="Search by drawer name or description..."
          onRowClick={handleRowClick}
          exportFilename="drawers"
          defaultSorting={[{ id: 'name', desc: false }]}
          numericColumns={['container_count', 'part_count']}
          defaultPageSize={20}
        />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {paginatedDrawers.map((drawer) => (
            <Card key={drawer.id}>
              <CardHeader>
                <CardTitle>{drawer.name}</CardTitle>
                {drawer.description && (
                  <CardDescription>{drawer.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Containers:</span>
                    <span className="font-medium">{formatNumber(drawer.container_count)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Parts:</span>
                    <span className="font-medium">{formatNumber(drawer.part_count)}</span>
                  </div>
                </div>
                <Button className="mt-4 w-full" variant="outline" asChild>
                  <Link href={`/drawers/${drawer.id}`}>View Details</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
          </div>
          {/* Pagination controls for card view */}
          <div className="flex items-center justify-between mt-4">
            <div className="flex items-center gap-2">
              <p className="text-sm text-muted-foreground">
                Showing {formatNumber(cardPageIndex * cardPageSize + 1)} to{' '}
                {formatNumber(Math.min((cardPageIndex + 1) * cardPageSize, drawers?.length || 0))}{' '}
                of {formatNumber(drawers?.length || 0)} results
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <p className="text-sm text-muted-foreground">Cards per page:</p>
                <Select
                  value={cardPageSize >= (drawers?.length || 0) ? 'all' : String(cardPageSize)}
                  onValueChange={(value) => {
                    if (value === 'all') {
                      setCardPageSize(drawers?.length || 0);
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

      <CreateDrawerDialog open={createDialogOpen} onOpenChange={setCreateDialogOpen} />
      <EditDrawerDialog
        drawer={selectedDrawer}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
      />
      <DeleteDrawerDialog
        drawer={selectedDrawer}
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
      />
    </div>
  );
}
