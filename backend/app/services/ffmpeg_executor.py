from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from app.domain.models import RenderExecutionDetails, RenderPlan
from app.services.ffmpeg_command_builder import FfmpegCommandBuilder
from app.services.subtitle_ass_builder import SubtitleAssBuilder


class FfmpegExecutionError(Exception):
    """Raised when FFmpeg execution fails or produces invalid outputs."""


class FfmpegExecutor:
    def __init__(self, *, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def execute(
        self,
        plan: RenderPlan,
        *,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> RenderExecutionDetails:
        self._ensure_output_dirs(plan)
        self._write_subtitles_if_needed(plan)

        total_duration_ms = plan.timeline_scene.duration_ms
        scene_command = FfmpegCommandBuilder(self.ffmpeg_path).build(plan)
        # Insertar -progress pipe:1 después del binary para output estructurado
        progress_command = scene_command[:1] + ["-progress", "pipe:1"] + scene_command[1:]

        scene_process = subprocess.Popen(
            progress_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Leer progress pipe línea por línea
        if scene_process.stdout is not None:
            self._read_progress(scene_process.stdout, total_duration_ms, progress_callback)

        _, stderr = scene_process.communicate()
        if scene_process.returncode != 0:
            raise FfmpegExecutionError(
                "ffmpeg scene render failed with exit code "
                f"{scene_process.returncode}: {stderr.strip()}"
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

    # ── progress parsing ──────────────────────────────────────────────────

    _PROGRESS_RE = re.compile(r"^(\w+)=(.+)$")

    def _read_progress(
        self,
        stdout,
        total_duration_ms: int,
        callback: Callable[[dict], None] | None,
    ) -> None:
        """Lee el output de `-progress pipe:1` y emite eventos de progreso.

        FFmpeg emite bloques key=value separados por líneas en blanco.
        Cada bloque termina con `progress=continue` o `progress=end`.
        """
        if callback is None:
            # Consumir stdout sin procesar para evitar bloqueo de pipe
            stdout.read()
            return

        current: dict[str, str] = {}
        for line in stdout:
            line = line.strip()
            if not line:
                continue

            match = self._PROGRESS_RE.match(line)
            if match:
                key, value = match.group(1), match.group(2)
                current[key] = value

                # Cada bloque termina con `progress=continue` o `progress=end`
                if key == "progress":
                    self._emit_progress(current, total_duration_ms, callback)
                    current = {}

    def _emit_progress(
        self,
        data: dict[str, str],
        total_duration_ms: int,
        callback: Callable[[dict], None],
    ) -> None:
        """Parsea un bloque de progreso y llama al callback.

        Nota: FFmpeg reporta `out_time_ms` en microsegundos (a pesar del nombre).
        """
        # out_time_ms de FFmpeg está en microsegundos
        out_time_us = int(data.get("out_time_ms", 0))
        out_time_ms = out_time_us // 1000
        frame = int(data.get("frame", 0))
        fps = float(data.get("fps", 0.0))
        speed_raw = data.get("speed", "0x")
        speed = float(speed_raw.replace("x", "")) if speed_raw else 0.0

        percent = 0.0
        if total_duration_ms > 0:
            percent = min(out_time_ms / total_duration_ms * 100, 100.0)

        callback({
            "frame": frame,
            "fps": round(fps, 2),
            "time_ms": out_time_ms,
            "speed": round(speed, 2),
            "percent": round(percent, 1),
        })
