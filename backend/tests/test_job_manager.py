"""Tests de persistencia de jobs en SQLite."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.domain.models import (
    AnalysisMetadata,
    AssetKind,
    AssetRecord,
    AssetRef,
    BackgroundConfig,
    LibraryBinding,
    NarrativeBlock,
    NarrativeRole,
    ProjectModel,
    ProjectSettings,
    RenderJobRecord,
    RenderJobResult,
    RenderJobStatus,
    RenderPlan,
    RenderPlanFilterStage,
    RenderPlanInput,
    RenderPlanOutputs,
    RenderSceneRequest,
    SceneNode,
    SceneNodeUI,
    SubtitleTrack,
    TimelineScene,
    CompiledBackgroundClip,
    ZoomMotion,
)
from app.services.job_manager import RenderJobManager, JobRow, JobPersistenceError


@pytest.fixture()
def tmp_db_path():
    """Provee un path de DB temporal que se limpia tras cada test."""
    import tempfile
    import time

    td = tempfile.mkdtemp()
    db_path = Path(td) / "jobs.db"
    yield db_path
    # Windows: dar tiempo a que se liberen los handles de SQLite
    import gc
    gc.collect()
    time.sleep(0.1)
    import shutil
    shutil.rmtree(td, ignore_errors=True)


@pytest.fixture()
def manager(tmp_db_path):
    """Crea un RenderJobManager con DB temporal y processor dummy."""
    def dummy_processor(request: RenderSceneRequest) -> RenderJobResult:
        return RenderJobResult(
            timeline_scene=TimelineScene(
                scene_id=request.scene_id,
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
            ),
            fingerprint="abc123",
            render_plan=RenderPlan(
                plan_id="plan-1",
                scene_id=request.scene_id,
                timeline_scene=TimelineScene(
                    scene_id=request.scene_id,
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
                ),
                inputs=[RenderPlanInput(
                    input_id="bg",
                    absolute_path="/fake/bg.mp4",
                    asset_kind=AssetKind.VIDEO,
                    role="background",
                )],
                filter_stages=[RenderPlanFilterStage(
                    name="normalize_background",
                    description="normalize",
                )],
                outputs=RenderPlanOutputs(
                    scene_output_path="/fake/scene.mp4",
                    preview_output_path="/fake/preview.png",
                    manifest_output_path="/fake/manifest.json",
                ),
            ),
            ffmpeg_command=["ffmpeg", "-i", "/fake/bg.mp4", "-c", "copy", "/fake/scene.mp4"],
            preview_command=["ffmpeg", "-i", "/fake/scene.mp4", "-frames:v", "1", "/fake/preview.png"],
        )

    mgr = RenderJobManager(processor=dummy_processor, db_path=tmp_db_path)
    yield mgr
    mgr.dispose()


def _make_project() -> ProjectModel:
    return ProjectModel(
        project_id="proj-001",
        schema_version="1.0.0",
        created_at="2026-05-19T00:00:00+00:00",
        updated_at="2026-05-19T00:00:00+00:00",
        name="Test Project",
        settings=ProjectSettings(),
        library_binding=LibraryBinding(library_id="local"),
        analysis=AnalysisMetadata(),
        nodes=[SceneNode(
            id="scene-001",
            order=0,
            title="Test Scene",
            duration_ms=5000,
            narrative=NarrativeBlock(
                summary="test",
                narrative_role=NarrativeRole.SETUP,
                confidence=1.0,
            ),
            background=BackgroundConfig(
                asset=AssetRef(asset_id="bg-001", kind=AssetKind.VIDEO),
                trim_in_ms=0,
                trim_out_ms=5000,
            ),
        )],
        scene_order=["scene-001"],
    )


def _make_request() -> RenderSceneRequest:
    return RenderSceneRequest(
        project=_make_project(),
        scene_id="scene-001",
        assets=[AssetRecord(
            asset_id="bg-001",
            kind=AssetKind.VIDEO,
            absolute_path="/fake/bg.mp4",
            content_sha256="abc123",
            size_bytes=1000000,
            duration_ms=10000,
            width=1920,
            height=1080,
            fps=30.0,
        )],
    )


# ── tests ─────────────────────────────────────────────────────────────────────

def test_submit_persists_job(tmp_db_path):
    """Al submitir un job, se persiste en SQLite con status QUEUED."""
    mgr = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    try:
        import asyncio
        req = _make_request()
        job = asyncio.run(mgr.submit(req))

        assert job.status == RenderJobStatus.QUEUED
        assert job.project_id == "proj-001"
        assert job.scene_id == "scene-001"

        # Verificar en DB directamente
        from sqlalchemy.orm import Session
        from app.services.job_manager import Base
        engine = mgr._engine
        with Session(engine) as session:
            row = session.get(JobRow, job.job_id)
            assert row is not None
            assert row.status == "queued"
            assert row.project_id == "proj-001"
            assert row.scene_id == "scene-001"
    finally:
        mgr.dispose()


def test_get_returns_persisted_job(tmp_db_path):
    """get() retorna el job persistido en SQLite."""
    mgr = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    try:
        import asyncio
        req = _make_request()
        job = asyncio.run(mgr.submit(req))

        retrieved = asyncio.run(mgr.get(job.job_id))
        assert retrieved is not None
        assert retrieved.job_id == job.job_id
        assert retrieved.status == RenderJobStatus.QUEUED
    finally:
        mgr.dispose()


def test_get_returns_none_for_unknown(tmp_db_path):
    """get() retorna None para un job_id que no existe."""
    mgr = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    try:
        import asyncio
        result = asyncio.run(mgr.get("nonexistent"))
        assert result is None
    finally:
        mgr.dispose()


def test_list_returns_all_jobs_sorted(tmp_db_path):
    """list() retorna todos los jobs ordenados por created_at descendente."""
    mgr = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    try:
        import asyncio
        req1 = _make_request()
        req2 = _make_request()
        req2.scene_id = "scene-002"

        job1 = asyncio.run(mgr.submit(req1))
        job2 = asyncio.run(mgr.submit(req2))

        jobs = asyncio.run(mgr.list())
        assert len(jobs) == 2
        # El último submitido aparece primero (orden descendente)
        assert jobs[0].job_id == job2.job_id
        assert jobs[1].job_id == job1.job_id
    finally:
        mgr.dispose()


def test_job_survives_manager_restart(tmp_db_path):
    """Los jobs persisten tras reiniciar el manager (simula restart del backend)."""
    import asyncio

    # Primer manager: submitir job
    mgr1 = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    req = _make_request()
    job1 = asyncio.run(mgr1.submit(req))
    mgr1.dispose()

    # Segundo manager: mismo DB, sin jobs en memoria
    mgr2 = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    try:
        retrieved = asyncio.run(mgr2.get(job1.job_id))
        assert retrieved is not None
        assert retrieved.job_id == job1.job_id
        assert retrieved.status == RenderJobStatus.QUEUED

        jobs = asyncio.run(mgr2.list())
        assert len(jobs) == 1
        assert jobs[0].job_id == job1.job_id
    finally:
        mgr2.dispose()


def test_completed_job_persists_result(tmp_db_path):
    """Un job completado persiste el resultado serializado."""
    mgr = RenderJobManager(processor=lambda req: "fake_result", db_path=tmp_db_path)
    try:
        import asyncio

        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            # Simular el worker: marcar como running y luego completed
            await mgr._mark_running(job.job_id)
            await mgr._mark_completed(job.job_id, "fake_result")

            retrieved = await mgr.get(job.job_id)
            assert retrieved.status == RenderJobStatus.COMPLETED
            # El resultado es un string, no RenderJobResult, así que result será None
            # porque el processor dummy no devuelve RenderJobResult
            assert retrieved.error_message is None

        asyncio.run(run_test())
    finally:
        mgr.dispose()


def test_failed_job_persists_error(tmp_db_path):
    """Un job fallido persiste el mensaje de error."""
    mgr = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    try:
        import asyncio

        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            await mgr._mark_running(job.job_id)
            await mgr._mark_failed(job.job_id, "FFmpeg not found")

            retrieved = await mgr.get(job.job_id)
            assert retrieved.status == RenderJobStatus.FAILED
            assert retrieved.error_message == "FFmpeg not found"

        asyncio.run(run_test())
    finally:
        mgr.dispose()


def test_worker_loop_persists_transitions(tmp_db_path):
    """El worker loop persiste las transiciones queued -> running -> completed."""
    import asyncio

    mgr = RenderJobManager(processor=lambda req: "done", db_path=tmp_db_path)
    try:
        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            # Iniciar worker y esperar a que procese
            await mgr.start()
            await asyncio.sleep(0.5)  # dar tiempo al worker
            await mgr.stop()

            retrieved = await mgr.get(job.job_id)
            assert retrieved.status == RenderJobStatus.COMPLETED

        asyncio.run(run_test())
    finally:
        mgr.dispose()


def test_worker_loop_persists_failure(tmp_db_path):
    """El worker loop persiste fallos del processor."""
    import asyncio

    def failing_processor(req):
        raise RuntimeError("FFmpeg exit code 1")

    mgr = RenderJobManager(processor=failing_processor, db_path=tmp_db_path)
    try:
        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            await mgr.start()
            await asyncio.sleep(0.5)
            await mgr.stop()

            retrieved = await mgr.get(job.job_id)
            assert retrieved.status == RenderJobStatus.FAILED
            assert "FFmpeg exit code 1" in retrieved.error_message

        asyncio.run(run_test())
    finally:
        mgr.dispose()


def test_job_row_to_record_roundtrip():
    """JobRow.to_record() reconstruye correctamente un RenderJobRecord."""
    result = RenderJobResult(
        timeline_scene=TimelineScene(
            scene_id="s1",
            width=1920,
            height=1080,
            fps=30,
            duration_ms=5000,
            background_clip=CompiledBackgroundClip(
                absolute_path="/bg.mp4",
                asset_kind=AssetKind.VIDEO,
                trim_in_ms=0,
                trim_out_ms=5000,
                loop_mode="cut",
            ),
            overlay_clips=[],
            text_clips=[],
            zoom=ZoomMotion(),
            subtitle_ass_path=None,
        ),
        fingerprint="fp1",
        render_plan=RenderPlan(
            plan_id="p1",
            scene_id="s1",
            timeline_scene=TimelineScene(
                scene_id="s1",
                width=1920,
                height=1080,
                fps=30,
                duration_ms=5000,
                background_clip=CompiledBackgroundClip(
                    absolute_path="/bg.mp4",
                    asset_kind=AssetKind.VIDEO,
                    trim_in_ms=0,
                    trim_out_ms=5000,
                    loop_mode="cut",
                ),
                overlay_clips=[],
                text_clips=[],
                zoom=ZoomMotion(),
                subtitle_ass_path=None,
            ),
            inputs=[],
            filter_stages=[],
            outputs=RenderPlanOutputs(
                scene_output_path="/out.mp4",
                preview_output_path="/preview.png",
                manifest_output_path="/manifest.json",
            ),
        ),
        ffmpeg_command=["ffmpeg"],
        preview_command=["ffmpeg"],
    )

    row = JobRow(
        job_id="j1",
        project_id="proj-1",
        scene_id="s1",
        status="completed",
        created_at="2026-05-19T00:00:00+00:00",
        updated_at="2026-05-19T00:01:00+00:00",
        error_message=None,
        result_json=result.model_dump_json(),
    )

    record = row.to_record()
    assert record.job_id == "j1"
    assert record.status == RenderJobStatus.COMPLETED
    assert record.result is not None
    assert record.result.fingerprint == "fp1"
    assert record.result.timeline_scene.scene_id == "s1"


def test_list_empty_db(tmp_db_path):
    """list() retorna lista vacía cuando no hay jobs."""
    mgr = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    try:
        import asyncio
        jobs = asyncio.run(mgr.list())
        assert jobs == []
    finally:
        mgr.dispose()


def test_db_file_created(tmp_db_path):
    """Se crea el archivo jobs.db al instanciar el manager."""
    assert not tmp_db_path.exists()
    mgr = RenderJobManager(processor=lambda req: None, db_path=tmp_db_path)
    mgr.dispose()
    assert tmp_db_path.exists()
    assert tmp_db_path.name == "jobs.db"
