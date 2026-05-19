from __future__ import annotations

import hashlib
import json

from app.domain.models import AssetRecord, ProjectSettings, SceneNode


def build_scene_fingerprint(
    *,
    scene: SceneNode,
    project_settings: ProjectSettings,
    asset_records: list[AssetRecord],
    compositor_version: str,
) -> str:
    relevant_assets = sorted(
        (
            asset.model_dump(mode="json")
            for asset in asset_records
            if _scene_uses_asset(scene=scene, asset_id=asset.asset_id)
        ),
        key=lambda item: item["asset_id"],
    )

    payload = {
        "render_schema_version": "1.0.0",
        "compositor_version": compositor_version,
        "project_settings": project_settings.model_dump(mode="json"),
        "scene": scene.model_dump(mode="json", exclude={"ui", "tags"}),
        "assets": relevant_assets,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scene_uses_asset(*, scene: SceneNode, asset_id: str) -> bool:
    if scene.background.asset.asset_id == asset_id:
        return True
    if any(overlay.asset.asset_id == asset_id for overlay in scene.overlays):
        return True
    return False
