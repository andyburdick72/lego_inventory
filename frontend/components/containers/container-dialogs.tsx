'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  useCreateContainer,
  useUpdateContainer,
  useDeleteContainer,
  ContainerSummary,
} from '@/lib/hooks/use-containers';
import { handleApiError } from '@/lib/api';
import { formatNumber, showApiErrorToast, showWarningToast } from '@/lib/utils';

interface CreateContainerDialogProps {
  drawerId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateContainerDialog({
  drawerId,
  open,
  onOpenChange,
}: CreateContainerDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rowIndex, setRowIndex] = useState<string>('');
  const [colIndex, setColIndex] = useState<string>('');
  const createContainer = useCreateContainer();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createContainer.mutateAsync({
        drawer_id: drawerId,
        name: name.trim(),
        description: description.trim() || undefined,
        row_index: rowIndex ? parseInt(rowIndex, 10) : undefined,
        col_index: colIndex ? parseInt(colIndex, 10) : undefined,
      });
      setName('');
      setDescription('');
      setRowIndex('');
      setColIndex('');
      onOpenChange(false);
    } catch (error) {
      showApiErrorToast(error);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Container</DialogTitle>
            <DialogDescription>Add a new container to this drawer.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="container-name">Name *</Label>
              <Input
                id="container-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., A1"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="container-description">Description</Label>
              <Textarea
                id="container-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="container-row">Row</Label>
                <Input
                  id="container-row"
                  type="number"
                  min="0"
                  value={rowIndex}
                  onChange={(e) => setRowIndex(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="container-col">Column</Label>
                <Input
                  id="container-col"
                  type="number"
                  min="0"
                  value={colIndex}
                  onChange={(e) => setColIndex(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createContainer.isPending || !name.trim()}>
              {createContainer.isPending ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface EditContainerDialogProps {
  container: ContainerSummary | null;
  drawerId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditContainerDialog({
  container,
  drawerId,
  open,
  onOpenChange,
}: EditContainerDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rowIndex, setRowIndex] = useState<string>('');
  const [colIndex, setColIndex] = useState<string>('');
  const updateContainer = useUpdateContainer(drawerId);

  useEffect(() => {
    if (container) {
      setName(container.name);
      setDescription(container.description || '');
      setRowIndex(container.row_index?.toString() || '');
      setColIndex(container.col_index?.toString() || '');
    }
  }, [container]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!container) return;
    try {
      const updates: {
        id: number;
        name?: string;
        description?: string | null;
        row_index?: number;
        col_index?: number;
      } = { id: container.id };

      // Only include fields that have changed
      let hasChanges = false;
      if (name.trim() !== container.name) {
        updates.name = name.trim();
        hasChanges = true;
      }
      // Check if description changed (including clearing it)
      const currentDescription = container.description || '';
      const newDescription = description.trim();
      if (newDescription !== currentDescription) {
        // Send empty string to clear description (API will convert to None)
        // Always include description in update if it changed, even if empty
        updates.description = newDescription;
        hasChanges = true;
      }
      const newRowIndex = rowIndex ? parseInt(rowIndex, 10) : undefined;
      const newColIndex = colIndex ? parseInt(colIndex, 10) : undefined;
      if (newRowIndex !== container.row_index) {
        updates.row_index = newRowIndex;
        hasChanges = true;
      }
      if (newColIndex !== container.col_index) {
        updates.col_index = newColIndex;
        hasChanges = true;
      }

      // Only call API if there are changes
      if (hasChanges) {
        await updateContainer.mutateAsync(updates);
      }
      onOpenChange(false);
    } catch (error) {
      showApiErrorToast(error);
    }
  };

  if (!container) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Container</DialogTitle>
            <DialogDescription>Update the container name and position.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-container-name">Name *</Label>
              <Input
                id="edit-container-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-container-description">Description</Label>
              <Textarea
                id="edit-container-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-container-row">Row</Label>
                <Input
                  id="edit-container-row"
                  type="number"
                  min="0"
                  value={rowIndex}
                  onChange={(e) => setRowIndex(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-container-col">Column</Label>
                <Input
                  id="edit-container-col"
                  type="number"
                  min="0"
                  value={colIndex}
                  onChange={(e) => setColIndex(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateContainer.isPending || !name.trim()}>
              {updateContainer.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface DeleteContainerDialogProps {
  container: ContainerSummary | null;
  drawerId?: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteContainerDialog({
  container,
  drawerId,
  open,
  onOpenChange,
}: DeleteContainerDialogProps) {
  const deleteContainer = useDeleteContainer(drawerId);
  const router = useRouter();

  const handleDelete = async () => {
    if (!container) return;
    try {
      await deleteContainer.mutateAsync({ id: container.id });
      onOpenChange(false);
    } catch (error) {
      const errorMessage = handleApiError(error);
      // Check if it's a conflict error (container has inventory)
      if (errorMessage.includes('inventory') || errorMessage.includes('merge')) {
        showWarningToast(
          `Cannot delete container "${container.name}" because it contains parts. ` +
            'Please move or merge the parts first.'
        );
      } else {
        showApiErrorToast(error);
      }
    }
  };

  if (!container) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Container</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete &quot;{container.name}&quot;? This action cannot be undone.
            {container.part_count > 0 && (
              <span className="block mt-2 text-destructive">
                Warning: This container contains {formatNumber(container.part_count)} part(s) and{' '}
                {formatNumber(container.unique_parts)} unique part type(s).
              </span>
            )}
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
            disabled={deleteContainer.isPending}
          >
            {deleteContainer.isPending ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

