import { api } from '@/lib/api';
import { useMutation } from '@tanstack/react-query';
import type { AssetRecord } from '@/features/assets/api';

export interface ProjectSettings {
  width: number;
  height: number;
  fps: number;
  video_codec: 'h264';
  audio_codec: 'aac';
  master_audio_asset_id?: string;
  subtitle_language: string;
  export_preset: 'youtube_1080p';
}

export interface RenderNodeRequest {
  settings: ProjectSettings;
  node: {
    id: string;
    order: number;
    title: string;
    enabled: boolean;
    duration_ms: number;
    narrative: any;
    background?: any;
    overlays: any[];
    texts: any[];
    zoom: any;
    subtitles: any;
    tags: string[];
    ui: any;
  };
  assets: AssetRecord[];
}

export interface RenderJobRecord {
  job_id: string;
  project_id: string;
  scene_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  error_message?: string;
}

export function renderNode(payload: RenderNodeRequest) {
  return api.post<RenderJobRecord>('/api/jobs/render-node', payload);
}

// Hook to trigger rendering
export function useRenderNode() {
  return useMutation({
    mutationFn: renderNode,
  });
}
