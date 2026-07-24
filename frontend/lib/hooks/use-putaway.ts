import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface StorageSuggestion {
  container_id: number | null;
  drawer_id: number | null;
  drawer_name: string | null;
  container_name: string | null;
  confidence: 'definitive' | 'high' | 'medium' | 'low';
  reason: string;
  quantity: number;
}

export interface PutawayPart {
  design_id: string;
  part_name: string;
  color_id: number;
  color_name: string;
  color_hex: string | null;
  quantity: number;
  part_url: string | null;
  part_img_url: string | null;
  inventory_id: number | null;
}

export interface PutawayPartWithSuggestion extends PutawayPart {
  suggestion: StorageSuggestion | null;
}

export function usePutawayPartsFromSet(setNumber: string) {
  return useQuery<PutawayPartWithSuggestion[]>({
    queryKey: ['putaway', 'parts-from-set', setNumber],
    queryFn: async () => {
      const response = await api.get<PutawayPartWithSuggestion[]>(
        `/api/v1/putaway/parts-from-set/${setNumber}`
      );
      return response.data;
    },
    enabled: !!setNumber && !APP_SAFE_MODE,
  });
}

export function usePutawayPartsInBin(search?: string) {
  return useQuery<PutawayPartWithSuggestion[]>({
    queryKey: ['putaway', 'parts-in-bin', search || ''],
    queryFn: async () => {
      const params = search ? { search } : {};
      const response = await api.get<PutawayPartWithSuggestion[]>('/api/v1/putaway/parts-in-bin', {
        params,
      });
      return response.data;
    },
    enabled: !APP_SAFE_MODE,
  });
}

export interface PartAssignment {
  design_id: string;
  color_id: number;
  quantity: number;
  container_id: number | null;
  inventory_id?: number | null;
}

export interface BatchAssignmentRequest {
  assignments: PartAssignment[];
  entry_point?: 'set' | 'bin' | null;
  set_number?: string | null;
}

export interface AssignmentResult {
  design_id: string;
  color_id: number;
  quantity: number;
  container_id: number | null;
  success: boolean;
  message: string | null;
}

export interface BatchAssignmentResult {
  total_requested: number;
  total_assigned: number;
  total_skipped: number;
  assignments: AssignmentResult[];
  errors: string[];
}

export function useBatchAssignParts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (request: BatchAssignmentRequest) => {
      const response = await api.post<BatchAssignmentResult>('/api/v1/putaway/batch-assign', request);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate relevant queries to refetch updated data
      queryClient.invalidateQueries({ queryKey: ['putaway'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['sets'] });
    },
  });
}

