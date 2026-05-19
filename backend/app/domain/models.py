from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1.0.0"


class AssetKind(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"


class NarrativeRole(str, Enum):
    HOOK = "hook"
    SETUP = "setup"
    CONTEXT = "context"
    ARGUMENT = "argument"
    EVIDENCE = "evidence"
    TRANSITION = "transition"
    PAYOFF = "payoff"
    CTA = "cta"


class AssetRef(BaseModel):
    asset_id: str
    kind: AssetKind


class AssetRecord(BaseModel):
    asset_id: str
    kind: AssetKind
    absolute_path: str
    content_sha256: str
    size_bytes: int = Field(ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    fps: float | None = Field(default=None, gt=0)


class Overlay(BaseModel):
    id: str
    asset: AssetRef
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)
    width_pct: float = Field(gt=0.0, le=1.0)
    height_pct: float = Field(gt=0.0, le=1.0)
    opacity: float = Field(ge=0.0, le=1.0)
    enter_anim: Literal["none", "fade", "slide_up", "pop"] = "none"
    exit_anim: Literal["none", "fade"] = "none"
    z_index: int = 0

    @model_validator(mode="after")
    def validate_range(self) -> "Overlay":
        if self.end_ms <= self.start_ms:
            raise ValueError("overlay end_ms must be greater than start_ms")
        return self


class TextBlock(BaseModel):
    id: str
    content: str = Field(min_length=1, max_length=500)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    anchor: Literal["top_left", "top_center", "center", "bottom_center"]
    x_offset_px: int = 0
    y_offset_px: int = 0
    font_family: str = Field(min_length=1)
    font_size_px: int = Field(ge=8, le=256)
    font_weight: Literal[400, 500, 600, 700, 800] = 700
    color_rgba: str = Field(min_length=4)
    stroke_rgba: str | None = None
    stroke_width_px: int = Field(default=0, ge=0, le=16)
    bg_rgba: str | None = None
    padding_px: int = Field(default=0, ge=0, le=64)
    anim: Literal["none", "fade", "pop"] = "none"
    z_index: int = 0

    @model_validator(mode="after")
    def validate_range(self) -> "TextBlock":
        if self.end_ms <= self.start_ms:
            raise ValueError("text end_ms must be greater than start_ms")
        return self


class ZoomMotion(BaseModel):
    mode: Literal["none", "zoom_in", "zoom_out"] = "none"
    start_ms: int = Field(default=0, ge=0)
    end_ms: int = Field(default=0, ge=0)
    start_scale: float = Field(default=1.0, gt=0)
    end_scale: float = Field(default=1.0, gt=0)
    anchor: Literal["center"] = "center"

    @model_validator(mode="after")
    def validate_zoom(self) -> "ZoomMotion":
        if self.mode != "none" and self.end_ms <= self.start_ms:
            raise ValueError("zoom end_ms must be greater than start_ms when zoom is enabled")
        return self


class SubtitleCue(BaseModel):
    id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> "SubtitleCue":
        if self.end_ms <= self.start_ms:
            raise ValueError("subtitle cue end_ms must be greater than start_ms")
        return self


class SubtitleTrack(BaseModel):
    enabled: bool = False
    mode: Literal["segment"] = "segment"
    cues: list[SubtitleCue] = Field(default_factory=list)
    style_preset: Literal["default_youtube"] = "default_youtube"


class NarrativeBlock(BaseModel):
    source_start_ms: int | None = Field(default=None, ge=0)
    source_end_ms: int | None = Field(default=None, ge=0)
    summary: str = Field(min_length=1)
    transcript_excerpt: str = Field(default="")
    entities: list[str] = Field(default_factory=list)
    narrative_role: NarrativeRole
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_source_range(self) -> "NarrativeBlock":
        if (
            self.source_start_ms is not None
            and self.source_end_ms is not None
            and self.source_end_ms <= self.source_start_ms
        ):
            raise ValueError("narrative source_end_ms must be greater than source_start_ms")
        return self


class BackgroundConfig(BaseModel):
    asset: AssetRef
    trim_in_ms: int = Field(ge=0)
    trim_out_ms: int = Field(gt=0)
    loop_mode: Literal["loop", "freeze_last_frame", "cut"] = "cut"
    fit_mode: Literal["cover"] = "cover"
    blur_background: Literal[False] = False

    @model_validator(mode="after")
    def validate_range(self) -> "BackgroundConfig":
        if self.trim_out_ms <= self.trim_in_ms:
            raise ValueError("background trim_out_ms must be greater than trim_in_ms")
        return self


class SceneNodeUI(BaseModel):
    canvas_x: float = 0.0
    canvas_y: float = 0.0
    color_hint: str | None = None


class SceneNode(BaseModel):
    id: str
    order: int = Field(ge=0)
    title: str = Field(min_length=1)
    enabled: bool = True
    duration_ms: int = Field(gt=0)
    narrative: NarrativeBlock
    background: BackgroundConfig
    overlays: list[Overlay] = Field(default_factory=list)
    texts: list[TextBlock] = Field(default_factory=list)
    zoom: ZoomMotion = Field(default_factory=ZoomMotion)
    subtitles: SubtitleTrack = Field(default_factory=SubtitleTrack)
    tags: list[str] = Field(default_factory=list)
    ui: SceneNodeUI = Field(default_factory=SceneNodeUI)

    @model_validator(mode="after")
    def validate_timing_bounds(self) -> "SceneNode":
        if self.background.trim_out_ms - self.background.trim_in_ms <= 0:
            raise ValueError("background duration must be positive")
        for overlay in self.overlays:
            if overlay.end_ms > self.duration_ms:
                raise ValueError(f"overlay {overlay.id} exceeds scene duration")
        for text in self.texts:
            if text.end_ms > self.duration_ms:
                raise ValueError(f"text {text.id} exceeds scene duration")
        for cue in self.subtitles.cues:
            if cue.end_ms > self.duration_ms:
                raise ValueError(f"subtitle cue {cue.id} exceeds scene duration")
        if self.zoom.mode != "none" and self.zoom.end_ms > self.duration_ms:
            raise ValueError("zoom exceeds scene duration")
        return self


class ProjectSettings(BaseModel):
    width: int = Field(default=1920, ge=16)
    height: int = Field(default=1080, ge=16)
    fps: int = Field(default=30, ge=1, le=120)
    video_codec: Literal["h264"] = "h264"
    audio_codec: Literal["aac"] = "aac"
    master_audio_asset_id: str | None = None
    subtitle_language: str = "es"
    export_preset: Literal["youtube_1080p"] = "youtube_1080p"


class LibraryBinding(BaseModel):
    library_id: str


class AnalysisMetadata(BaseModel):
    source_type: Literal["script", "audio", "manual"] = "manual"
    source_asset_id: str | None = None
    source_text_sha256: str | None = None
    last_analysis_id: str | None = None
    last_analysis_provider: str | None = None
    last_analysis_model: str | None = None


class ProjectModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    project_id: str
    created_at: str
    updated_at: str
    name: str
    settings: ProjectSettings
    library_binding: LibraryBinding
    analysis: AnalysisMetadata = Field(default_factory=AnalysisMetadata)
    nodes: list[SceneNode] = Field(default_factory=list)
    scene_order: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if not value:
            raise ValueError("schema_version is required")
        return value

    @model_validator(mode="after")
    def validate_scene_order(self) -> "ProjectModel":
        node_ids = {node.id for node in self.nodes}
        order_ids = set(self.scene_order)
        if order_ids and order_ids != node_ids:
            raise ValueError("scene_order must contain the same ids as nodes")
        if not self.scene_order and self.nodes:
            self.scene_order = [node.id for node in sorted(self.nodes, key=lambda item: item.order)]
        return self

    def get_scene(self, scene_id: str) -> SceneNode | None:
        for node in self.nodes:
            if node.id == scene_id:
                return node
        return None


class CompiledBackgroundClip(BaseModel):
    absolute_path: str
    asset_kind: AssetKind
    trim_in_ms: int
    trim_out_ms: int
    loop_mode: Literal["loop", "freeze_last_frame", "cut"]


class CompiledOverlayClip(BaseModel):
    id: str
    absolute_path: str
    asset_kind: AssetKind
    start_ms: int
    end_ms: int
    x_px: int
    y_px: int
    width_px: int
    height_px: int
    opacity: float
    enter_anim: Literal["none", "fade", "slide_up", "pop"]
    exit_anim: Literal["none", "fade"]
    z_index: int


class CompiledTextStyle(BaseModel):
    font_file: str
    font_size_px: int
    color_rgba: str
    stroke_rgba: str | None
    stroke_width_px: int
    bg_rgba: str | None
    padding_px: int


class CompiledTextClip(BaseModel):
    id: str
    content: str
    start_ms: int
    end_ms: int
    x_px: int
    y_px: int
    style: CompiledTextStyle
    anim: Literal["none", "fade", "pop"]
    z_index: int


class TimelineScene(BaseModel):
    scene_id: str
    width: int
    height: int
    fps: int
    duration_ms: int
    background_clip: CompiledBackgroundClip
    overlay_clips: list[CompiledOverlayClip]
    text_clips: list[CompiledTextClip]
    zoom: ZoomMotion
    subtitle_ass_path: str | None = None
    subtitle_cues: list[SubtitleCue] = Field(default_factory=list)


class RenderPlanInput(BaseModel):
    input_id: str
    absolute_path: str
    asset_kind: AssetKind
    role: Literal["background", "overlay"]
    start_ms: int | None = None
    end_ms: int | None = None
    loop_indefinitely: bool = False


class RenderPlanFilterStage(BaseModel):
    name: Literal[
        "normalize_background",
        "apply_zoom",
        "composite_overlays",
        "draw_texts",
        "burn_subtitles",
    ]
    description: str


class RenderPlanOutputs(BaseModel):
    scene_output_path: str
    preview_output_path: str
    manifest_output_path: str
    subtitle_ass_path: str | None = None


class RenderPlan(BaseModel):
    plan_id: str
    scene_id: str
    timeline_scene: TimelineScene
    inputs: list[RenderPlanInput]
    filter_stages: list[RenderPlanFilterStage]
    outputs: RenderPlanOutputs


class RenderSceneRequest(BaseModel):
    project: ProjectModel
    scene_id: str
    assets: list[AssetRecord]
    cache_root: str | None = None
    ffmpeg_path: str | None = None


class RenderNodeRequest(BaseModel):
    settings: ProjectSettings
    node: SceneNode
    assets: list[AssetRecord]
    cache_root: str | None = None
    ffmpeg_path: str | None = None


class RenderJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RenderJobResult(BaseModel):
    timeline_scene: TimelineScene
    fingerprint: str
    render_plan: RenderPlan
    ffmpeg_command: list[str]
    preview_command: list[str]
    execution: RenderExecutionDetails | None = None


class RenderExecutionDetails(BaseModel):
    scene_output_path: str
    preview_output_path: str
    subtitles_output_path: str | None = None
    ffmpeg_executed: bool = False
    preview_generated: bool = False
    exit_code: int | None = None
    preview_exit_code: int | None = None


class RenderSceneManifest(BaseModel):
    manifest_version: str = "1.0.0"
    scene_id: str
    fingerprint: str
    generated_at: str
    render_plan: RenderPlan
    ffmpeg_command: list[str]
    preview_command: list[str]
    execution: RenderExecutionDetails | None = None


class RenderJobRecord(BaseModel):
    job_id: str
    project_id: str
    scene_id: str
    status: RenderJobStatus
    created_at: str
    updated_at: str
    error_message: str | None = None
    result: RenderJobResult | None = None


class RuntimeDirectoryCheck(BaseModel):
    label: str
    path: str
    exists: bool
    writable: bool


class RuntimeBinaryCheck(BaseModel):
    label: str
    configured_path: str
    resolved_path: str | None = None
    available: bool
    executable: bool
    version: str | None = None
    error_message: str | None = None


class RuntimeHealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    ready_for_render: bool
    runtime_root: str
    cache_root: RuntimeDirectoryCheck
    logs_root: RuntimeDirectoryCheck
    ffmpeg: RuntimeBinaryCheck
    ffprobe: RuntimeBinaryCheck
    issues: list[str] = Field(default_factory=list)
