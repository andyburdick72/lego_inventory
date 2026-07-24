import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface InventoryLocation {
  drawer_id: number | null;
  drawer_name: string;
  container_id: number | null;
  container_name: string;
  quantity: number;
}

export interface LocationReconciliationItem {
  design_id: string;
  part_name: string;
  color_id: number;
  color_name: string;
  color_hex: string | null;
  required_quantity: number;
  current_locations: InventoryLocation[];
  current_total: number;
  put_away_quantity: number;
  delta: number;
  needs_update: boolean;
  part_url: string | null;
  part_img_url: string | null;
}

export function useLocationReconciliationItems(type: 'loose-parts' | 'teardown' = 'loose-parts') {
  return useQuery<LocationReconciliationItem[]>({
    queryKey: ['location-reconciliation', 'items', type],
    queryFn: async () => {
      const endpoint = type === 'loose-parts' 
        ? '/api/v1/location-reconciliation/items/loose-parts'
        : '/api/v1/location-reconciliation/items/teardown';
      const response = await api.get<LocationReconciliationItem[]>(endpoint);
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export function useUpdateInventoryLocation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      design_id,
      color_id,
      quantity,
      drawer_id,
      container_id,
      is_teardown = false,
    }: {
      design_id: string;
      color_id: number;
      quantity: number;
      drawer_id?: number | null;
      container_id?: number | null;
      is_teardown?: boolean;
    }) => {
      const params = new URLSearchParams();
      params.append('quantity', quantity.toString());
      if (drawer_id !== undefined && drawer_id !== null) {
        params.append('drawer_id', drawer_id.toString());
      }
      if (container_id !== undefined && container_id !== null) {
        params.append('container_id', container_id.toString());
      }
      if (is_teardown) {
        params.append('is_teardown', 'true');
      }
      const response = await api.patch<{ message: string }>(
        `/api/v1/location-reconciliation/items/${design_id}/${color_id}?${params.toString()}`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['location-reconciliation'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });
}

export interface PutAwayBin {
  container_id: number | null;
  drawer_id: number | null;
  drawer_name: string | null;
  container_name: string | null;
}

export function usePutAwayBin() {
  return useQuery<PutAwayBin>({
    queryKey: ['put-away-bin'],
    queryFn: async () => {
      const response = await api.get<PutAwayBin>('/api/v1/containers/put-away-bin');
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export function useSetPutAwayBin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (container_id: number) => {
      const response = await api.post<{ message: string }>('/api/v1/containers/put-away-bin', {
        container_id,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['put-away-bin'] });
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      queryClient.invalidateQueries({ queryKey: ['location-reconciliation'] });
    },
  });
}

