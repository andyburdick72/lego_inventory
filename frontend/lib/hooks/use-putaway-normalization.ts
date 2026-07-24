import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../api';

export interface PutawayUnknownRule {
  part_id: string;
  color_id: number;
  required_loose_qty: number;
  category_id: number | null;
  part_name: string | null;
  color_name: string | null;
  category_name: string | null;
}

export interface PutawayShortage {
  part_id: string;
  color_id: number;
  required_total: number;
  existing_total: number;
  missing: number;
  part_name: string | null;
  color_name: string | null;
}

export interface PutawaySurplus {
  part_id: string;
  color_id: number;
  required_total: number;
  existing_total: number;
  surplus: number;
  part_name: string | null;
  color_name: string | null;
}

export interface PutawayAction {
  part_id: string;
  color_id: number;
  container_id: number | null;
  old_quantity: number;
  new_quantity: number;
}

export interface PutawayPlan {
  plan_id: number;
  can_apply: boolean;
  unknown_rules: PutawayUnknownRule[];
  shortages: PutawayShortage[];
  surpluses: PutawaySurplus[];
  actions: PutawayAction[];
  summary: Record<string, any>;
}

export interface PutawayApplyResult {
  plan_id: number;
  applied: boolean;
  summary: Record<string, any>;
}

export function usePutawayNormalizationPlan(enabled: boolean = false) {
  return useQuery<PutawayPlan>({
    queryKey: ['putaway-normalization', 'plan'],
    queryFn: async () => {
      const res = await api.post<PutawayPlan>('/api/v1/putaway-normalization/plan');
      return res.data;
    },
    enabled,
    retry: false,
  });
}

export function useComputePutawayNormalizationPlan() {
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<PutawayPlan>('/api/v1/putaway-normalization/plan');
      return res.data;
    },
  });
}

export function useApplyPutawayNormalizationPlan() {
  return useMutation({
    mutationFn: async (planId: number) => {
      const res = await api.post<PutawayApplyResult>(
        `/api/v1/putaway-normalization/plans/${planId}/apply`
      );
      return res.data;
    },
  });
}


