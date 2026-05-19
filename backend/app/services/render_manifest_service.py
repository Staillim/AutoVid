from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import RenderJobResult, RenderSceneManifest


class RenderManifestService:
    def write(self, result: RenderJobResult) -> RenderSceneManifest:
        manifest = RenderSceneManifest(
            scene_id=result.render_plan.scene_id,
            fingerprint=result.fingerprint,
            generated_at=self._utcnow(),
            render_plan=result.render_plan,
            ffmpeg_command=result.ffmpeg_command,
            preview_command=result.preview_command,
            execution=result.execution,
        )
        path = Path(result.render_plan.outputs.manifest_output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest

    def read(self, manifest_path: str) -> RenderSceneManifest:
        raw = Path(manifest_path).read_text(encoding="utf-8")
        return RenderSceneManifest.model_validate_json(raw)

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat()
