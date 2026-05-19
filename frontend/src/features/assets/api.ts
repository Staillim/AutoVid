import { api } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export type AssetKind = 'video' | 'image' | 'audio';

export interface AssetRecord {
  asset_id: string;
  kind: AssetKind;
  absolute_path: string;
  content_sha256: string;
  size_bytes: number;
  duration_ms?: number;
  width?: number;
  height?: number;
  fps?: number;
}

export function getAssets(kind?: AssetKind) {
  return api.get<AssetRecord[]>('/api/assets', { params: kind ? { kind } : {} });
}

export function importAsset(absolute_path: string) {
  return api.post<AssetRecord>('/api/assets/import', { absolute_path });
}

export function deleteAsset(asset_id: string) {
  return api.delete(`/api/assets/${asset_id}`);
}

// Hooks

export function useAssets(kind?: AssetKind) {
  return useQuery({
    queryKey: ['assets', kind],
    queryFn: () => getAssets(kind),
  });
}

export function useImportAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importAsset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

export function useDeleteAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteAsset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}
