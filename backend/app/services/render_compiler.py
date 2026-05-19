from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import (
    AssetKind,
    AssetRecord,
    CompiledBackgroundClip,
    CompiledOverlayClip,
    CompiledTextClip,
    CompiledTextStyle,
    ProjectSettings,
    SceneNode,
    TextBlock,
    TimelineScene,
)


class RenderCompilerError(Exception):
    """Raised when a scene cannot be compiled into a renderable timeline."""


@dataclass(slots=True)
class PixelBox:
    x_px: int
    y_px: int
    width_px: int
    height_px: int


class RenderCompiler:
    def __init__(self, settings: ProjectSettings) -> None:
        self.settings = settings

    def compile(self, node: SceneNode, asset_index: dict[str, AssetRecord]) -> TimelineScene:
        background_asset = self._require_asset(
            asset_id=node.background.asset.asset_id,
            expected_kinds={AssetKind.VIDEO, AssetKind.IMAGE},
            asset_index=asset_index,
        )

        overlay_clips = [
            self._compile_overlay(overlay, asset_index)
            for overlay in sorted(node.overlays, key=lambda item: (item.z_index, item.start_ms))
        ]
        text_clips = [
            self._compile_text(text)
            for text in sorted(node.texts, key=lambda item: (item.z_index, item.start_ms))
        ]

        subtitle_path = None
        if node.subtitles.enabled and node.subtitles.cues:
            subtitle_path = f"subtitles/{node.id}.ass"

        return TimelineScene(
            scene_id=node.id,
            width=self.settings.width,
            height=self.settings.height,
            fps=self.settings.fps,
            duration_ms=node.duration_ms,
            background_clip=CompiledBackgroundClip(
                absolute_path=background_asset.absolute_path,
                asset_kind=background_asset.kind,
                trim_in_ms=node.background.trim_in_ms,
                trim_out_ms=node.background.trim_out_ms,
                loop_mode=node.background.loop_mode,
            ),
            overlay_clips=overlay_clips,
            text_clips=text_clips,
            zoom=node.zoom,
            subtitle_ass_path=subtitle_path,
            subtitle_cues=node.subtitles.cues,
        )

    def _compile_overlay(
        self,
        overlay,
        asset_index: dict[str, AssetRecord],
    ) -> CompiledOverlayClip:
        asset = self._require_asset(
            asset_id=overlay.asset.asset_id,
            expected_kinds={AssetKind.IMAGE, AssetKind.VIDEO},
            asset_index=asset_index,
        )
        box = self._pct_box_to_px(
            x_pct=overlay.x_pct,
            y_pct=overlay.y_pct,
            width_pct=overlay.width_pct,
            height_pct=overlay.height_pct,
        )
        return CompiledOverlayClip(
            id=overlay.id,
            absolute_path=asset.absolute_path,
            asset_kind=asset.kind,
            start_ms=overlay.start_ms,
            end_ms=overlay.end_ms,
            x_px=box.x_px,
            y_px=box.y_px,
            width_px=box.width_px,
            height_px=box.height_px,
            opacity=overlay.opacity,
            enter_anim=overlay.enter_anim,
            exit_anim=overlay.exit_anim,
            z_index=overlay.z_index,
        )

    def _compile_text(self, text: TextBlock) -> CompiledTextClip:
        x_px, y_px = self._resolve_text_anchor(text)
        return CompiledTextClip(
            id=text.id,
            content=text.content,
            start_ms=text.start_ms,
            end_ms=text.end_ms,
            x_px=x_px,
            y_px=y_px,
            style=CompiledTextStyle(
                font_file=text.font_family,
                font_size_px=text.font_size_px,
                color_rgba=text.color_rgba,
                stroke_rgba=text.stroke_rgba,
                stroke_width_px=text.stroke_width_px,
                bg_rgba=text.bg_rgba,
                padding_px=text.padding_px,
            ),
            anim=text.anim,
            z_index=text.z_index,
        )

    def _resolve_text_anchor(self, text: TextBlock) -> tuple[int, int]:
        width = self.settings.width
        height = self.settings.height

        if text.anchor == "top_left":
            return 64 + text.x_offset_px, 64 + text.y_offset_px
        if text.anchor == "top_center":
            return width // 2 + text.x_offset_px, 96 + text.y_offset_px
        if text.anchor == "center":
            return width // 2 + text.x_offset_px, height // 2 + text.y_offset_px
        return width // 2 + text.x_offset_px, height - 120 + text.y_offset_px

    def _pct_box_to_px(
        self,
        *,
        x_pct: float,
        y_pct: float,
        width_pct: float,
        height_pct: float,
    ) -> PixelBox:
        return PixelBox(
            x_px=round(self.settings.width * x_pct),
            y_px=round(self.settings.height * y_pct),
            width_px=max(1, round(self.settings.width * width_pct)),
            height_px=max(1, round(self.settings.height * height_pct)),
        )

    def _require_asset(
        self,
        *,
        asset_id: str,
        expected_kinds: set[AssetKind],
        asset_index: dict[str, AssetRecord],
    ) -> AssetRecord:
        asset = asset_index.get(asset_id)
        if asset is None:
            raise RenderCompilerError(f"asset not found: {asset_id}")
        if asset.kind not in expected_kinds:
            expected = ", ".join(sorted(kind.value for kind in expected_kinds))
            raise RenderCompilerError(
                f"asset {asset_id} has kind {asset.kind.value}, expected one of {expected}"
            )
        return asset
