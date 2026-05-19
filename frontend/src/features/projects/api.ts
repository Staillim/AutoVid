import { api } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';

export interface RuntimeHealthReport {
  timestamp: string;
  ready_for_render: boolean;
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  font_available: boolean;
}

export function getHealth() {
  return api.get<RuntimeHealthReport>('/api/health');
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30000, // Refetch every 30s
  });
}
