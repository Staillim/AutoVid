import json
from pathlib import Path


def test_minimal_project_fixture_has_expected_shape() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[2] / "shared" / "examples" / "minimal_project.avproj"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1.0.0"
    assert payload["project_id"] == "example-project-001"
    assert len(payload["nodes"]) == 1
    assert payload["scene_order"] == ["scene-example-001"]
