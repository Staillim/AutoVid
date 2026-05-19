"""Exporta los modelos Pydantic del dominio como JSON Schema a shared/jsonschema/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SCHEMA_OUTPUT_DIR = REPO_ROOT / "shared" / "jsonschema"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.models import (  # noqa: E402
    ProjectModel,
    SceneNode,
    TimelineScene,
    RenderPlan,
    RenderJobRecord,
    RuntimeHealthReport,
)


EXPORTS: list[tuple[str, type]] = [
    ("project.json", ProjectModel),
    ("scene_node.json", SceneNode),
    ("timeline_scene.json", TimelineScene),
    ("render_plan.json", RenderPlan),
    ("render_job_record.json", RenderJobRecord),
    ("runtime_health_report.json", RuntimeHealthReport),
]


def main() -> None:
    SCHEMA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename, model_class in EXPORTS:
        schema = model_class.model_json_schema()
        output_path = SCHEMA_OUTPUT_DIR / filename
        output_path.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  exported: {output_path.relative_to(REPO_ROOT)}")

    print(f"\n{len(EXPORTS)} schemas exportados a: {SCHEMA_OUTPUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
