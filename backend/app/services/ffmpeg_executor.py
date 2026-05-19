from __future__ import annotations

import subprocess
from pathlib import Path

from app.domain.models import RenderExecutionDetails, RenderPlan
from app.services.ffmpeg_command_builder import FfmpegCommandBuilder
from app.services.subtitle_ass_builder import SubtitleAssBuilder


class FfmpegExecutionError(Exception):
    """Raised when FFmpeg execution fails or produces invalid outputs."""


class FfmpegExecutor:
    def __init__(self, *, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def execute(self, plan: RenderPlan) -> RenderExecutionDetails:
        self._ensure_output_dirs(plan)
        self._write_subtitles_if_needed(plan)

        scene_command = FfmpegCommandBuilder(self.ffmpeg_path).build(plan)
        scene_process = subprocess.run(scene_command, capture_output=True, text=True, check=False)
        if scene_process.returncode != 0:
            raise FfmpegExecutionError(
                "ffmpeg scene render failed with exit code "
                f"{scene_process.returncode}: {scene_process.stderr.strip()}"
            )

        scene_output = Path(plan.outputs.scene_output_path)
        self._ensure_non_empty_file(scene_output, "scene output")

        preview_command = self._build_preview_command(plan)
        preview_process = subprocess.run(preview_command, capture_output=True, text=True, check=False)
        if preview_process.returncode != 0:
            raise FfmpegExecutionError(
                "ffmpeg preview generation failed with exit code "
                f"{preview_process.returncode}: {preview_process.stderr.strip()}"
            )

        preview_output = Path(plan.outputs.preview_output_path)
        self._ensure_non_empty_file(preview_output, "preview output")

        return RenderExecutionDetails(
            scene_output_path=str(scene_output),
            preview_output_path=str(preview_output),
            subtitles_output_path=plan.outputs.subtitle_ass_path,
            ffmpeg_executed=True,
            preview_generated=True,
            exit_code=scene_process.returncode,
            preview_exit_code=preview_process.returncode,
        )

    def build_preview_command(self, plan: RenderPlan) -> list[str]:
        return self._build_preview_command(plan)

    def _build_preview_command(self, plan: RenderPlan) -> list[str]:
        midpoint_seconds = max(plan.timeline_scene.duration_ms / 2000, 0.001)
        return [
            self.ffmpeg_path,
            "-y",
            "-hide_banner",
            "-ss",
            f"{midpoint_seconds:.3f}",
            "-i",
            plan.outputs.scene_output_path,
            "-frames:v",
            "1",
            plan.outputs.preview_output_path,
        ]

    def _ensure_output_dirs(self, plan: RenderPlan) -> None:
        Path(plan.outputs.scene_output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(plan.outputs.preview_output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(plan.outputs.manifest_output_path).parent.mkdir(parents=True, exist_ok=True)
        if plan.outputs.subtitle_ass_path:
            Path(plan.outputs.subtitle_ass_path).parent.mkdir(parents=True, exist_ok=True)

    def _write_subtitles_if_needed(self, plan: RenderPlan) -> None:
        subtitle_path = plan.outputs.subtitle_ass_path
        if not subtitle_path:
            return
        content = SubtitleAssBuilder().build(plan.timeline_scene)
        Path(subtitle_path).write_text(content, encoding="utf-8")

    def _ensure_non_empty_file(self, path: Path, label: str) -> None:
        if not path.exists():
            raise FfmpegExecutionError(f"{label} was not created at {path}")
        if path.stat().st_size <= 0:
            raise FfmpegExecutionError(f"{label} is empty at {path}")
