import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface TotalPartCount {
  total_count: number;
}

export interface LoosePart {
  id: number;
  part_id: string;
  color_id: number;
  color_name: string | null;
  color_hex: string | null;
  quantity: number;
  status: string;
  drawer_id: number | null;
  drawer_name: string | null;
  container_id: number | null;
  container_label: string | null;
  set_number: string | null;
  set_name: string | null;
  part_name: string | null;
  image_url: string | null;
  rebrickable_url: string | null;
}

export function useTotalPartCount() {
  return useQuery<TotalPartCount>({
    queryKey: ['inventory', 'total-count'],
    queryFn: async () => {
      const response = await api.get<TotalPartCount>('/api/v1/inventory/total-count');
      return response.data;
    },
  });
}

export function useLooseParts() {
  return useQuery<LoosePart[]>({
    queryKey: ['inventory', 'loose'],
    queryFn: async () => {
      const response = await api.get<LoosePart[]>('/api/v1/inventory/loose');
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export interface UpdateQuantityRequest {
  quantity: number;
}

export interface MoveInventoryRequest {
  to_container_id: number | null;
  quantity: number;
}

export function useUpdateInventoryQuantity() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ inventoryId, quantity }: { inventoryId: number; quantity: number }) => {
      const response = await api.patch(`/api/v1/inventory/loose/${inventoryId}/quantity`, {
        quantity,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'loose'] });
      queryClient.invalidateQueries({ queryKey: ['inventory', 'multiple-locations'] });
    },
  });
}

export function useUpdateInventoryLocation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ inventoryId, containerId }: { inventoryId: number; containerId: number | null }) => {
      const response = await api.patch(`/api/v1/inventory/loose/${inventoryId}/location`, {
        container_id: containerId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'loose'] });
      queryClient.invalidateQueries({ queryKey: ['inventory', 'multiple-locations'] });
    },
  });
}

export function useDeleteInventory() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (inventoryId: number) => {
      const response = await api.delete(`/api/v1/inventory/loose/${inventoryId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'loose'] });
      queryClient.invalidateQueries({ queryKey: ['inventory', 'multiple-locations'] });
    },
  });
}

export function useMoveInventory() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ inventoryId, toContainerId, quantity }: { inventoryId: number; toContainerId: number | null; quantity: number }) => {
      const response = await api.post(`/api/v1/inventory/loose/${inventoryId}/move`, {
        to_container_id: toContainerId,
        quantity,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'loose'] });
      queryClient.invalidateQueries({ queryKey: ['inventory', 'multiple-locations'] });
    },
  });
}

export interface ElementLocation {
  drawer_id: number | null;
  drawer_name: string | null;
  container_id: number | null;
  container_name: string | null;
  quantity: number;
  inventory_id: number | null;
}

export interface MultipleLocationsElement {
  design_id: string;
  part_name: string;
  color_id: number;
  color_name: string;
  color_hex: string | null;
  part_url: string | null;
  part_img_url: string | null;
  location_count: number;
  total_quantity: number;
  locations: ElementLocation[];
}

export function useMultipleLocationsElements() {
  return useQuery<MultipleLocationsElement[]>({
    queryKey: ['inventory', 'multiple-locations'],
    queryFn: async () => {
      const response = await api.get<MultipleLocationsElement[]>('/api/v1/inventory/multiple-locations');
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

