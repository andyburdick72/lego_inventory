import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface SetsCountResponse {
  count: number;
}

export function useSetsCount() {
  return useQuery<SetsCountResponse>({
    queryKey: ['sets', 'count'],
    queryFn: async () => {
      const response = await api.get<SetsCountResponse>('/api/v1/sets/count');
      return response.data;
    },
  });
}

export interface LEGOSet {
  set_number: string;
  name: string;
  year: number | null;
  theme_id: number | null;
  theme_name: string | null;
  status: string;
  total_parts: number | null;
  quantity: number;
  image_url: string | null;
  rebrickable_url: string | null;
}

export interface LEGOSetCopy {
  id: number;
  set_number: string;
  name: string;
  year: number | null;
  theme_id: number | null;
  theme_name: string | null;
  status: string;
  added_at: string | null;
  total_parts: number | null;
  image_url: string | null;
  rebrickable_url: string | null;
}

export function useSets() {
  return useQuery<LEGOSet[]>({
    queryKey: ['sets'],
    queryFn: async () => {
      const response = await api.get<LEGOSet[]>('/api/v1/sets');
      return response.data;
    },
  });
}

export function useSetCopiesList() {
  return useQuery<LEGOSetCopy[]>({
    queryKey: ['sets', 'copies'],
    queryFn: async () => {
      const response = await api.get<LEGOSetCopy[]>('/api/v1/sets/copies');
      return response.data;
    },
  });
}

export function useSetCopies(setNumber: string) {
  return useQuery<LEGOSetCopy[]>({
    queryKey: ['sets', setNumber, 'copies'],
    queryFn: async () => {
      const response = await api.get<LEGOSetCopy[]>(`/api/v1/sets/${setNumber}/copies`);
      return response.data;
    },
    enabled: !!setNumber,
  });
}

export function useSet(setNumber: string) {
  return useQuery<LEGOSet>({
    queryKey: ['sets', setNumber],
    queryFn: async () => {
      const response = await api.get<LEGOSet>(`/api/v1/sets/${setNumber}`);
      return response.data;
    },
    enabled: !!setNumber,
  });
}

export interface SetPart {
  design_id: string;
  name: string;
  color_id: number;
  color_name: string;
  hex: string | null;
  quantity: number;
  part_url: string | null;
  part_img_url: string | null;
}

export function useSetParts(setNumber: string) {
  return useQuery<SetPart[]>({
    queryKey: ['sets', setNumber, 'parts'],
    queryFn: async () => {
      const response = await api.get<SetPart[]>(`/api/v1/sets/${setNumber}/parts`);
      return response.data;
    },
    enabled: !!setNumber,
  });
}

export function useUpdateSetStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ setNumber, status }: { setNumber: string; status: string }) => {
      const response = await api.patch(`/api/v1/sets/${setNumber}/status`, { status });
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate queries to refetch updated data
      queryClient.invalidateQueries({ queryKey: ['sets', variables.setNumber] });
      queryClient.invalidateQueries({ queryKey: ['sets'] });
    },
  });
}

export function useUpdateSetCopyStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ setId, status }: { setId: number; status: string }) => {
      const response = await api.patch(`/api/v1/sets/copies/${setId}/status`, { status });
      return response.data;
    },
    onSuccess: async () => {
      // Broad invalidation is fine here — status changes can affect multiple pages.
      await queryClient.invalidateQueries({ queryKey: ['sets', 'copies'] });
      await queryClient.invalidateQueries({ queryKey: ['sets'] });
    },
  });
}

export interface PartLocation {
  drawer_id: number | null;
  drawer_name: string | null;
  container_id: number | null;
  container_name: string | null;
  quantity: number;
}

export interface SetPartWithLocations {
  design_id: string;
  name: string;
  color_id: number;
  color_name: string;
  hex: string | null;
  required_quantity: number;
  available_quantity: number;
  locations: PartLocation[];
  part_url: string | null;
  part_img_url: string | null;
}

export function useSetPartsWithLocations(setNumber: string) {
  return useQuery<SetPartWithLocations[]>({
    queryKey: ['sets', setNumber, 'parts-locations'],
    queryFn: async () => {
      const response = await api.get<SetPartWithLocations[]>(
        `/api/v1/sets/${setNumber}/parts-locations`
      );
      return response.data;
    },
    enabled: !!setNumber && !APP_SAFE_MODE,
  });
}

