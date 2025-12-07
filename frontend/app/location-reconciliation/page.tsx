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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { useContainers } from '@/lib/hooks/use-containers';
import { useDrawers } from '@/lib/hooks/use-drawers';
import {
  LocationReconciliationItem,
  useLocationReconciliationItems,
  usePutAwayBin,
  useUpdateInventoryLocation,
} from '@/lib/hooks/use-location-reconciliation';
import { formatNumber, isLightColor } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { AlertCircle, ArrowLeft, Download, Edit2, RefreshCw, Search } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

export default function LocationReconciliationPage() {
  const [activeTab, setActiveTab] = useState<'loose-parts' | 'teardown'>('loose-parts');
  const { data: items, isLoading, error, refetch } = useLocationReconciliationItems(activeTab);
  const { data: drawers } = useDrawers();
  const { data: putAwayBin } = usePutAwayBin();
  const updateMutation = useUpdateInventoryLocation();
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<LocationReconciliationItem | null>(null);
  const [selectedDrawerId, setSelectedDrawerId] = useState<string>('none');
  const [selectedContainerId, setSelectedContainerId] = useState<string>('none');
  const [quantity, setQuantity] = useState<string>('');
  const [filterNeedsUpdate, setFilterNeedsUpdate] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const selectedDrawer = drawers?.find((d) => d.id.toString() === selectedDrawerId);
  const { data: containers } = useContainers(
    selectedDrawer ? selectedDrawer.id : 0
  );

  // Auto-select container if drawer has only one container
  useEffect(() => {
    if (containers && containers.length === 1 && selectedDrawerId && selectedDrawerId !== 'none') {
      setSelectedContainerId(containers[0].id.toString());
    }
  }, [containers, selectedDrawerId]);

  const handleEdit = (item: LocationReconciliationItem) => {
    setEditingItem(item);

    if (activeTab === 'teardown') {
      // For teardown, default to put away bin
      if (putAwayBin?.drawer_id && putAwayBin?.container_id) {
        setSelectedDrawerId(putAwayBin.drawer_id.toString());
        setSelectedContainerId(putAwayBin.container_id.toString());
      } else {
        // Pre-select first current location if available
        if (item.current_locations.length > 0) {
          const firstLoc = item.current_locations[0];
          setSelectedDrawerId(firstLoc.drawer_id?.toString() || 'none');
          setSelectedContainerId(firstLoc.container_id?.toString() || 'none');
        } else {
          setSelectedDrawerId('none');
          setSelectedContainerId('none');
        }
      }
    } else {
      // For loose parts, pre-select first current location if available
      if (item.current_locations.length > 0) {
        const firstLoc = item.current_locations[0];
        setSelectedDrawerId(firstLoc.drawer_id?.toString() || 'none');
        setSelectedContainerId(firstLoc.container_id?.toString() || 'none');
      } else {
        setSelectedDrawerId('none');
        setSelectedContainerId('none');
      }
    }

    // Initialize quantity with current total if item exists, otherwise use required quantity
    setQuantity(item.current_total > 0 ? item.current_total.toString() : item.required_quantity.toString());
    setEditDialogOpen(true);
  };

  const handleSave = async () => {
    if (!editingItem) return;

    const quantityValue = parseInt(quantity, 10);
    if (isNaN(quantityValue) || quantityValue < 0) {
      alert('Please enter a valid non-negative quantity');
      return;
    }

    const drawerId = selectedDrawerId && selectedDrawerId !== 'none' ? parseInt(selectedDrawerId, 10) : null;
    const containerId = selectedContainerId && selectedContainerId !== 'none' ? parseInt(selectedContainerId, 10) : null;

    try {
      await updateMutation.mutateAsync({
        design_id: editingItem.design_id,
        color_id: editingItem.color_id,
        quantity: quantityValue,
        drawer_id: drawerId,
        container_id: containerId,
        is_teardown: activeTab === 'teardown',
      });
      setEditDialogOpen(false);
      setEditingItem(null);
      setSelectedDrawerId('none');
      setSelectedContainerId('none');
      setQuantity('');
    } catch (err) {
      console.error('Failed to update inventory location:', err);
      alert('Failed to update inventory location. Please try again.');
    }
  };

  const filteredItems = items?.filter((item) => {
    // Filter by needs update if enabled
    if (filterNeedsUpdate && !item.needs_update) {
      return false;
    }

    // Filter by search query (case-insensitive)
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      const matchesPartId = item.design_id.toLowerCase().includes(query);
      const matchesPartName = item.part_name.toLowerCase().includes(query);
      const matchesColor = item.color_name.toLowerCase().includes(query);

      if (!matchesPartId && !matchesPartName && !matchesColor) {
        return false;
      }
    }

    return true;
  }) || [];

  const exportToCSV = () => {
    const headers = [
      'Image',
      'Part ID',
      'Part Name',
      'Color',
      'Required (Set Parts)',
      activeTab === 'teardown' ? 'Current Location (Put Away)' : 'Current Locations (Not Put Away)',
      'Current Total',
      activeTab === 'teardown' ? 'In Wrong Location' : 'In Put Away',
      'Delta',
    ];

    const rows = filteredItems.map((item) => {
      const locations = item.current_locations
        .map((loc) => `${loc.drawer_name}${loc.container_name ? ` / ${loc.container_name}` : ''}: ${loc.quantity}`)
        .join('; ');

      return [
        item.part_img_url || '',
        item.design_id,
        item.part_name,
        item.color_name,
        item.required_quantity.toString(),
        locations || 'No location',
        item.current_total.toString(),
        item.put_away_quantity.toString(),
        item.delta.toString(),
      ];
    });

    const csvContent = [
      headers.map((h) => `"${h.replace(/"/g, '""')}"`).join(','),
      ...rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')),
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `location-reconciliation-${activeTab}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const summary = {
    total: items?.length || 0,
    needsUpdate: items?.filter((item) => item.needs_update).length || 0,
    withMismatch: items?.filter((item) => item.delta !== 0).length || 0,
    inPutAway: items?.filter((item) => item.put_away_quantity > 0).length || 0,
  };

  const columns: ColumnDef<LocationReconciliationItem>[] = [
    {
      accessorKey: 'part_img_url',
      header: 'Image',
      cell: ({ row }) => {
        const item = row.original;
        return (
          <div className="flex items-center justify-center">
            {item.part_img_url && (
              <img
                src={item.part_img_url}
                alt={item.part_name}
                className="w-12 h-12 object-contain"
              />
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'design_id',
      header: 'Part ID',
      cell: ({ row }) => {
        const item = row.original;
        return (
          <Link
            href={`/parts/${item.design_id}?from=location-reconciliation`}
            className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
          >
            {item.design_id}
          </Link>
        );
      },
    },
    {
      accessorKey: 'part_name',
      header: 'Part Name',
      cell: ({ row }) => row.original.part_name,
    },
    {
      accessorKey: 'color_name',
      header: 'Color',
      cell: ({ row }) => {
        const item = row.original;
        const bgColor = item.color_hex ? `#${item.color_hex}` : '#ffffff';
        const textColor = isLightColor(item.color_hex) ? '#000000' : '#ffffff';

        return (
          <div
            className="inline-flex items-center px-2 py-1 rounded border"
            style={{
              backgroundColor: bgColor,
              color: textColor,
            }}
          >
            {item.color_name || 'Unknown'}
          </div>
        );
      },
    },
    {
      accessorKey: 'required_quantity',
      header: 'Required (Set Parts)',
      cell: ({ row }) => formatNumber(row.original.required_quantity),
    },
    {
      accessorKey: 'current_locations',
      header: activeTab === 'teardown' ? 'Current Location (Put Away)' : 'Current Locations (Not Put Away)',
      cell: ({ row }) => {
        const item = row.original;
        if (item.current_locations.length === 0) {
          return <span className="text-muted-foreground italic">No location</span>;
        }
        return (
          <div className="space-y-1">
            {item.current_locations.map((loc, idx) => (
              <div key={idx} className="text-sm">
                <span className="font-medium">
                  {loc.drawer_name}
                  {loc.container_name && ` / ${loc.container_name}`}
                </span>
                : <span className="text-muted-foreground">{formatNumber(loc.quantity)}</span>
              </div>
            ))}
          </div>
        );
      },
    },
    {
      accessorKey: 'current_total',
      header: 'Current Total',
      cell: ({ row }) => formatNumber(row.original.current_total),
    },
    {
      accessorKey: 'put_away_quantity',
      header: activeTab === 'teardown' ? 'In Wrong Location' : 'In Put Away',
      cell: ({ row }) => {
        const qty = row.original.put_away_quantity;
        return qty > 0 ? (
          <span className="text-destructive font-semibold">{formatNumber(qty)}</span>
        ) : (
          <span className="text-muted-foreground">0</span>
        );
      },
    },
    {
      accessorKey: 'delta',
      header: 'Delta',
      cell: ({ row }) => {
        const delta = row.original.delta;
        if (delta === 0) {
          return <span className="text-muted-foreground">0</span>;
        }
        return (
          <span className={delta < 0 ? 'text-destructive font-semibold' : 'text-orange-600'}>
            {delta > 0 ? '+' : ''}
            {formatNumber(delta)}
          </span>
        );
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const item = row.original;
        return (
          <Button size="sm" variant="outline" onClick={() => handleEdit(item)}>
            <Edit2 className="w-4 h-4 mr-1" />
            Edit Location
          </Button>
        );
      },
    },
  ];

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-destructive" />
              Error Loading Reconciliation Items
            </CardTitle>
            <CardDescription>
              Failed to load location reconciliation items. Please try again.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Location Reconciliation</h1>
          <p className="text-muted-foreground mt-2">
            Reconcile inventory locations for Loose Parts and Teardown sets. Review where parts are currently
            stored and update locations as needed.
          </p>
        </div>
        <Link href="/">
          <Button variant="outline">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>
        </Link>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'loose-parts' | 'teardown')}>
        <TabsList>
          <TabsTrigger value="loose-parts">Loose Parts</TabsTrigger>
          <TabsTrigger value="teardown">Teardown</TabsTrigger>
        </TabsList>

        <TabsContent value="loose-parts" className="space-y-6 mt-6">
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Total Items</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatNumber(summary.total)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Needs Update</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-destructive">
                  {formatNumber(summary.needsUpdate)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Quantity Mismatch</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-orange-600">
                  {formatNumber(summary.withMismatch)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">In Put Away</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-destructive">
                  {formatNumber(summary.inPutAway)}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Loose Parts Reconciliation</CardTitle>
                  <CardDescription>
                    Parts should be in inventory but NOT in Put Away bin
                  </CardDescription>
                </div>
                <div className="flex items-center gap-4">
                  <Label htmlFor="filter-needs-update" className="flex items-center gap-2">
                    <input
                      id="filter-needs-update"
                      type="checkbox"
                      checked={filterNeedsUpdate}
                      onChange={(e) => setFilterNeedsUpdate(e.target.checked)}
                      className="w-4 h-4"
                    />
                    Show only items needing update
                  </Label>
                  <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex items-center justify-between gap-4">
                <div className="relative max-w-sm flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                  <Input
                    type="text"
                    placeholder="Search by Part ID, Part Name, or Color..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Button onClick={exportToCSV} variant="outline" size="sm">
                  <Download className="mr-2 h-4 w-4" />
                  Export CSV
                </Button>
              </div>
              <DataTable columns={columns} data={filteredItems} hideTopBar={true} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="teardown" className="space-y-6 mt-6">
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Total Items</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatNumber(summary.total)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Needs Update</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-destructive">
                  {formatNumber(summary.needsUpdate)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Quantity Mismatch</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-orange-600">
                  {formatNumber(summary.withMismatch)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">In Wrong Location</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-destructive">
                  {formatNumber(summary.inPutAway)}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Teardown Reconciliation</CardTitle>
                  <CardDescription>
                    Parts should be in Put Away bin
                  </CardDescription>
                </div>
                <div className="flex items-center gap-4">
                  <Label htmlFor="filter-needs-update-teardown" className="flex items-center gap-2">
                    <input
                      id="filter-needs-update-teardown"
                      type="checkbox"
                      checked={filterNeedsUpdate}
                      onChange={(e) => setFilterNeedsUpdate(e.target.checked)}
                      className="w-4 h-4"
                    />
                    Show only items needing update
                  </Label>
                  <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex items-center justify-between gap-4">
                <div className="relative max-w-sm flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                  <Input
                    type="text"
                    placeholder="Search by Part ID, Part Name, or Color..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Button onClick={exportToCSV} variant="outline" size="sm">
                  <Download className="mr-2 h-4 w-4" />
                  Export CSV
                </Button>
              </div>
              <DataTable columns={columns} data={filteredItems} hideTopBar={true} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Inventory Location & Quantity</DialogTitle>
            <DialogDescription>
              Set the storage location and quantity for {editingItem?.part_name} ({editingItem?.color_name}).
              {activeTab === 'teardown' && putAwayBin && putAwayBin.drawer_id && putAwayBin.container_id && (
                <span className="block mt-1 text-xs">
                  Teardown parts must be stored in Put Away bin
                  {putAwayBin.drawer_name && putAwayBin.container_name
                    ? ` (${putAwayBin.drawer_name} / ${putAwayBin.container_name})`
                    : '.'}
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-end gap-4">
              <div className="w-32">
                <Label htmlFor="quantity">Quantity</Label>
                <Input
                  id="quantity"
                  type="number"
                  min="0"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="mt-1"
                />
              </div>
              <p className="text-xs text-muted-foreground pb-2">
                Required from set parts: {formatNumber(editingItem?.required_quantity || 0)}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="drawer">Drawer</Label>
              <Select
                value={selectedDrawerId}
                onValueChange={(value) => {
                  setSelectedDrawerId(value);
                  if (value === 'none') {
                    setSelectedContainerId('none');
                  } else {
                    // Reset container when drawer changes (will be auto-selected if only one)
                    setSelectedContainerId('none');
                  }
                }}
              >
                <SelectTrigger id="drawer">
                  <SelectValue placeholder="Select drawer" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No drawer (unassigned)</SelectItem>
                  {drawers?.map((drawer) => (
                    <SelectItem key={drawer.id} value={drawer.id.toString()}>
                      {drawer.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="container">Container</Label>
              <Select
                value={selectedContainerId}
                onValueChange={setSelectedContainerId}
                disabled={!selectedDrawerId || selectedDrawerId === 'none'}
              >
                <SelectTrigger id="container">
                  <SelectValue placeholder="Select container" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No container (unassigned)</SelectItem>
                  {containers?.map((container) => (
                    <SelectItem key={container.id} value={container.id.toString()}>
                      {container.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="text-sm text-muted-foreground space-y-1">
              <div>
                <strong>Required quantity:</strong> {formatNumber(editingItem?.required_quantity || 0)}
              </div>
              <div>
                <strong>Current total:</strong> {formatNumber(editingItem?.current_total || 0)}
              </div>
              <div>
                <strong>Delta:</strong>{' '}
                <span
                  className={
                    (editingItem?.delta || 0) < 0
                      ? 'text-destructive font-semibold'
                      : (editingItem?.delta || 0) > 0
                        ? 'text-orange-600'
                        : ''
                  }
                >
                  {(editingItem?.delta || 0) > 0 ? '+' : ''}
                  {formatNumber(editingItem?.delta || 0)}
                </span>
              </div>
              {editingItem && editingItem.current_locations.length > 0 && (
                <div>
                  <strong>Current locations:</strong>
                  <ul className="list-disc list-inside mt-1">
                    {editingItem.current_locations.map((loc, idx) => (
                      <li key={idx}>
                        {loc.drawer_name}
                        {loc.container_name && ` / ${loc.container_name}`}:{' '}
                        {formatNumber(loc.quantity)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
