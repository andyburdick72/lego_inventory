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
  useCreateDrawer,
  useRenameDrawer,
  useDeleteDrawer,
  DrawerSummary,
} from '@/lib/hooks/use-drawers';
import { formatNumber, showApiErrorToast } from '@/lib/utils';

interface CreateDrawerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateDrawerDialog({ open, onOpenChange }: CreateDrawerDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rows, setRows] = useState<string>('');
  const [cols, setCols] = useState<string>('');
  const createDrawer = useCreateDrawer();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createDrawer.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
        rows: rows ? parseInt(rows, 10) : undefined,
        cols: cols ? parseInt(cols, 10) : undefined,
      });
      setName('');
      setDescription('');
      setRows('');
      setCols('');
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
            <DialogTitle>Create Drawer</DialogTitle>
            <DialogDescription>Add a new drawer to organize your LEGO parts.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Wall A"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="rows">Rows</Label>
                <Input
                  id="rows"
                  type="number"
                  min="0"
                  value={rows}
                  onChange={(e) => setRows(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="cols">Columns</Label>
                <Input
                  id="cols"
                  type="number"
                  min="0"
                  value={cols}
                  onChange={(e) => setCols(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createDrawer.isPending || !name.trim()}>
              {createDrawer.isPending ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface EditDrawerDialogProps {
  drawer: DrawerSummary | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditDrawerDialog({ drawer, open, onOpenChange }: EditDrawerDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rows, setRows] = useState<string>('');
  const [cols, setCols] = useState<string>('');
  const renameDrawer = useRenameDrawer();

  useEffect(() => {
    if (drawer) {
      setName(drawer.name);
      setDescription(drawer.description || '');
      setRows(drawer.rows?.toString() || '');
      setCols(drawer.cols?.toString() || '');
    }
  }, [drawer]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!drawer) return;
    try {
      await renameDrawer.mutateAsync({
        id: drawer.id,
        new_name: name.trim(),
        description: description.trim() || undefined,
        rows: rows ? parseInt(rows, 10) : undefined,
        cols: cols ? parseInt(cols, 10) : undefined,
      });
      onOpenChange(false);
    } catch (error) {
      showApiErrorToast(error);
    }
  };

  if (!drawer) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Drawer</DialogTitle>
            <DialogDescription>Update the drawer name and description.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-name">Name *</Label>
              <Input
                id="edit-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-rows">Rows</Label>
                <Input
                  id="edit-rows"
                  type="number"
                  min="0"
                  value={rows}
                  onChange={(e) => setRows(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-cols">Columns</Label>
                <Input
                  id="edit-cols"
                  type="number"
                  min="0"
                  value={cols}
                  onChange={(e) => setCols(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={renameDrawer.isPending || !name.trim()}>
              {renameDrawer.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface DeleteDrawerDialogProps {
  drawer: DrawerSummary | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteDrawerDialog({ drawer, open, onOpenChange }: DeleteDrawerDialogProps) {
  const deleteDrawer = useDeleteDrawer();
  const router = useRouter();

  const handleDelete = async () => {
    if (!drawer) return;
    try {
      await deleteDrawer.mutateAsync({ id: drawer.id });
      onOpenChange(false);
      router.push('/drawers');
    } catch (error) {
      showApiErrorToast(error);
    }
  };

  if (!drawer) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Drawer</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete &quot;{drawer.name}&quot;? This action cannot be undone.
            {drawer.container_count > 0 && (
              <span className="block mt-2 text-destructive">
                Warning: This drawer contains {formatNumber(drawer.container_count)} container(s) and{' '}
                {formatNumber(drawer.part_count)} part(s).
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
            disabled={deleteDrawer.isPending}
          >
            {deleteDrawer.isPending ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

