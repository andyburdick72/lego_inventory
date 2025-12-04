'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ColumnDef } from '@tanstack/react-table';
import { useDrawer } from '@/lib/hooks/use-drawers';
import { useContainers, ContainerSummary } from '@/lib/hooks/use-containers';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { DataTable } from '@/components/data-table';
import { LayoutGrid, Table as TableIcon, MoreHorizontal, Plus, Trash2, Pencil } from 'lucide-react';
import { formatNumber } from '@/lib/utils';
import {
  CreateContainerDialog,
  EditContainerDialog,
  DeleteContainerDialog,
} from '@/components/containers/container-dialogs';
import Link from 'next/link';

type ViewMode = 'cards' | 'table';

export default function DrawerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const drawerId = parseInt(params.id as string, 10);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedContainer, setSelectedContainer] = useState<ContainerSummary | null>(null);

  const { data: drawer, isLoading: drawersLoading } = useDrawer(drawerId);

  const { data: containers, isLoading: containersLoading } =
    useContainers(drawerId);

  const handleRowClick = (container: ContainerSummary) => {
    router.push(`/containers/${container.id}`);
  };

  const handleEdit = (container: ContainerSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedContainer(container);
    setEditDialogOpen(true);
  };

  const handleDelete = (container: ContainerSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedContainer(container);
    setDeleteDialogOpen(true);
  };

  const columns: ColumnDef<ContainerSummary>[] = [
    {
      id: 'position',
      header: 'Position',
      accessorFn: (row) => {
        // Create a sortable value: row_index * 10000 + col_index
        // This allows sorting by row first, then column
        const rowIdx = row.row_index ?? 999;
        const colIdx = row.col_index ?? 999;
        return rowIdx * 10000 + colIdx;
      },
      cell: ({ row }) => {
        const container = row.original;
        const position =
          container.row_index !== null && container.col_index !== null
            ? `r${container.row_index} c${container.col_index}`
            : '—';
        return <span className="font-mono text-xs">{position}</span>;
      },
    },
    {
      accessorKey: 'name',
      header: 'Name',
      cell: ({ row }) => {
        const container = row.original;
        return (
          <Link
            href={`/containers/${container.id}`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {container.name}
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
      accessorKey: 'unique_parts',
      header: 'Unique Parts',
      cell: ({ row }) => {
        return (
          <div className="text-right">
            {formatNumber(row.original.unique_parts)}
          </div>
        );
      },
    },
    {
      accessorKey: 'part_count',
      header: 'Total Parts',
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
        const container = row.original;
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
                <span className="sr-only">Open menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/containers/${container.id}`}>View Details</Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => handleEdit(container, e)}>Edit</DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => handleDelete(container, e)}
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

  if (drawersLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-muted-foreground">Loading drawer...</div>
      </div>
    );
  }

  if (!drawer) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-destructive">Drawer not found.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/drawers">← Back to Drawers</Link>
        </Button>
        <h1 className="text-3xl font-bold">{drawer.name}</h1>
        {drawer.description && (
          <p className="text-muted-foreground mt-2">{drawer.description}</p>
        )}
        <div className="flex gap-4 mt-4 text-sm">
          <div>
            <span className="text-muted-foreground">Containers: </span>
            <span className="font-medium">{formatNumber(drawer.container_count)}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Parts: </span>
            <span className="font-medium">{formatNumber(drawer.part_count)}</span>
          </div>
          {drawer.rows !== null && (
            <div>
              <span className="text-muted-foreground">Rows: </span>
              <span className="font-medium">{formatNumber(drawer.rows)}</span>
            </div>
          )}
          {drawer.cols !== null && (
            <div>
              <span className="text-muted-foreground">Columns: </span>
              <span className="font-medium">{formatNumber(drawer.cols)}</span>
            </div>
          )}
        </div>
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-semibold">Containers</h2>
          <div className="flex items-center gap-2">
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Container
            </Button>
            <div className="flex items-center border rounded-md">
            <Button
              variant={viewMode === 'table' ? 'default' : 'ghost'}
              size="sm"
              className="rounded-r-none"
              onClick={() => setViewMode('table')}
            >
              <TableIcon className="h-4 w-4 mr-2" />
              Table
            </Button>
            <Button
              variant={viewMode === 'cards' ? 'default' : 'ghost'}
              size="sm"
              className="rounded-l-none"
              onClick={() => setViewMode('cards')}
            >
              <LayoutGrid className="h-4 w-4 mr-2" />
              Cards
            </Button>
          </div>
          </div>
        </div>
        {containersLoading ? (
          <div className="text-muted-foreground">Loading containers...</div>
        ) : containers && containers.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No containers in this drawer.
          </div>
        ) : viewMode === 'table' ? (
          <DataTable
            columns={columns}
            data={containers || []}
            searchKeys={['name', 'description']}
            searchPlaceholder="Search by container name or description..."
            onRowClick={handleRowClick}
            exportFilename={`drawer-${drawerId}-containers`}
            defaultSorting={[{ id: 'position', desc: false }]}
            numericColumns={['unique_parts', 'part_count']}
            defaultPageSize={20}
          />
        ) : (
          (() => {
            // Separate containers with positions from those without
            const containersWithPositions: Array<{ container: ContainerSummary; row: number; col: number }> = [];
            const containersWithoutPositions: ContainerSummary[] = [];
            
            containers?.forEach((container) => {
              if (container.row_index !== null && container.col_index !== null) {
                containersWithPositions.push({
                  container,
                  row: container.row_index,
                  col: container.col_index,
                });
              } else {
                containersWithoutPositions.push(container);
              }
            });
            
            // Check if we should use grid layout:
            // 1. Drawer has rows/cols defined, OR
            // 2. We have containers with positions (infer layout from positions)
            const hasExplicitGridLayout = drawer.rows !== null && drawer.cols !== null && drawer.rows > 0 && drawer.cols > 0;
            const hasContainersWithPositions = containersWithPositions.length > 0;
            const shouldUseGridLayout = hasExplicitGridLayout || hasContainersWithPositions;
            
            if (shouldUseGridLayout) {
              // Find the actual grid bounds from containers with positions
              let maxRow = -1;
              let maxCol = -1;
              containersWithPositions.forEach(({ row, col }) => {
                if (row > maxRow) maxRow = row;
                if (col > maxCol) maxCol = col;
              });
              
              // Calculate columns per row to handle non-uniform layouts
              const colsPerRow = new Map<number, number>();
              containersWithPositions.forEach(({ row, col }) => {
                const currentMax = colsPerRow.get(row) ?? -1;
                if (col > currentMax) {
                  colsPerRow.set(row, col);
                }
              });
              
              // Use drawer dimensions if available, otherwise infer from container positions
              const numRows = drawer.rows ?? maxRow + 1;
              const numCols = drawer.cols ?? maxCol + 1;
              
              // Use the drawer dimensions or actual max dimensions, whichever is larger
              const gridRows = Math.max(numRows, maxRow + 1);
              const gridCols = Math.max(numCols, maxCol + 1);
              
              return (
                <>
                  {containersWithPositions.length > 0 && (
                    <div className="space-y-2">
                      {Array.from({ length: gridRows }, (_, rowIndex) => {
                        const rowContainers = containersWithPositions.filter(({ row }) => row === rowIndex);
                        const colsInThisRow = colsPerRow.get(rowIndex) ?? -1;
                        const numColsInRow = colsInThisRow + 1;
                        
                        if (rowContainers.length === 0) return null;
                        
                        return (
                          <div
                            key={`row-${rowIndex}`}
                            className="grid gap-2"
                            style={{
                              gridTemplateColumns: `repeat(${numColsInRow}, minmax(0, 1fr))`,
                            }}
                          >
                            {rowContainers
                              .sort((a, b) => a.col - b.col)
                              .map(({ container, col }) => {
                                const position = `r${rowIndex} c${col}`;
                                
                                return (
                                  <Card 
                                    key={container.id} 
                                    className="min-h-[200px]"
                                  >
                                    <CardHeader>
                                      <CardTitle className="text-sm">{container.name}</CardTitle>
                                      {container.description && (
                                        <CardDescription className="text-xs">{container.description}</CardDescription>
                                      )}
                                      <CardDescription className="font-mono text-xs text-muted-foreground">
                                        {position}
                                      </CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-2">
                                      <div className="space-y-1 text-xs">
                                        <div className="flex justify-between">
                                          <span className="text-muted-foreground">Unique:</span>
                                          <span className="font-medium">{formatNumber(container.unique_parts)}</span>
                                        </div>
                                        <div className="flex justify-between">
                                          <span className="text-muted-foreground">Total:</span>
                                          <span className="font-medium">{formatNumber(container.part_count)}</span>
                                        </div>
                                      </div>
                                      <div className="flex gap-1 pt-2">
                                        <Button className="flex-1 text-xs h-7" variant="outline" size="sm" asChild>
                                          <Link href={`/containers/${container.id}`}>
                                            View
                                          </Link>
                                        </Button>
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          className="h-7 w-7 p-0"
                                          onClick={(e) => handleEdit(container, e)}
                                          title="Edit container"
                                        >
                                          <Pencil className="h-3 w-3" />
                                        </Button>
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                                          onClick={(e) => handleDelete(container, e)}
                                          title="Delete container"
                                        >
                                          <Trash2 className="h-3 w-3" />
                                        </Button>
                                      </div>
                                    </CardContent>
                                  </Card>
                                );
                              })}
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {containersWithoutPositions.length > 0 && (
                    <div className="mt-6">
                      <h3 className="text-lg font-semibold mb-4">Containers without position</h3>
                      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {containersWithoutPositions.map((container) => (
                          <Card key={container.id}>
                            <CardHeader>
                              <CardTitle>{container.name}</CardTitle>
                              {container.description && (
                                <CardDescription>{container.description}</CardDescription>
                              )}
                            </CardHeader>
                            <CardContent>
                              <div className="space-y-2 text-sm mb-4">
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Unique Parts:</span>
                                  <span className="font-medium">{formatNumber(container.unique_parts)}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Total Parts:</span>
                                  <span className="font-medium">{formatNumber(container.part_count)}</span>
                                </div>
                              </div>
                              <div className="flex gap-2">
                                <Button className="flex-1" variant="outline" asChild>
                                  <Link href={`/containers/${container.id}`}>
                                    View Details
                                  </Link>
                                </Button>
                                <Button
                                  variant="outline"
                                  size="icon"
                                  onClick={(e) => handleEdit(container, e)}
                                  title="Edit container"
                                >
                                  <Pencil className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="outline"
                                  size="icon"
                                  onClick={(e) => handleDelete(container, e)}
                                  title="Delete container"
                                  className="text-destructive hover:text-destructive"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              );
            } else {
              // Fallback to flexible grid layout when rows/cols aren't defined
              return (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {containers?.map((container) => {
                    const position =
                      container.row_index !== null && container.col_index !== null
                        ? `r${container.row_index} c${container.col_index}`
                        : null;

                    return (
                      <Card key={container.id}>
                        <CardHeader>
                          <CardTitle>{container.name}</CardTitle>
                          {container.description && (
                            <CardDescription>{container.description}</CardDescription>
                          )}
                          {position && (
                            <CardDescription className="font-mono text-xs">
                              {position}
                            </CardDescription>
                          )}
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2 text-sm mb-4">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Unique Parts:</span>
                              <span className="font-medium">{formatNumber(container.unique_parts)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Total Parts:</span>
                              <span className="font-medium">{formatNumber(container.part_count)}</span>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button className="flex-1" variant="outline" asChild>
                              <Link href={`/containers/${container.id}`}>
                                View Details
                              </Link>
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={(e) => handleEdit(container, e)}
                              title="Edit container"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={(e) => handleDelete(container, e)}
                              title="Delete container"
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              );
            }
          })()
        )}
      </div>

      <CreateContainerDialog
        drawerId={drawerId}
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
      <EditContainerDialog
        container={selectedContainer}
        drawerId={drawerId}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
      />
      <DeleteContainerDialog
        container={selectedContainer}
        drawerId={drawerId}
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
      />
    </div>
  );
}

