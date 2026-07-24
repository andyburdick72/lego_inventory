import { useQuery } from '@tanstack/react-query';
import { api } from '../api';

export interface Color {
  id: number;
  name: string;
  hex: string | null;
}

export function useColors(query?: string) {
  return useQuery<Color[]>({
    queryKey: ['colors', query || ''],
    queryFn: async () => {
      const res = await api.get<Color[]>('/api/v1/colors', {
        params: query ? { q: query, limit: 5000 } : { limit: 5000 },
      });
      return res.data;
    },
  });
}


