import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface PartMismatch {
  design_id: string;
  part_name: string;
  color_id: number;
  color_name: string;
  color_hex: string | null;
  required_quantity: number;
  available_quantity: number;
  delta: number; // available - required (negative = missing, positive = excess)
  part_url: string | null;
  part_img_url: string | null;
}

export interface SetMismatch {
  set_number: string;
  set_name: string;
  status: string;
  total_parts: number;
  missing_parts_count: number;
  excess_parts_count: number;
  total_missing_quantity: number;
  total_excess_quantity: number;
  mismatches: PartMismatch[];
  image_url: string | null;
  rebrickable_url: string | null;
}

export interface MismatchSummary {
  total_sets: number;
  sets_with_mismatches: number;
  total_missing_parts: number;
  total_excess_parts: number;
  total_missing_quantity: number;
  total_excess_quantity: number;
}

export interface PartColorMismatch {
  design_id: string;
  part_name: string;
  color_id: number;
  color_name: string;
  color_hex: string | null;
  inventory_quantity: number;
  required_quantity: number;
  delta: number;
  can_auto_update: boolean;
  part_url: string | null;
  part_img_url: string | null;
}

export function useMismatches(setNumber?: string, statuses?: string) {
  return useQuery<PartColorMismatch[]>({
    queryKey: ['mismatches', 'part-color', setNumber, statuses],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (setNumber) {
        params.append('set_number', setNumber);
      }
      if (statuses) {
        params.append('statuses', statuses);
      }
      const response = await api.get<PartColorMismatch[]>(
        `/api/v1/mismatches/part-color?${params.toString()}`
      );
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export function useSetMismatch(setNumber: string) {
  return useQuery<SetMismatch>({
    queryKey: ['mismatches', setNumber],
    queryFn: async () => {
      const response = await api.get<SetMismatch>(`/api/v1/mismatches/${setNumber}`);
      return response.data;
    },
    enabled: !!setNumber && !APP_SAFE_MODE,
  });
}

export function useMismatchSummary(statuses?: string) {
  return useQuery<MismatchSummary>({
    queryKey: ['mismatches', 'summary', statuses],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (statuses) {
        params.append('statuses', statuses);
      }
      const response = await api.get<MismatchSummary>(
        `/api/v1/mismatches/summary?${params.toString()}`
      );
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

