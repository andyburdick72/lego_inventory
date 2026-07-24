import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, handleApiError } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface DrawerSummary {
  id: number;
  name: string;
  description: string | null;
  kind: string | null;
  cols: number | null;
  rows: number | null;
  sort_index: number;
  container_count: number;
  part_count: number;
}

export interface CreateDrawerRequest {
  name: string;
  description?: string;
  rows?: number;
  cols?: number;
}

export interface RenameDrawerRequest {
  id: number;
  new_name: string;
  description?: string;
  rows?: number;
  cols?: number;
}

export interface DeleteDrawerRequest {
  id: number;
}

export function useDrawers() {
  return useQuery<DrawerSummary[]>({
    queryKey: ['drawers'],
    queryFn: async () => {
      const response = await api.get<DrawerSummary[]>('/api/v1/drawers');
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export function useDrawer(drawerId: number) {
  return useQuery<DrawerSummary>({
    queryKey: ['drawers', drawerId],
    queryFn: async () => {
      const response = await api.get<DrawerSummary>(`/api/v1/drawers/${drawerId}`);
      return response.data;
    },
    enabled: !!drawerId && !APP_SAFE_MODE,
  });
}

export function useCreateDrawer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateDrawerRequest) => {
      const response = await api.post<{ id: number }>('/api/v1/drawers/create', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

export function useRenameDrawer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: RenameDrawerRequest) => {
      const response = await api.post<{ updated: number }>('/api/v1/drawers/rename', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

export function useDeleteDrawer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: DeleteDrawerRequest) => {
      const response = await api.post<{ deleted: number }>('/api/v1/drawers/delete', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

