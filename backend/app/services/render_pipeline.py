from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from app.core.settings import AppSettings
from app.domain.models import RenderJobResult, RenderSceneRequest, RenderSceneManifest
from app.services.cache_fingerprint import build_scene_fingerprint
from app.services.ffmpeg_command_builder import FfmpegCommandBuilder
from app.services.ffmpeg_executor import FfmpegExecutor
from app.services.render_manifest_service import RenderManifestService
from app.services.render_compiler import RenderCompiler, RenderCompilerError
from app.services.render_plan_builder import RenderPlanBuilder

logger = logging.getLogger(__name__)


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

        # Intentar cache hit antes de ejecutar FFmpeg
        cached = self._try_load_cached_render(prepared)
        if cached is not None:
            logger.info("[CACHE HIT] fingerprint=%s", prepared.fingerprint)
            return cached

        logger.info("[CACHE MISS] fingerprint=%s", prepared.fingerprint)

        # Ejecutar FFmpeg
        execution = FfmpegExecutor(ffmpeg_path=prepared.ffmpeg_command[0]).execute(
            prepared.render_plan,
            progress_callback=progress_callback,
        )
        executed = prepared.model_copy(update={"execution": execution})
        RenderManifestService().write(executed)
        return executed

    def _try_load_cached_render(
        self,
        prepared: RenderJobResult,
    ) -> RenderJobResult | None:
        """Intenta cargar un render cacheado válido.

        Valida en orden:
        1. render_manifest.json existe y parsea correctamente
        2. execution.ffmpeg_executed == True
        3. execution.exit_code == 0
        4. scene.mp4 existe y tamaño > 0
        5. preview.png existe y tamaño > 0 (opcional, no bloquea)

        Retorna RenderJobResult con cache_hit=True o None si el cache es inválido.
        """
        manifest_path = prepared.render_plan.outputs.manifest_output_path
        scene_path = prepared.render_plan.outputs.scene_output_path
        preview_path = prepared.render_plan.outputs.preview_output_path

        # 1. Verificar que el manifest existe
        if not Path(manifest_path).exists():
            logger.debug("[CACHE INVALID] missing manifest for fingerprint=%s", prepared.fingerprint)
            return None

        # 2. Intentar parsear el manifest
        try:
            manifest = RenderManifestService().read(manifest_path)
        except Exception:
            logger.info("[CACHE INVALID] manifest parse error for fingerprint=%s", prepared.fingerprint)
            return None

        # 3. Verificar que la ejecución previa fue exitosa
        execution = manifest.execution
        if execution is None:
            logger.debug("[CACHE INVALID] no execution data for fingerprint=%s", prepared.fingerprint)
            return None

        if not execution.ffmpeg_executed:
            logger.debug("[CACHE INVALID] ffmpeg not executed for fingerprint=%s", prepared.fingerprint)
            return None

        if execution.exit_code != 0:
            logger.info(
                "[CACHE INVALID] previous render failed (exit_code=%s) for fingerprint=%s",
                execution.exit_code,
                prepared.fingerprint,
            )
            return None

        # 4. Verificar que scene.mp4 existe y tiene tamaño > 0
        scene_file = Path(scene_path)
        if not scene_file.exists():
            logger.info("[CACHE INVALID] missing scene.mp4 for fingerprint=%s", prepared.fingerprint)
            return None
        if scene_file.stat().st_size <= 0:
            logger.info("[CACHE INVALID] empty scene.mp4 for fingerprint=%s", prepared.fingerprint)
            return None

        # 5. Verificar preview.png (opcional — no bloquea cache hit)
        preview_file = Path(preview_path)
        if not preview_file.exists() or preview_file.stat().st_size <= 0:
            logger.debug("[CACHE WARN] missing or empty preview.png for fingerprint=%s", prepared.fingerprint)

        # Cache válido — reconstruir resultado desde manifest
        cached_result = RenderJobResult(
            timeline_scene=manifest.render_plan.timeline_scene,
            fingerprint=manifest.fingerprint,
            render_plan=manifest.render_plan,
            ffmpeg_command=manifest.ffmpeg_command,
            preview_command=manifest.preview_command,
            execution=execution,
            cache_hit=True,
        )
        return cached_result
