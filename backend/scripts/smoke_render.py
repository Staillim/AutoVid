from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.settings import AppSettings
from app.domain.models import (  # noqa: E402
    AnalysisMetadata,
    AssetKind,
    AssetRecord,
    AssetRef,
    BackgroundConfig,
    LibraryBinding,
    NarrativeBlock,
    NarrativeRole,
    Overlay,
    ProjectModel,
    ProjectSettings,
    RenderSceneRequest,
    SceneNode,
    SceneNodeUI,
    SubtitleCue,
    SubtitleTrack,
    TextBlock,
    ZoomMotion,
)
from app.services.render_pipeline import RenderPipeline  # noqa: E402
from app.services.runtime_diagnostics import RuntimeDiagnosticsService  # noqa: E402


def main() -> int:
    settings = AppSettings.from_env()
    report = RuntimeDiagnosticsService(settings).build_report()
    if not report.ready_for_render:
        print("Runtime no listo para render.")
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        return 1

    smoke_root = BACKEND_ROOT / ".smoke"
    assets_root = smoke_root / "assets"
    project_root = smoke_root / "project"
    assets_root.mkdir(parents=True, exist_ok=True)
    project_root.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = settings.resolve_ffmpeg_path()
    font_file = _resolve_font_file(settings)
    if font_file is None:
        print("No se encontro una fuente valida para drawtext.")
        return 1

    background_path = assets_root / "background.mp4"
    overlay_path = assets_root / "overlay.png"

    _generate_background_video(ffmpeg_path, background_path)
    _generate_overlay_image(ffmpeg_path, overlay_path)

    project, assets = _build_smoke_project(
        background_path=background_path,
        overlay_path=overlay_path,
        font_file=font_file,
    )

    request = RenderSceneRequest(
        project=project,
        scene_id=project.scene_order[0],
        assets=assets,
        cache_root=str(project_root / "cache"),
        ffmpeg_path=ffmpeg_path,
    )

    result = RenderPipeline(settings=settings).execute_scene_render(request)

    print("Smoke render completado.")
    print(f"Scene output: {result.execution.scene_output_path if result.execution else 'n/a'}")
    print(f"Preview output: {result.execution.preview_output_path if result.execution else 'n/a'}")
    print(f"Manifest: {result.render_plan.outputs.manifest_output_path}")
    return 0


def _build_smoke_project(
    *,
    background_path: Path,
    overlay_path: Path,
    font_file: str,
) -> tuple[ProjectModel, list[AssetRecord]]:
    background_asset = AssetRecord(
        asset_id="smoke-bg-001",
        kind=AssetKind.VIDEO,
        absolute_path=str(background_path),
        content_sha256=_sha256_file(background_path),
        size_bytes=background_path.stat().st_size,
        duration_ms=6000,
        width=1280,
        height=720,
        fps=30,
    )
    overlay_asset = AssetRecord(
        asset_id="smoke-overlay-001",
        kind=AssetKind.IMAGE,
        absolute_path=str(overlay_path),
        content_sha256=_sha256_file(overlay_path),
        size_bytes=overlay_path.stat().st_size,
        width=360,
        height=180,
    )

    scene = SceneNode(
        id="smoke-scene-001",
        order=0,
        title="Smoke Scene",
        enabled=True,
        duration_ms=6000,
        narrative=NarrativeBlock(
            source_start_ms=None,
            source_end_ms=None,
            summary="Smoke test scene",
            transcript_excerpt="Este render valida el pipeline base.",
            entities=["NodeAV"],
            narrative_role=NarrativeRole.HOOK,
            confidence=1.0,
        ),
        background=BackgroundConfig(
            asset=AssetRef(asset_id="smoke-bg-001", kind=AssetKind.VIDEO),
            trim_in_ms=0,
            trim_out_ms=6000,
            loop_mode="cut",
            fit_mode="cover",
            blur_background=False,
        ),
        overlays=[
            Overlay(
                id="smoke-overlay-layer-001",
                asset=AssetRef(asset_id="smoke-overlay-001", kind=AssetKind.IMAGE),
                start_ms=500,
                end_ms=3500,
                x_pct=0.07,
                y_pct=0.08,
                width_pct=0.28,
                height_pct=0.2,
                opacity=1.0,
                enter_anim="fade",
                exit_anim="fade",
                z_index=1,
            )
        ],
        texts=[
            TextBlock(
                id="smoke-text-001",
                content="NodeAV Smoke Render",
                start_ms=1000,
                end_ms=5000,
                anchor="center",
                x_offset_px=0,
                y_offset_px=0,
                font_family=font_file,
                font_size_px=56,
                font_weight=700,
                color_rgba="#FFFFFF",
                stroke_rgba="#000000",
                stroke_width_px=2,
                bg_rgba=None,
                padding_px=0,
                anim="pop",
                z_index=2,
            )
        ],
        zoom=ZoomMotion(
            mode="zoom_in",
            start_ms=0,
            end_ms=3000,
            start_scale=1.0,
            end_scale=1.1,
            anchor="center",
        ),
        subtitles=SubtitleTrack(
            enabled=True,
            cues=[
                SubtitleCue(
                    id="smoke-cue-001",
                    start_ms=0,
                    end_ms=2600,
                    text="Este render valida el pipeline base.",
                )
            ],
        ),
        tags=["smoke"],
        ui=SceneNodeUI(canvas_x=0, canvas_y=0, color_hint=None),
    )

    now = datetime.now(timezone.utc).isoformat()
    project = ProjectModel(
        project_id="smoke-project-001",
        created_at=now,
        updated_at=now,
        name="NodeAV Smoke Project",
        settings=ProjectSettings(width=1280, height=720, fps=30),
        library_binding=LibraryBinding(library_id="smoke-library"),
        analysis=AnalysisMetadata(source_type="manual"),
        nodes=[scene],
        scene_order=["smoke-scene-001"],
        notes="Proyecto generado por scripts/smoke_render.py",
    )
    return project, [background_asset, overlay_asset]


def _generate_background_video(ffmpeg_path: str, output_path: Path) -> None:
    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-t",
        "6",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    _run(command, "background video generation")


def _generate_overlay_image(ffmpeg_path: str, output_path: Path) -> None:
    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=yellow@0.85:s=360x180:d=1",
        "-frames:v",
        "1",
        str(output_path),
    ]
    _run(command, "overlay image generation")


def _resolve_font_file(settings: AppSettings) -> str | None:
    candidates: list[Path] = []
    if settings.font_root:
        font_root = Path(settings.font_root)
        candidates.extend(
            [
                font_root / "Inter-Bold.ttf",
                font_root / "Arial.ttf",
            ]
        )
    candidates.extend(
        [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/ARIAL.TTF"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], label: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code {completed.returncode}: {completed.stderr.strip()}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
