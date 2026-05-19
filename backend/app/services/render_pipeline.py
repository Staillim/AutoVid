from __future__ import annotations

from typing import Callable

from app.core.settings import AppSettings
from app.domain.models import RenderJobResult, RenderSceneRequest
from app.services.cache_fingerprint import build_scene_fingerprint
from app.services.ffmpeg_command_builder import FfmpegCommandBuilder
from app.services.ffmpeg_executor import FfmpegExecutor
from app.services.render_manifest_service import RenderManifestService
from app.services.render_compiler import RenderCompiler, RenderCompilerError
from app.services.render_plan_builder import RenderPlanBuilder


class RenderPipeline:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings.from_env()

    def prepare_scene_render(self, request: RenderSceneRequest) -> RenderJobResult:
        node = request.project.get_scene(request.scene_id)
        if node is None:
            raise RenderCompilerError("scene not found")

        resolved_cache_root = self.settings.resolve_cache_root(
            override=request.cache_root,
            project_id=request.project.project_id,
        )
        resolved_ffmpeg_path = self.settings.resolve_ffmpeg_path(request.ffmpeg_path)

        asset_index = {asset.asset_id: asset for asset in request.assets}
        compiler = RenderCompiler(request.project.settings)
        timeline_scene = compiler.compile(node=node, asset_index=asset_index)

        fingerprint = build_scene_fingerprint(
            scene=node,
            project_settings=request.project.settings,
            asset_records=request.assets,
            compositor_version="0.2.0",
        )
        plan = RenderPlanBuilder().build(
            timeline_scene=timeline_scene,
            fingerprint=fingerprint,
            cache_root=resolved_cache_root,
        )
        executor = FfmpegExecutor(ffmpeg_path=resolved_ffmpeg_path)
        command = FfmpegCommandBuilder(ffmpeg_path=resolved_ffmpeg_path).build(plan)
        preview_command = executor.build_preview_command(plan)
        result = RenderJobResult(
            timeline_scene=timeline_scene,
            fingerprint=fingerprint,
            render_plan=plan,
            ffmpeg_command=command,
            preview_command=preview_command,
        )
        RenderManifestService().write(result)
        return result

    def execute_scene_render(
        self,
        request: RenderSceneRequest,
        *,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> RenderJobResult:
        prepared = self.prepare_scene_render(request)
        execution = FfmpegExecutor(ffmpeg_path=prepared.ffmpeg_command[0]).execute(
            prepared.render_plan,
            progress_callback=progress_callback,
        )
        executed = prepared.model_copy(update={"execution": execution})
        RenderManifestService().write(executed)
        return executed
