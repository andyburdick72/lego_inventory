import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, handleApiError } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface Part {
  design_id: string;
  name: string;
  part_url: string;
  part_img_url: string;
  ignore_in_inventory: boolean;
  part_category_id: number | null;
  part_category_name: string | null;
}

export interface InventoryItem {
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

export interface PartInSet {
  set_number: string;
  set_name: string;
  status: string | null;
  color_id: number;
  color_name: string;
  hex: string | null;
  quantity: number;
  part_category_id: number | null;
  part_category_name: string | null;
}

export function usePart(designId: string) {
  return useQuery<Part>({
    queryKey: ['parts', designId],
    queryFn: async () => {
      const response = await api.get<Part>(`/api/v1/parts/${designId}`);
      return response.data;
    },
    enabled: !!designId,
  });
}

export function useLooseInventoryForPart(designId: string) {
  return useQuery<InventoryItem[]>({
    queryKey: ['parts', designId, 'loose'],
    queryFn: async () => {
      const response = await api.get<InventoryItem[]>(
        `/api/v1/parts/${designId}/loose`
      );
      return response.data;
    },
    enabled: !!designId && !APP_SAFE_MODE,
  });
}

export function useSetsForPart(designId: string) {
  return useQuery<PartInSet[]>({
    queryKey: ['parts', designId, 'sets'],
    queryFn: async () => {
      const response = await api.get<PartInSet[]>(
        `/api/v1/parts/${designId}/sets`
      );
      return response.data;
    },
    enabled: !!designId,
  });
}

export interface PartCount {
  design_id: string;
  part_name: string;
  total_qty: number;
  part_url: string | null;
  part_img_url: string | null;
  part_category_id: number | null;
  part_category_name: string | null;
}

export function usePartCounts() {
  return useQuery<PartCount[]>({
    queryKey: ['inventory', 'part-counts'],
    queryFn: async () => {
      const response = await api.get<PartCount[]>(
        '/api/v1/inventory/part-counts'
      );
      return response.data;
    },
  });
}

export interface PartColorCount {
  design_id: string;
  part_name: string;
  color_id: number;
  color_name: string;
  hex: string | null;
  total_qty: number;
  part_url: string | null;
  part_img_url: string | null;
}

export function usePartColorCounts() {
  return useQuery<PartColorCount[]>({
    queryKey: ['inventory', 'part-color-counts'],
    queryFn: async () => {
      const response = await api.get<PartColorCount[]>(
        '/api/v1/inventory/part-color-counts'
      );
      return response.data;
    },
  });
}

export interface LocationCount {
  location: string;
  total_qty: number;
  drawer_id: number | null;
  drawer_name: string | null;
  container_id: number | null;
  container_name: string | null;
}

export function useLocationCounts() {
  return useQuery<LocationCount[]>({
    queryKey: ['inventory', 'location-counts'],
    queryFn: async () => {
      const response = await api.get<LocationCount[]>(
        '/api/v1/inventory/location-counts'
      );
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export interface PartCategoryCount {
  part_category_id: number | null;
  part_category_name: string | null;
  part_count: number;
  total_qty: number;
}

export function usePartCategoryCounts() {
  return useQuery<PartCategoryCount[]>({
    queryKey: ['inventory', 'part-category-counts'],
    queryFn: async () => {
      const response = await api.get<PartCategoryCount[]>(
        '/api/v1/inventory/part-category-counts'
      );
      return response.data;
    },
  });
}

export interface UpdatePartRequest {
  ignore_in_inventory?: boolean;
}

export function usePartAliases(designId: string) {
  return useQuery<string[]>({
    queryKey: ['parts', designId, 'aliases'],
    queryFn: async () => {
      const response = await api.get<string[]>(
        `/api/v1/parts/${designId}/aliases`
      );
      return response.data;
    },
    enabled: !!designId,
  });
}

export function useUpdatePart(designId: string) {
  const queryClient = useQueryClient();

  return useMutation<Part, Error, UpdatePartRequest>({
    mutationFn: async (updateData: UpdatePartRequest) => {
      const response = await api.patch<Part>(
        `/api/v1/parts/${designId}`,
        updateData
      );
      return response.data;
    },
    onSuccess: (updatedPart) => {
      // Invalidate and refetch part data
      queryClient.setQueryData(['parts', designId], updatedPart);
      queryClient.invalidateQueries({ queryKey: ['parts', designId] });
    },
    onError: (error) => {
      console.error('Failed to update part:', error);
      alert(handleApiError(error));
    },
  });
}

