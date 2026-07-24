import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

export type StorageRuleKind = 'element' | 'part' | 'category_subset' | 'category';

export interface StorageRule {
  id: number;
  kind: StorageRuleKind;
  container_id: number;
  container_name: string | null;
  drawer_id: number | null;
  drawer_name: string | null;

  part_id: string | null;
  color_id: number | null;
  color_name: string | null;
  category_id: number | null;
  category_name: string | null;
  name: string | null;
  active: number | null;
}

export interface CreateStorageRuleRequest {
  kind: StorageRuleKind;
  container_id: number;
  part_id?: string | null;
  color_id?: number | null;
  category_id?: number | null;
  name?: string | null;
  active?: boolean;
}

export interface UpdateStorageRuleRequest {
  id: number;
  container_id?: number | null;
  name?: string | null;
  active?: boolean | null;
}

export interface StorageRuleSubsetMember {
  part_id: string;
  part_name: string | null;
}

export interface StorageRuleInferenceProposal {
  kind: StorageRuleKind;
  container_id: number;
  part_id: string | null;
  color_id: number | null;
  category_id: number | null;
  name: string | null;
  source: string;
  evidence: string;
  issues: string[];
}

export function useStorageRules(filters?: {
  kind?: string;
  active?: boolean;
  part_id?: string;
  category_id?: number;
  container_id?: number;
}) {
  return useQuery<StorageRule[]>({
    queryKey: ['storage-rules', filters || {}],
    queryFn: async () => {
      const res = await api.get<StorageRule[]>('/api/v1/storage-rules', { params: filters });
      return res.data;
    },
  });
}

export function useCreateStorageRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (req: CreateStorageRuleRequest) => {
      const res = await api.post<StorageRule>('/api/v1/storage-rules', req);
      return res.data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['storage-rules'] });
    },
  });
}

export function useUpdateStorageRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (req: UpdateStorageRuleRequest) => {
      const res = await api.patch<{ message: string }>(`/api/v1/storage-rules/${req.id}`, {
        container_id: req.container_id,
        name: req.name,
        active: req.active,
      });
      return res.data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['storage-rules'] });
    },
  });
}

export function useDeleteStorageRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await api.delete<{ message: string }>(`/api/v1/storage-rules/${id}`);
      return res.data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['storage-rules'] });
    },
  });
}

export function useStorageRuleSubsetMembers(ruleId: number) {
  return useQuery<StorageRuleSubsetMember[]>({
    queryKey: ['storage-rules', ruleId, 'parts'],
    queryFn: async () => {
      const res = await api.get<StorageRuleSubsetMember[]>(`/api/v1/storage-rules/${ruleId}/parts`);
      return res.data;
    },
    enabled: !!ruleId,
  });
}

export function useAddStorageRuleSubsetMembers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { id: number; part_ids: string[] }) => {
      const res = await api.post<{ added: number }>(`/api/v1/storage-rules/${args.id}/parts`, {
        part_ids: args.part_ids,
      });
      return res.data;
    },
    onSuccess: async (_data, vars) => {
      await qc.invalidateQueries({ queryKey: ['storage-rules', vars.id, 'parts'] });
    },
  });
}

export function useRemoveStorageRuleSubsetMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { id: number; part_id: string }) => {
      const res = await api.delete<{ message: string }>(
        `/api/v1/storage-rules/${args.id}/parts/${encodeURIComponent(args.part_id)}`
      );
      return res.data;
    },
    onSuccess: async (_data, vars) => {
      await qc.invalidateQueries({ queryKey: ['storage-rules', vars.id, 'parts'] });
    },
  });
}

export function useStorageRuleInference(enabled: boolean = true) {
  return useQuery<StorageRuleInferenceProposal[]>({
    queryKey: ['storage-rules', 'infer'],
    queryFn: async () => {
      const res = await api.get<StorageRuleInferenceProposal[]>('/api/v1/storage-rules/infer');
      return res.data;
    },
    enabled,
  });
}


