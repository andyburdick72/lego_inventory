'use client';

import { Button } from '@/components/ui/button';
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
import { handleApiError } from '@/lib/api';
import { useContainers } from '@/lib/hooks/use-containers';
import { useDrawers } from '@/lib/hooks/use-drawers';
import {
  LoosePart,
  useDeleteInventory,
  useMoveInventory,
  useUpdateInventoryQuantity,
} from '@/lib/hooks/use-inventory';
import { formatNumber } from '@/lib/utils';
import { useEffect, useState } from 'react';

interface UpdateQuantityDialogProps {
  part: LoosePart | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UpdateQuantityDialog({ part, open, onOpenChange }: UpdateQuantityDialogProps) {
  const [quantity, setQuantity] = useState<string>('');
  const updateQuantity = useUpdateInventoryQuantity();

  useEffect(() => {
    if (part) {
      setQuantity(part.quantity.toString());
    }
  }, [part]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!part) return;
    try {
      const qty = parseInt(quantity, 10);
      if (isNaN(qty) || qty < 0) {
        alert('Quantity must be a non-negative number');
        return;
      }
      await updateQuantity.mutateAsync({
        inventoryId: part.id,
        quantity: qty,
      });
      onOpenChange(false);
    } catch (error) {
      alert(handleApiError(error));
    }
  };

  if (!part) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Update Quantity</DialogTitle>
            <DialogDescription>
              Update the quantity for {part.part_name || part.part_id} ({part.color_name || 'Unknown color'})
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="quantity">Quantity *</Label>
              <Input
                id="quantity"
                type="number"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="Enter quantity"
                required
              />
              <p className="text-sm text-muted-foreground">
                Current quantity: {formatNumber(part.quantity)}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateQuantity.isPending}>
              {updateQuantity.isPending ? 'Updating...' : 'Update'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface MoveInventoryDialogProps {
  part: LoosePart | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MoveInventoryDialog({ part, open, onOpenChange }: MoveInventoryDialogProps) {
  const [quantity, setQuantity] = useState<string>('');
  const [selectedDrawerId, setSelectedDrawerId] = useState<string>('');
  const [selectedContainerId, setSelectedContainerId] = useState<string>('');
  const moveInventory = useMoveInventory();
  const { data: drawers } = useDrawers();
  const { data: containers } = useContainers(
    selectedDrawerId ? parseInt(selectedDrawerId, 10) : 0
  );

  useEffect(() => {
    if (part) {
      setQuantity('');
      setSelectedDrawerId(part.drawer_id?.toString() || '');
      setSelectedContainerId(part.container_id?.toString() || '');
    }
  }, [part]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!part) return;
    try {
      const qty = parseInt(quantity, 10);
      if (isNaN(qty) || qty <= 0) {
        alert('Quantity must be a positive number');
        return;
      }
      if (qty > part.quantity) {
        alert(`Cannot move more than available quantity (${formatNumber(part.quantity)})`);
        return;
      }
      const containerId = selectedContainerId ? parseInt(selectedContainerId, 10) : null;
      await moveInventory.mutateAsync({
        inventoryId: part.id,
        toContainerId: containerId,
        quantity: qty,
      });
      onOpenChange(false);
    } catch (error) {
      alert(handleApiError(error));
    }
  };

  if (!part) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Move Parts</DialogTitle>
            <DialogDescription>
              Move parts from {part.part_name || part.part_id} ({part.color_name || 'Unknown color'})
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="move-quantity">Quantity to Move *</Label>
              <Input
                id="move-quantity"
                type="number"
                min="1"
                max={part.quantity}
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="Enter quantity"
                required
              />
              <p className="text-sm text-muted-foreground">
                Available: {formatNumber(part.quantity)}
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="move-drawer">Drawer (Optional)</Label>
              <Select value={selectedDrawerId} onValueChange={setSelectedDrawerId}>
                <SelectTrigger id="move-drawer">
                  <SelectValue placeholder="Select a drawer" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">No drawer</SelectItem>
                  {drawers?.map((drawer) => (
                    <SelectItem key={drawer.id} value={drawer.id.toString()}>
                      {drawer.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedDrawerId && (
              <div className="grid gap-2">
                <Label htmlFor="move-container">Container (Optional)</Label>
                <Select value={selectedContainerId} onValueChange={setSelectedContainerId}>
                  <SelectTrigger id="move-container">
                    <SelectValue placeholder="Select a container" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">No container</SelectItem>
                    {containers?.map((container) => (
                      <SelectItem key={container.id} value={container.id.toString()}>
                        {container.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="text-sm text-muted-foreground">
              <p>Current location: {part.drawer_name || '(none)'} / {part.container_label || '(none)'}</p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={moveInventory.isPending || !quantity}>
              {moveInventory.isPending ? 'Moving...' : 'Move'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface DeleteInventoryDialogProps {
  part: LoosePart | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteInventoryDialog({ part, open, onOpenChange }: DeleteInventoryDialogProps) {
  const deleteInventory = useDeleteInventory();

  const handleDelete = async () => {
    if (!part) return;
    try {
      await deleteInventory.mutateAsync(part.id);
      onOpenChange(false);
    } catch (error) {
      alert(handleApiError(error));
    }
  };

  if (!part) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Inventory Item</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this inventory item? This action cannot be undone.
            <div className="mt-2 space-y-1">
              <p><strong>Part:</strong> {part.part_name || part.part_id}</p>
              <p><strong>Color:</strong> {part.color_name || 'Unknown'}</p>
              <p><strong>Quantity:</strong> {formatNumber(part.quantity)}</p>
              <p><strong>Location:</strong> {part.drawer_name || '(none)'} / {part.container_label || '(none)'}</p>
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteInventory.isPending}
          >
            {deleteInventory.isPending ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

