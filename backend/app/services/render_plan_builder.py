from __future__ import annotations

from pathlib import Path

from app.domain.models import (
    AssetKind,
    RenderPlan,
    RenderPlanFilterStage,
    RenderPlanInput,
    RenderPlanOutputs,
    TimelineScene,
)


class RenderPlanBuilder:
    def build(
        self,
        *,
        timeline_scene: TimelineScene,
        fingerprint: str,
        cache_root: str,
    ) -> RenderPlan:
        scene_root = Path(cache_root) / "scenes" / timeline_scene.scene_id / fingerprint
        subtitle_path = None
        if timeline_scene.subtitle_ass_path:
            subtitle_path = str(scene_root / "subtitles.ass")
            timeline_scene = timeline_scene.model_copy(update={"subtitle_ass_path": subtitle_path})

        inputs = [
            RenderPlanInput(
                input_id="background",
                absolute_path=timeline_scene.background_clip.absolute_path,
                asset_kind=timeline_scene.background_clip.asset_kind,
                role="background",
                start_ms=timeline_scene.background_clip.trim_in_ms,
                end_ms=timeline_scene.background_clip.trim_out_ms,
                loop_indefinitely=timeline_scene.background_clip.asset_kind == AssetKind.IMAGE,
            )
        ]
        for overlay in timeline_scene.overlay_clips:
            inputs.append(
                RenderPlanInput(
                    input_id=overlay.id,
                    absolute_path=overlay.absolute_path,
                    asset_kind=overlay.asset_kind,
                    role="overlay",
                    start_ms=overlay.start_ms,
                    end_ms=overlay.end_ms,
                    loop_indefinitely=overlay.asset_kind == AssetKind.IMAGE,
                )
            )

        filter_stages = [self._normalize_background_stage()]
        if timeline_scene.zoom.mode != "none":
            filter_stages.append(
                RenderPlanFilterStage(
                    name="apply_zoom",
                    description=f"Apply {timeline_scene.zoom.mode} on background",
                )
            )
        if timeline_scene.overlay_clips:
            filter_stages.append(
                RenderPlanFilterStage(
                    name="composite_overlays",
                    description=f"Composite {len(timeline_scene.overlay_clips)} overlay clip(s)",
                )
            )
        if timeline_scene.text_clips:
            filter_stages.append(
                RenderPlanFilterStage(
                    name="draw_texts",
                    description=f"Draw {len(timeline_scene.text_clips)} text block(s)",
                )
            )
        if subtitle_path:
            filter_stages.append(
                RenderPlanFilterStage(
                    name="burn_subtitles",
                    description="Burn ASS subtitles into the output scene",
                )
            )

        return RenderPlan(
            plan_id=f"{timeline_scene.scene_id}:{fingerprint}",
            scene_id=timeline_scene.scene_id,
            timeline_scene=timeline_scene,
            inputs=inputs,
            filter_stages=filter_stages,
            outputs=RenderPlanOutputs(
                scene_output_path=str(scene_root / "scene.mp4"),
                preview_output_path=str(scene_root / "preview.png"),
                manifest_output_path=str(scene_root / "render_manifest.json"),
                subtitle_ass_path=subtitle_path,
            ),
        )

    def _normalize_background_stage(self) -> RenderPlanFilterStage:
        return RenderPlanFilterStage(
            name="normalize_background",
            description="Scale, crop and normalize the background clip to project resolution",
        )
