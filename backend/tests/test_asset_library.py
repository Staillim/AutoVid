"""Tests de AssetLibrary — importar, consultar y eliminar assets."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.domain.models import AssetKind
from app.services.asset_library import AssetLibrary, AssetImportError, AssetNotFoundError

# Assets generados por el smoke test (existentes en disco)
SMOKE_ASSETS = Path(__file__).resolve().parents[1] / ".smoke" / "assets"
SMOKE_BG = SMOKE_ASSETS / "background.mp4"
SMOKE_OV = SMOKE_ASSETS / "overlay.png"

# Fixture mínima avproj (usada como archivo de extensión no reconocida)
AVPROJ_FIXTURE = Path(__file__).resolve().parents[2] / "shared" / "examples" / "minimal_project.avproj"

_HAVE_SMOKE = SMOKE_BG.exists() and SMOKE_OV.exists()
skip_no_smoke = pytest.mark.skipif(not _HAVE_SMOKE, reason="smoke assets no generados aún")


# ── fixture de pytest ─────────────────────────────────────────────────────────

@pytest.fixture()
def lib_factory():
    """Factory que crea AssetLibrary en un directorio temporal.

    Garantiza dispose() antes de que TemporaryDirectory limpie el .db
    (evita PermissionError en Windows con SQLite).
    """
    instances: list[tuple[AssetLibrary, TemporaryDirectory]] = []

    def make() -> AssetLibrary:
        tmp = TemporaryDirectory()
        library = AssetLibrary(db_path=Path(tmp.name) / "library.db")
        instances.append((library, tmp))
        return library

    yield make

    for library, tmp in instances:
        library.dispose()
        tmp.cleanup()


# ── import_asset ──────────────────────────────────────────────────────────────

@skip_no_smoke
def test_asset_library_import_video_extracts_metadata(lib_factory) -> None:
    lib = lib_factory()
    record = lib.import_asset(SMOKE_BG)

    assert record.asset_id
    assert record.kind == AssetKind.VIDEO
    assert record.absolute_path == str(SMOKE_BG)
    assert record.content_sha256
    assert record.size_bytes > 0
    assert record.duration_ms is not None and record.duration_ms > 0
    assert record.width == 1280
    assert record.height == 720
    assert record.fps is not None and record.fps > 0


@skip_no_smoke
def test_asset_library_import_image_has_no_duration(lib_factory) -> None:
    lib = lib_factory()
    record = lib.import_asset(SMOKE_OV)

    assert record.kind == AssetKind.IMAGE
    assert record.duration_ms is None


@skip_no_smoke
def test_asset_library_import_is_idempotent(lib_factory) -> None:
    """Importar el mismo archivo dos veces retorna el mismo record (sin duplicar)."""
    lib = lib_factory()
    first = lib.import_asset(SMOKE_BG)
    second = lib.import_asset(SMOKE_BG)

    assert first.asset_id == second.asset_id
    assert lib.count() == 1


def test_asset_library_import_raises_for_missing_file(lib_factory) -> None:
    lib = lib_factory()
    with pytest.raises(AssetImportError, match="no encontrado"):
        lib.import_asset("/ruta/inexistente/video.mp4")


def test_asset_library_import_raises_for_unknown_extension(lib_factory) -> None:
    lib = lib_factory()
    with pytest.raises(AssetImportError, match="extensión no reconocida"):
        lib.import_asset(AVPROJ_FIXTURE)


# ── get ───────────────────────────────────────────────────────────────────────

@skip_no_smoke
def test_asset_library_get_returns_imported_asset(lib_factory) -> None:
    lib = lib_factory()
    imported = lib.import_asset(SMOKE_BG)
    fetched = lib.get(imported.asset_id)

    assert fetched.asset_id == imported.asset_id
    assert fetched.kind == AssetKind.VIDEO


def test_asset_library_get_raises_for_unknown_id(lib_factory) -> None:
    lib = lib_factory()
    with pytest.raises(AssetNotFoundError):
        lib.get("id-que-no-existe")


# ── list ──────────────────────────────────────────────────────────────────────

@skip_no_smoke
def test_asset_library_list_returns_all(lib_factory) -> None:
    lib = lib_factory()
    lib.import_asset(SMOKE_BG)
    lib.import_asset(SMOKE_OV)

    all_assets = lib.list()
    assert len(all_assets) == 2


@skip_no_smoke
def test_asset_library_list_filters_by_kind(lib_factory) -> None:
    lib = lib_factory()
    lib.import_asset(SMOKE_BG)
    lib.import_asset(SMOKE_OV)

    videos = lib.list(kind=AssetKind.VIDEO)
    images = lib.list(kind=AssetKind.IMAGE)

    assert len(videos) == 1 and videos[0].kind == AssetKind.VIDEO
    assert len(images) == 1 and images[0].kind == AssetKind.IMAGE


# ── search ────────────────────────────────────────────────────────────────────

@skip_no_smoke
def test_asset_library_search_finds_by_filename(lib_factory) -> None:
    lib = lib_factory()
    lib.import_asset(SMOKE_BG)

    results = lib.search("background")
    assert len(results) == 1

    empty = lib.search("nombre-que-no-existe")
    assert len(empty) == 0


# ── remove ────────────────────────────────────────────────────────────────────

@skip_no_smoke
def test_asset_library_remove_deletes_from_index(lib_factory) -> None:
    lib = lib_factory()
    record = lib.import_asset(SMOKE_BG)

    removed = lib.remove(record.asset_id)
    assert removed is True
    assert lib.count() == 0


def test_asset_library_remove_returns_false_for_unknown_id(lib_factory) -> None:
    lib = lib_factory()
    result = lib.remove("id-inexistente")
    assert result is False


# ── count ─────────────────────────────────────────────────────────────────────

def test_asset_library_count_empty(lib_factory) -> None:
    lib = lib_factory()
    assert lib.count() == 0


@skip_no_smoke
def test_asset_library_count_after_import(lib_factory) -> None:
    lib = lib_factory()
    lib.import_asset(SMOKE_BG)
    assert lib.count() == 1
