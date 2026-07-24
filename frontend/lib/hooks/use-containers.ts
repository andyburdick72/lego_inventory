import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface ContainerSummary {
  id: number;
  name: string;
  description: string | null;
  row_index: number | null;
  col_index: number | null;
  sort_index: number;
  part_count: number;
  unique_parts: number;
}

export interface CreateContainerRequest {
  drawer_id: number;
  name: string;
  description?: string;
  row_index?: number;
  col_index?: number;
  sort_index?: number;
}

export interface RenameContainerRequest {
  id: number;
  new_name: string;
}

export interface MoveContainerRequest {
  id: number;
  new_drawer_id?: number;
  row_index?: number;
  col_index?: number;
  sort_index?: number;
}

export interface UpdateContainerRequest {
  id: number;
  name?: string;
  description?: string;
  row_index?: number;
  col_index?: number;
}

export interface DeleteContainerRequest {
  id: number;
}

export interface ContainerDetails {
  id: number;
  drawer_id: number;
  name: string;
  description: string | null;
  row_index: number | null;
  col_index: number | null;
  drawer_name: string;
  is_put_away_bin?: number | null;
}

export interface ContainerPart {
  design_id: string;
  part_name: string;
  color_id: number;
  color_name: string;
  hex: string | null;
  quantity: number;
  part_url: string | null;
  part_img_url: string | null;
}

export function useContainers(drawerId: number) {
  return useQuery<ContainerSummary[]>({
    queryKey: ['containers', drawerId],
    queryFn: async () => {
      const response = await api.get<ContainerSummary[]>(
        `/api/v1/containers?drawer_id=${drawerId}`
      );
      return response.data;
    },
    enabled: !!drawerId && !APP_SAFE_MODE,
  });
}

export function useContainer(containerId: number) {
  return useQuery<ContainerDetails>({
    queryKey: ['containers', containerId, 'details'],
    queryFn: async () => {
      const response = await api.get<ContainerDetails>(`/api/v1/containers/${containerId}`);
      return response.data;
    },
    enabled: !!containerId && !APP_SAFE_MODE,
  });
}

export function useContainerParts(containerId: number) {
  return useQuery<ContainerPart[]>({
    queryKey: ['containers', containerId, 'parts'],
    queryFn: async () => {
      const response = await api.get<ContainerPart[]>(`/api/v1/containers/${containerId}/parts`);
      return response.data;
    },
    enabled: !!containerId && !APP_SAFE_MODE,
  });
}

export function useCreateContainer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateContainerRequest) => {
      const response = await api.post<{ id: number }>('/api/v1/containers/create', data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['containers', variables.drawer_id] });
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

export function useRenameContainer(drawerId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: RenameContainerRequest) => {
      const response = await api.post<{ updated: number }>('/api/v1/containers/rename', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      if (drawerId) {
        queryClient.invalidateQueries({ queryKey: ['containers', drawerId] });
      }
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

export function useMoveContainer(drawerId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: MoveContainerRequest) => {
      const response = await api.post<{ updated: number }>('/api/v1/containers/move', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      if (drawerId) {
        queryClient.invalidateQueries({ queryKey: ['containers', drawerId] });
      }
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

export function useUpdateContainer(drawerId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: UpdateContainerRequest) => {
      const response = await api.post<{ updated: number }>('/api/v1/containers/update', data);
      return response.data;
    },
    onSuccess: async () => {
      // Invalidate all container queries (this will match ['containers', drawerId] too)
      await queryClient.invalidateQueries({ queryKey: ['containers'] });
      // Also explicitly invalidate and refetch the specific drawer's containers if drawerId is provided
      if (drawerId !== undefined) {
        await queryClient.invalidateQueries({ queryKey: ['containers', drawerId] });
        await queryClient.refetchQueries({ queryKey: ['containers', drawerId] });
      }
      await queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

export function useDeleteContainer(drawerId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: DeleteContainerRequest) => {
      const response = await api.post<{ deleted: number }>('/api/v1/containers/delete', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      if (drawerId) {
        queryClient.invalidateQueries({ queryKey: ['containers', drawerId] });
      }
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}

