from pathlib import Path
from tempfile import TemporaryDirectory

from app.domain.models import (
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
from app.services.cache_fingerprint import build_scene_fingerprint
from app.services.ffmpeg_command_builder import FfmpegCommandBuilder
from app.services.ffmpeg_executor import FfmpegExecutor
from app.services.render_manifest_service import RenderManifestService
from app.services.render_pipeline import RenderPipeline
from app.services.render_compiler import RenderCompiler
from app.services.render_plan_builder import RenderPlanBuilder
from app.services.subtitle_ass_builder import SubtitleAssBuilder


def make_project() -> tuple[ProjectModel, list[AssetRecord]]:
    background_asset = AssetRecord(
        asset_id="asset-bg-001",
        kind=AssetKind.VIDEO,
        absolute_path="C:/media/background.mp4",
        content_sha256="hash-bg",
        size_bytes=1024,
        duration_ms=45000,
        width=1920,
        height=1080,
        fps=30,
    )
    overlay_asset = AssetRecord(
        asset_id="asset-overlay-001",
        kind=AssetKind.IMAGE,
        absolute_path="C:/media/logo.png",
        content_sha256="hash-overlay",
        size_bytes=128,
        width=800,
        height=600,
    )

    scene = SceneNode(
        id="scene-001",
        order=0,
        title="Hook scene",
        enabled=True,
        duration_ms=12000,
        narrative=NarrativeBlock(
            source_start_ms=0,
            source_end_ms=12000,
            summary="Presenta la idea principal",
            transcript_excerpt="Rockstar podria cambiar el mercado.",
            entities=["Rockstar", "GTA 6"],
            narrative_role=NarrativeRole.HOOK,
            confidence=0.95,
        ),
        background=BackgroundConfig(
            asset=AssetRef(asset_id="asset-bg-001", kind=AssetKind.VIDEO),
            trim_in_ms=0,
            trim_out_ms=12000,
            loop_mode="cut",
            fit_mode="cover",
            blur_background=False,
        ),
        overlays=[
            Overlay(
                id="overlay-001",
                asset=AssetRef(asset_id="asset-overlay-001", kind=AssetKind.IMAGE),
                start_ms=1000,
                end_ms=5000,
                x_pct=0.1,
                y_pct=0.1,
                width_pct=0.2,
                height_pct=0.2,
                opacity=1.0,
                enter_anim="fade",
                exit_anim="fade",
                z_index=1,
            )
        ],
        texts=[
            TextBlock(
                id="text-001",
                content="80 USD?",
                start_ms=2000,
                end_ms=6000,
                anchor="center",
                font_family="C:/fonts/Inter-Bold.ttf",
                font_size_px=72,
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
            end_ms=6000,
            start_scale=1.0,
            end_scale=1.15,
            anchor="center",
        ),
        subtitles=SubtitleTrack(
            enabled=True,
            cues=[
                SubtitleCue(
                    id="cue-001",
                    start_ms=0,
                    end_ms=3000,
                    text="Rockstar podria cambiar el mercado.",
                )
            ],
        ),
        tags=["hook"],
        ui=SceneNodeUI(canvas_x=0, canvas_y=0, color_hint=None),
    )

    project = ProjectModel(
        project_id="project-001",
        created_at="2026-05-19T15:00:00Z",
        updated_at="2026-05-19T15:10:00Z",
        name="Proyecto demo",
        settings=ProjectSettings(),
        library_binding=LibraryBinding(library_id="default-local-library"),
        analysis=AnalysisMetadata(source_type="script"),
        nodes=[scene],
        scene_order=["scene-001"],
        notes="",
    )
    return project, [background_asset, overlay_asset]


def test_render_compiler_builds_timeline_scene() -> None:
    project, assets = make_project()
    compiler = RenderCompiler(project.settings)
    asset_index = {asset.asset_id: asset for asset in assets}

    timeline_scene = compiler.compile(project.nodes[0], asset_index)

    assert timeline_scene.scene_id == "scene-001"
    assert timeline_scene.width == 1920
    assert timeline_scene.height == 1080
    assert timeline_scene.background_clip.asset_kind == AssetKind.VIDEO
    assert timeline_scene.overlay_clips[0].width_px == 384
    assert timeline_scene.text_clips[0].anim == "pop"
    assert timeline_scene.subtitle_ass_path == "subtitles/scene-001.ass"


def test_scene_fingerprint_changes_when_render_data_changes() -> None:
    project, assets = make_project()

    fingerprint_a = build_scene_fingerprint(
        scene=project.nodes[0],
        project_settings=project.settings,
        asset_records=assets,
        compositor_version="0.1.0",
    )

    project.nodes[0].texts[0].content = "90 USD?"

    fingerprint_b = build_scene_fingerprint(
        scene=project.nodes[0],
        project_settings=project.settings,
        asset_records=assets,
        compositor_version="0.1.0",
    )

    assert fingerprint_a != fingerprint_b


def test_render_plan_builder_creates_cache_paths() -> None:
    project, assets = make_project()
    compiler = RenderCompiler(project.settings)
    asset_index = {asset.asset_id: asset for asset in assets}
    timeline_scene = compiler.compile(project.nodes[0], asset_index)

    plan = RenderPlanBuilder().build(
        timeline_scene=timeline_scene,
        fingerprint="abc123",
        cache_root="C:/cache",
    )

    assert Path(plan.outputs.scene_output_path) == Path("C:/cache/scenes/scene-001/abc123/scene.mp4")
    assert Path(plan.outputs.preview_output_path) == Path("C:/cache/scenes/scene-001/abc123/preview.png")
    assert Path(plan.outputs.manifest_output_path) == Path("C:/cache/scenes/scene-001/abc123/render_manifest.json")
    assert plan.inputs[0].role == "background"


def test_render_pipeline_builds_ffmpeg_command() -> None:
    project, assets = make_project()
    request = RenderSceneRequest(
        project=project,
        scene_id="scene-001",
        assets=assets,
        cache_root="C:/cache",
        ffmpeg_path="C:/bin/ffmpeg.exe",
    )

    result = RenderPipeline().prepare_scene_render(request)

    assert result.render_plan.scene_id == "scene-001"
    assert Path(result.ffmpeg_command[0]) == Path("C:/bin/ffmpeg.exe")
    assert "-filter_complex" in result.ffmpeg_command
    assert Path(result.preview_command[0]) == Path("C:/bin/ffmpeg.exe")
    assert result.render_plan.outputs.scene_output_path.endswith("scene.mp4")
    assert result.execution is None


def test_ffmpeg_command_builder_maps_final_video_output() -> None:
    project, assets = make_project()
    request = RenderSceneRequest(
        project=project,
        scene_id="scene-001",
        assets=assets,
        cache_root="C:/cache",
        ffmpeg_path="ffmpeg",
    )

    result = RenderPipeline().prepare_scene_render(request)
    command = FfmpegCommandBuilder("ffmpeg").build(result.render_plan)

    assert "-map" in command
    assert command[-1].endswith("scene.mp4")


def test_subtitle_ass_builder_emits_dialogue_lines() -> None:
    project, assets = make_project()
    request = RenderSceneRequest(
        project=project,
        scene_id="scene-001",
        assets=assets,
        cache_root="C:/cache",
        ffmpeg_path="ffmpeg",
    )
    result = RenderPipeline().prepare_scene_render(request)

    ass_text = SubtitleAssBuilder().build(result.render_plan.timeline_scene)

    assert "[Events]" in ass_text
    assert "Dialogue:" in ass_text
    assert "Rockstar podria cambiar el mercado." in ass_text


def test_preview_command_targets_preview_png() -> None:
    project, assets = make_project()
    request = RenderSceneRequest(
        project=project,
        scene_id="scene-001",
        assets=assets,
        cache_root="C:/cache",
        ffmpeg_path="ffmpeg",
    )
    result = RenderPipeline().prepare_scene_render(request)

    preview_command = FfmpegExecutor(ffmpeg_path="ffmpeg").build_preview_command(result.render_plan)

    assert "-frames:v" in preview_command
    assert preview_command[-1].endswith("preview.png")


def test_prepare_scene_render_writes_manifest_to_cache() -> None:
    project, assets = make_project()
    with TemporaryDirectory() as temp_dir:
        request = RenderSceneRequest(
            project=project,
            scene_id="scene-001",
            assets=assets,
            cache_root=temp_dir,
            ffmpeg_path="ffmpeg",
        )

        result = RenderPipeline().prepare_scene_render(request)
        manifest_path = Path(result.render_plan.outputs.manifest_output_path)

        assert manifest_path.exists()
        manifest = RenderManifestService().read(str(manifest_path))
        assert manifest.scene_id == "scene-001"
        assert manifest.fingerprint == result.fingerprint
        assert manifest.execution is None


# ── Cache hit detection tests ─────────────────────────────────────────────────


def _write_fake_manifest_at_path(manifest_path: str, scene_id: str, fingerprint: str, *, exit_code: int = 0, ffmpeg_executed: bool = True) -> None:
    """Escribe un manifest falso en la ruta exacta dada.

    Args:
        manifest_path: Ruta completa donde escribir el manifest.
        scene_id: ID de la escena.
        fingerprint: SHA-256 fingerprint.
        exit_code: Código de salida de FFmpeg.
        ffmpeg_executed: Si FFmpeg se ejecutó.
    """
    from app.domain.models import (
        RenderExecutionDetails,
        RenderJobResult,
        RenderPlan,
        RenderPlanFilterStage,
        RenderPlanInput,
        RenderPlanOutputs,
        TimelineScene,
        CompiledBackgroundClip,
        AssetKind,
        ZoomMotion,
    )

    scene_root = Path(manifest_path).parent
    scene_root.mkdir(parents=True, exist_ok=True)

    scene_path = str(scene_root / "scene.mp4")
    preview_path = str(scene_root / "preview.png")

    fake_timeline = TimelineScene(
        scene_id=scene_id,
        width=1920,
        height=1080,
        fps=30,
        duration_ms=5000,
        background_clip=CompiledBackgroundClip(
            absolute_path="/fake/bg.mp4",
            asset_kind=AssetKind.VIDEO,
            trim_in_ms=0,
            trim_out_ms=5000,
            loop_mode="cut",
        ),
        overlay_clips=[],
        text_clips=[],
        zoom=ZoomMotion(),
        subtitle_ass_path=None,
    )
    fake_plan = RenderPlan(
        plan_id=f"{scene_id}:{fingerprint}",
        scene_id=scene_id,
        timeline_scene=fake_timeline,
        inputs=[RenderPlanInput(
            input_id="bg",
            absolute_path="/fake/bg.mp4",
            asset_kind=AssetKind.VIDEO,
            role="background",
        )],
        filter_stages=[RenderPlanFilterStage(name="normalize_background", description="test")],
        outputs=RenderPlanOutputs(
            scene_output_path=scene_path,
            preview_output_path=preview_path,
            manifest_output_path=manifest_path,
        ),
    )
    execution = RenderExecutionDetails(
        scene_output_path=scene_path,
        preview_output_path=preview_path,
        ffmpeg_executed=ffmpeg_executed,
        preview_generated=True,
        exit_code=exit_code,
        preview_exit_code=0,
    )
    fake_result = RenderJobResult(
        timeline_scene=fake_timeline,
        fingerprint=fingerprint,
        render_plan=fake_plan,
        ffmpeg_command=["ffmpeg", "-i", "/fake/bg.mp4", "-c", "copy", scene_path],
        preview_command=["ffmpeg", "-i", scene_path, "-frames:v", "1", preview_path],
        execution=execution,
    )
    RenderManifestService().write(fake_result)


def test_cache_miss_no_manifest() -> None:
    """No existe manifest → FFmpeg se ejecuta, cache_hit=False."""
    project, assets = make_project()
    with TemporaryDirectory() as temp_dir:
        request = RenderSceneRequest(
            project=project,
            scene_id="scene-001",
            assets=assets,
            cache_root=temp_dir,
            ffmpeg_path="ffmpeg",
        )

        result = RenderPipeline().prepare_scene_render(request)

        # Borrar el manifest para simular cache miss
        manifest_path = Path(result.render_plan.outputs.manifest_output_path)
        manifest_path.unlink()

        cached = RenderPipeline()._try_load_cached_render(result)
        assert cached is None
        assert result.cache_hit is False


def test_cache_hit_valid() -> None:
    """Manifest válido + scene.mp4 válido → FFmpeg NO se ejecuta, cache_hit=True."""
    project, assets = make_project()
    with TemporaryDirectory() as temp_dir:
        request = RenderSceneRequest(
            project=project,
            scene_id="scene-001",
            assets=assets,
            cache_root=temp_dir,
            ffmpeg_path="ffmpeg",
        )

        result = RenderPipeline().prepare_scene_render(request)
        fingerprint = result.fingerprint
        scene_id = result.render_plan.scene_id
        scene_path = Path(result.render_plan.outputs.scene_output_path)
        preview_path = Path(result.render_plan.outputs.preview_output_path)
        manifest_path = result.render_plan.outputs.manifest_output_path

        # Sobrescribir el manifest con execution exitosa en la ruta correcta
        _write_fake_manifest_at_path(manifest_path, scene_id, fingerprint, exit_code=0, ffmpeg_executed=True)

        # Crear archivos válidos
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_bytes(b"fake-mp4-content")
        preview_path.write_bytes(b"fake-png-content")

        cached = RenderPipeline()._try_load_cached_render(result)
        assert cached is not None
        assert cached.cache_hit is True
        assert cached.fingerprint == fingerprint
        assert cached.execution is not None
        assert cached.execution.ffmpeg_executed is True


def test_cache_invalid_corrupt_manifest() -> None:
    """Manifest JSON corrupto → invalidar cache, rerenderizar."""
    project, assets = make_project()
    with TemporaryDirectory() as temp_dir:
        request = RenderSceneRequest(
            project=project,
            scene_id="scene-001",
            assets=assets,
            cache_root=temp_dir,
            ffmpeg_path="ffmpeg",
        )

        result = RenderPipeline().prepare_scene_render(request)
        manifest_path = Path(result.render_plan.outputs.manifest_output_path)

        # Corromper el manifest
        manifest_path.write_text("NOT VALID JSON {{{", encoding="utf-8")

        cached = RenderPipeline()._try_load_cached_render(result)
        assert cached is None


def test_cache_invalid_missing_scene_mp4() -> None:
    """Manifest OK pero scene.mp4 falta → invalidar cache, rerenderizar."""
    project, assets = make_project()
    with TemporaryDirectory() as temp_dir:
        request = RenderSceneRequest(
            project=project,
            scene_id="scene-001",
            assets=assets,
            cache_root=temp_dir,
            ffmpeg_path="ffmpeg",
        )

        result = RenderPipeline().prepare_scene_render(request)
        scene_path = Path(result.render_plan.outputs.scene_output_path)

        # Borrar scene.mp4 si existe (prepare no lo crea, pero por seguridad)
        if scene_path.exists():
            scene_path.unlink()

        cached = RenderPipeline()._try_load_cached_render(result)
        assert cached is None


def test_cache_invalid_previous_failed() -> None:
    """execution.exit_code != 0 → invalidar cache, rerenderizar."""
    project, assets = make_project()
    with TemporaryDirectory() as temp_dir:
        request = RenderSceneRequest(
            project=project,
            scene_id="scene-001",
            assets=assets,
            cache_root=temp_dir,
            ffmpeg_path="ffmpeg",
        )

        result = RenderPipeline().prepare_scene_render(request)
        fingerprint = result.fingerprint
        scene_id = result.render_plan.scene_id
        scene_path = Path(result.render_plan.outputs.scene_output_path)
        preview_path = Path(result.render_plan.outputs.preview_output_path)
        manifest_path = result.render_plan.outputs.manifest_output_path

        # Escribir manifest con exit_code != 0 en la ruta correcta
        _write_fake_manifest_at_path(manifest_path, scene_id, fingerprint, exit_code=1)

        # Crear archivos (existen pero el render falló)
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_bytes(b"partial-output")
        preview_path.write_bytes(b"partial-preview")

        cached = RenderPipeline()._try_load_cached_render(result)
        assert cached is None


def test_cache_hit_propagates_to_result() -> None:
    """Cache hit → result tiene cache_hit=True y WebSocket data lo incluye."""
    project, assets = make_project()
    with TemporaryDirectory() as temp_dir:
        request = RenderSceneRequest(
            project=project,
            scene_id="scene-001",
            assets=assets,
            cache_root=temp_dir,
            ffmpeg_path="ffmpeg",
        )

        result = RenderPipeline().prepare_scene_render(request)
        fingerprint = result.fingerprint
        scene_id = result.render_plan.scene_id
        scene_path = Path(result.render_plan.outputs.scene_output_path)
        preview_path = Path(result.render_plan.outputs.preview_output_path)
        manifest_path = result.render_plan.outputs.manifest_output_path

        # Escribir cache válido en la ruta correcta
        _write_fake_manifest_at_path(manifest_path, scene_id, fingerprint, exit_code=0, ffmpeg_executed=True)
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_bytes(b"cached-scene")
        preview_path.write_bytes(b"cached-preview")

        cached = RenderPipeline()._try_load_cached_render(result)

        assert cached is not None
        assert cached.cache_hit is True
        assert cached.execution is not None
        assert cached.execution.ffmpeg_executed is True
        assert cached.execution.exit_code == 0
        assert cached.fingerprint == fingerprint
