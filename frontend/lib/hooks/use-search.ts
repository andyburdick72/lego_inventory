import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { APP_SAFE_MODE } from '../safe-mode';

export interface SearchPart {
  design_id: string;
  name: string;
  part_url: string | null;
  part_img_url: string | null;
  part_category_id: number | null;
  part_category_name: string | null;
}

export interface SearchSet {
  set_number: string;
  name: string;
  year: number | null;
  theme_id: number | null;
  theme_name: string | null;
  status: string | null;
  image_url: string | null;
  rebrickable_url: string | null;
}

export interface SearchDrawer {
  id: number;
  name: string;
  description: string | null;
}

export interface SearchContainer {
  id: number;
  name: string;
  description: string | null;
  drawer_id: number;
  drawer_name: string | null;
}

export interface SearchCategory {
  id: number;
  name: string;
}

export interface SearchResults {
  parts: SearchPart[];
  sets: SearchSet[];
  drawers: SearchDrawer[];
  containers: SearchContainer[];
  categories: SearchCategory[];
}

export function useSearch(query: string, enabled: boolean = true) {
  return useQuery<SearchResults>({
    queryKey: ['search', query],
    queryFn: async () => {
      const response = await api.get<SearchResults>('/api/v1/search', {
        params: { q: query, limit: 10 },
      });
      return response.data;
    },
    enabled: !APP_SAFE_MODE && enabled && query.length >= 2,
    staleTime: 30000, // Cache for 30 seconds
  });
}
