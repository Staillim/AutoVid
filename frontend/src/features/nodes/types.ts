import type { Node } from 'reactflow';

export type NodeType = 'scene' | 'audio' | 'effect';

export interface BaseNodeData {
  title: string;
}

export type AssetKind = 'video' | 'image' | 'audio';

export interface AssetRef {
  asset_id: string;
  kind: AssetKind;
}

export interface BackgroundConfig {
  asset: AssetRef;
  trim_in_ms: int;
  trim_out_ms: int;
  loop_mode: 'loop' | 'freeze_last_frame' | 'cut';
  fit_mode: 'cover';
  blur_background: false;
}

export interface Overlay {
  id: string;
  asset: AssetRef;
  start_ms: int;
  end_ms: int;
  x_pct: float;
  y_pct: float;
  width_pct: float;
  height_pct: float;
  opacity: float;
  enter_anim: 'none' | 'fade' | 'slide_up' | 'pop';
  exit_anim: 'none' | 'fade';
  z_index: int;
}

export interface TextBlock {
  id: string;
  content: string;
  start_ms: int;
  end_ms: int;
  anchor: 'top_left' | 'top_center' | 'center' | 'bottom_center';
  x_offset_px: int;
  y_offset_px: int;
  font_family: string;
  font_size_px: int;
  font_weight: 400 | 500 | 600 | 700 | 800;
  color_rgba: string;
  stroke_rgba: string | null;
  stroke_width_px: int;
  bg_rgba: string | null;
  padding_px: int;
  anim: 'none' | 'fade' | 'pop';
  z_index: int;
}

export interface ZoomMotion {
  mode: 'none' | 'zoom_in' | 'zoom_out';
  start_ms: int;
  end_ms: int;
  start_scale: float;
  end_scale: float;
  anchor: 'center';
}

export interface SubtitleCue {
  id: string;
  start_ms: int;
  end_ms: int;
  text: string;
}

export interface SubtitleTrack {
  enabled: boolean;
  mode: 'segment';
  cues: SubtitleCue[];
  style_preset: 'default_youtube';
}

export interface NarrativeBlock {
  source_start_ms: int | null;
  source_end_ms: int | null;
  summary: string;
  transcript_excerpt: string;
  entities: string[];
  narrative_role: 'hook' | 'setup' | 'context' | 'argument' | 'evidence' | 'transition' | 'payoff' | 'cta';
  confidence: float;
}

export interface SceneNodeUI {
  canvas_x: float;
  canvas_y: float;
  color_hint: string | null;
}

export interface SceneNodeData extends BaseNodeData {
  enabled: boolean;
  duration_ms: number;
  narrative: NarrativeBlock;
  background?: BackgroundConfig;
  overlays: Overlay[];
  texts: TextBlock[];
  zoom: ZoomMotion;
  subtitles: SubtitleTrack;
  tags: string[];
  ui: SceneNodeUI;
}

export type AppNode = Node<SceneNodeData, NodeType>;

// Typescript doesn't have int/float keywords natively, creating type aliases for semantic parity with Python
type int = number;
type float = number;
