import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface ElementStoragePattern {
  container_id: number;
  drawer_id: number;
  drawer_name: string;
  container_name: string;
  element_count: number;
  total_quantity: number;
  is_exclusive: number; // 1 if exclusive, 0 otherwise
}

export interface PartStoragePattern {
  container_id: number;
  drawer_id: number;
  drawer_name: string;
  container_name: string;
  design_id: string;
  part_name: string;
  color_count: number;
  total_quantity: number;
}

export interface CategoryStoragePattern {
  container_id: number;
  drawer_id: number;
  drawer_name: string;
  container_name: string;
  part_category_id: number;
  part_category_name: string | null;
  part_count: number;
  element_count: number;
  total_quantity: number;
}

export function useElementStoragePatterns() {
  return useQuery<ElementStoragePattern[]>({
    queryKey: ['storage-hierarchy', 'patterns', 'elements'],
    queryFn: async () => {
      const response = await api.get<ElementStoragePattern[]>(
        '/api/v1/storage-hierarchy/patterns/elements'
      );
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export function usePartStoragePatterns() {
  return useQuery<PartStoragePattern[]>({
    queryKey: ['storage-hierarchy', 'patterns', 'parts'],
    queryFn: async () => {
      const response = await api.get<PartStoragePattern[]>(
        '/api/v1/storage-hierarchy/patterns/parts'
      );
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export function useCategoryStoragePatterns() {
  return useQuery<CategoryStoragePattern[]>({
    queryKey: ['storage-hierarchy', 'patterns', 'categories'],
    queryFn: async () => {
      const response = await api.get<CategoryStoragePattern[]>(
        '/api/v1/storage-hierarchy/patterns/categories'
      );
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export interface ElementStorageStrategy {
  design_id: string;
  color_id: number;
  part_name: string;
  part_img_url: string | null;
  part_category_id: number | null;
  part_category_name: string | null;
  color_name: string;
  color_hex: string | null;
  storage_strategy: string; // 'by_element', 'by_part', 'by_category_size', 'by_category', 'unassigned', 'unknown', 'in_putaway_bin'
  drawer_id: number | null;
  drawer_name: string | null;
  container_id: number | null;
  container_name: string | null;
  quantity: number;
  evidence: string;
}

export function useElementStorageStrategies() {
  return useQuery<ElementStorageStrategy[]>({
    queryKey: ['storage-hierarchy', 'strategies'],
    queryFn: async () => {
      const response = await api.get<ElementStorageStrategy[]>(
        '/api/v1/storage-hierarchy/strategies'
      );
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

