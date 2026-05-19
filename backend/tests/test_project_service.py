"""Tests del ProjectService — abrir, guardar, crear y validar .avproj."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.domain.models import ProjectModel, ProjectSettings, SCHEMA_VERSION
from app.services.project_service import (
    ProjectNotFoundError,
    ProjectParseError,
    ProjectSaveError,
    ProjectService,
)

MINIMAL_AVPROJ = Path(__file__).resolve().parents[2] / "shared" / "examples" / "minimal_project.avproj"


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ── open() ────────────────────────────────────────────────────────────────────

def test_project_service_open_loads_minimal_fixture() -> None:
    """Abre el fixture minimal_project.avproj y valida los campos básicos."""
    service = ProjectService()
    project = service.open(MINIMAL_AVPROJ)

    assert project.project_id == "example-project-001"
    assert project.schema_version == "1.0.0"
    assert len(project.nodes) == 1
    assert project.nodes[0].id == "scene-example-001"


def test_project_service_open_raises_not_found() -> None:
    service = ProjectService()
    with pytest.raises(ProjectNotFoundError):
        service.open("/ruta/que/no/existe/proyecto.avproj")


def test_project_service_open_raises_parse_error_on_bad_json() -> None:
    with TemporaryDirectory() as tmp:
        bad_file = Path(tmp) / "bad.avproj"
        bad_file.write_text("esto no es JSON {{{", encoding="utf-8")

        service = ProjectService()
        with pytest.raises(ProjectParseError, match="JSON inválido"):
            service.open(bad_file)


def test_project_service_open_raises_parse_error_on_invalid_schema() -> None:
    with TemporaryDirectory() as tmp:
        bad_file = Path(tmp) / "invalid.avproj"
        # JSON válido pero sin los campos requeridos por ProjectModel
        _write_json(bad_file, {"schema_version": "1.0.0", "nombre": "sin campos requeridos"})

        service = ProjectService()
        with pytest.raises(ProjectParseError, match="schema del dominio"):
            service.open(bad_file)


# ── save() ────────────────────────────────────────────────────────────────────

def test_project_service_save_writes_valid_file() -> None:
    service = ProjectService()
    project = service.open(MINIMAL_AVPROJ)

    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "output.avproj"
        saved_path = service.save(project, output_path)

        assert saved_path == output_path
        assert saved_path.exists()
        assert saved_path.stat().st_size > 0

        # El archivo guardado debe poder cargarse de vuelta
        reloaded = service.open(saved_path)
        assert reloaded.project_id == project.project_id
        assert len(reloaded.nodes) == len(project.nodes)


def test_project_service_save_updates_updated_at() -> None:
    service = ProjectService()
    project = service.open(MINIMAL_AVPROJ)
    original_updated_at = project.updated_at

    with TemporaryDirectory() as tmp:
        saved_path = service.save(project, Path(tmp) / "out.avproj")
        reloaded = service.open(saved_path)

        assert reloaded.updated_at != original_updated_at


def test_project_service_save_creates_parent_dirs() -> None:
    service = ProjectService()
    project = service.open(MINIMAL_AVPROJ)

    with TemporaryDirectory() as tmp:
        nested_path = Path(tmp) / "subdir" / "deep" / "project.avproj"
        service.save(project, nested_path)
        assert nested_path.exists()


# ── create() ──────────────────────────────────────────────────────────────────

def test_project_service_create_returns_valid_project() -> None:
    service = ProjectService()
    project = service.create(name="Mi video de prueba")

    assert isinstance(project, ProjectModel)
    assert project.name == "Mi video de prueba"
    assert project.schema_version == SCHEMA_VERSION
    assert project.nodes == []
    assert project.scene_order == []
    assert project.project_id  # UUID generado


def test_project_service_create_accepts_custom_settings() -> None:
    service = ProjectService()
    custom_settings = ProjectSettings(width=1920, height=1080, fps=60)
    project = service.create(name="HD 60fps", settings=custom_settings)

    assert project.settings.width == 1920
    assert project.settings.fps == 60


def test_project_service_create_two_projects_have_different_ids() -> None:
    service = ProjectService()
    a = service.create(name="Proyecto A")
    b = service.create(name="Proyecto B")
    assert a.project_id != b.project_id


# ── roundtrip ─────────────────────────────────────────────────────────────────

def test_project_service_create_save_open_roundtrip() -> None:
    """Crea un proyecto, lo guarda y lo carga de vuelta íntegramente."""
    service = ProjectService()
    original = service.create(name="Roundtrip Test", library_id="my-lib")

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "roundtrip.avproj"
        service.save(original, path)
        loaded = service.open(path)

        assert loaded.project_id == original.project_id
        assert loaded.name == original.name
        assert loaded.library_binding.library_id == "my-lib"


# ── is_compatible() ───────────────────────────────────────────────────────────

def test_project_service_is_compatible_with_valid_file() -> None:
    service = ProjectService()
    ok, reason = service.is_compatible(MINIMAL_AVPROJ)
    assert ok is True
    assert reason == ""


def test_project_service_is_compatible_returns_false_for_wrong_version() -> None:
    with TemporaryDirectory() as tmp:
        bad_version = Path(tmp) / "old.avproj"
        _write_json(bad_version, {"schema_version": "0.9.0"})

        service = ProjectService()
        ok, reason = service.is_compatible(bad_version)
        assert ok is False
        assert "0.9.0" in reason


def test_project_service_is_compatible_returns_false_for_missing_file() -> None:
    service = ProjectService()
    ok, reason = service.is_compatible("/ruta/inexistente/proj.avproj")
    assert ok is False
    assert "no encontrado" in reason


# ── check_schema_version() ────────────────────────────────────────────────────

def test_project_service_check_schema_version_current() -> None:
    service = ProjectService()
    project = service.open(MINIMAL_AVPROJ)
    assert service.check_schema_version(project) is True
