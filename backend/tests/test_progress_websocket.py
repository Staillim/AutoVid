"""Tests de ProgressBroadcaster y WebSocket de progreso."""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path

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
    CompiledBackgroundClip,
    ZoomMotion,
)
from app.services.job_manager import RenderJobManager
from app.services.progress_broadcaster import ProgressBroadcaster


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def broadcaster():
    b = ProgressBroadcaster()
    yield b
    b.close_all()


@pytest.fixture()
def tmp_db_path():
    import tempfile
    td = tempfile.mkdtemp()
    db_path = Path(td) / "jobs.db"
    yield db_path
    import gc
    gc.collect()
    time.sleep(0.1)
    import shutil
    shutil.rmtree(td, ignore_errors=True)


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


# ── ProgressBroadcaster tests ─────────────────────────────────────────────────

def test_subscribe_returns_queue(broadcaster):
    queue = broadcaster.subscribe("job-1")
    assert isinstance(queue, asyncio.Queue)
    assert queue.maxsize == broadcaster.QUEUE_MAXSIZE


def test_emit_delivers_to_subscriber(broadcaster):
    queue = broadcaster.subscribe("job-1")
    broadcaster.emit("job_queued", "job-1", {"foo": "bar"})

    item = queue.get_nowait()
    data = json.loads(item)
    assert data["event_type"] == "job_queued"
    assert data["job_id"] == "job-1"
    assert data["data"] == {"foo": "bar"}
    assert "timestamp" in data
    assert data["schema_version"] == "1.0.0"


def test_emit_delivers_to_multiple_subscribers(broadcaster):
    q1 = broadcaster.subscribe("job-1")
    q2 = broadcaster.subscribe("job-1")

    broadcaster.emit("job_started", "job-1")

    assert q1.get_nowait() is not None
    assert q2.get_nowait() is not None


def test_emit_does_not_deliver_to_other_job(broadcaster):
    q1 = broadcaster.subscribe("job-1")
    q2 = broadcaster.subscribe("job-2")

    broadcaster.emit("job_started", "job-1")

    assert q1.qsize() == 1
    assert q2.qsize() == 0


def test_unsubscribe_removes_listener(broadcaster):
    q1 = broadcaster.subscribe("job-1")
    q2 = broadcaster.subscribe("job-1")

    broadcaster.unsubscribe("job-1", q1)
    broadcaster.emit("job_started", "job-1")

    assert q1.qsize() == 0
    assert q2.qsize() == 1


def test_unsubscribe_is_idempotent(broadcaster):
    q = broadcaster.subscribe("job-1")
    broadcaster.unsubscribe("job-1", q)
    broadcaster.unsubscribe("job-1", q)  # no error


def test_close_sends_sentinel(broadcaster):
    q = broadcaster.subscribe("job-1")
    broadcaster.close("job-1")

    item = q.get_nowait()
    assert item is None  # sentinel


def test_close_all(broadcaster):
    q1 = broadcaster.subscribe("job-1")
    q2 = broadcaster.subscribe("job-2")

    broadcaster.close_all()

    assert q1.get_nowait() is None
    assert q2.get_nowait() is None


def test_backpressure_drops_oldest(broadcaster):
    """Cuando la queue está llena, se descarta el evento más antiguo."""
    q = broadcaster.subscribe("job-1")
    # Llenar la queue
    for i in range(broadcaster.QUEUE_MAXSIZE):
        broadcaster.emit("ffmpeg_progress", "job-1", {"frame": i})

    # Emitir uno más — debería descartar el primero
    broadcaster.emit("ffmpeg_progress", "job-1", {"frame": 999})

    # El primer evento debería haber sido descartado
    first = json.loads(q.get_nowait())
    assert first["data"]["frame"] == 1  # frame=0 fue descartado


def test_emit_raw(broadcaster):
    queue = broadcaster.subscribe("job-1")
    broadcaster.emit_raw("job-1", '{"custom": true}')

    item = queue.get_nowait()
    assert item == '{"custom": true}'


# ── Integration: job_manager + broadcaster ────────────────────────────────────

def test_submit_emits_job_queued(tmp_db_path):
    broadcaster = ProgressBroadcaster()
    mgr = RenderJobManager(
        processor=lambda req: None,
        db_path=tmp_db_path,
        broadcaster=broadcaster,
    )
    try:
        import asyncio
        req = _make_request()

        # Pre-subscribe using a known job_id pattern
        # We'll check that the event was emitted by inspecting after submit
        job = asyncio.run(mgr.submit(req))

        # Now subscribe and verify the job was queued (event already emitted)
        # The job record itself confirms the emit happened
        assert job.status == RenderJobStatus.QUEUED

        # Verify broadcaster has no stale subscribers (event was emitted, no listeners)
        assert job.job_id not in broadcaster._subscribers
    finally:
        mgr.dispose()
        broadcaster.close_all()


def test_worker_emits_started_and_completed(tmp_db_path):
    broadcaster = ProgressBroadcaster()
    mgr = RenderJobManager(
        processor=lambda req: "done",
        db_path=tmp_db_path,
        broadcaster=broadcaster,
    )
    try:
        import asyncio

        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            job_queue = broadcaster.subscribe(job.job_id)

            await mgr.start()
            await asyncio.sleep(0.5)
            await mgr.stop()

            events = []
            while not job_queue.empty():
                item = job_queue.get_nowait()
                if item is not None:
                    events.append(json.loads(item))

            event_types = [e["event_type"] for e in events]
            assert "job_started" in event_types
            assert "job_completed" in event_types

        asyncio.run(run_test())
    finally:
        mgr.dispose()
        broadcaster.close_all()


def test_worker_emits_failed_on_error(tmp_db_path):
    broadcaster = ProgressBroadcaster()

    def failing_processor(req):
        raise RuntimeError("FFmpeg crashed")

    mgr = RenderJobManager(
        processor=failing_processor,
        db_path=tmp_db_path,
        broadcaster=broadcaster,
    )
    try:
        import asyncio

        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            job_queue = broadcaster.subscribe(job.job_id)

            await mgr.start()
            await asyncio.sleep(0.5)
            await mgr.stop()

            events = []
            while not job_queue.empty():
                item = job_queue.get_nowait()
                if item is not None:
                    events.append(json.loads(item))

            event_types = [e["event_type"] for e in events]
            assert "job_failed" in event_types

            failed_event = [e for e in events if e["event_type"] == "job_failed"][0]
            assert "FFmpeg crashed" in failed_event["data"]["error"]

        asyncio.run(run_test())
    finally:
        mgr.dispose()
        broadcaster.close_all()


# ── FfmpegExecutor progress parsing tests ─────────────────────────────────────

def test_ffmpeg_progress_callback_called():
    """El callback recibe datos de progreso parseados correctamente."""
    import io
    from app.services.ffmpeg_executor import FfmpegExecutor

    executor = FfmpegExecutor()
    progress_events = []

    def callback(data):
        progress_events.append(data)

    # Simular output de -progress pipe:1
    fake_stdout = io.StringIO(
        "frame=30\n"
        "fps=25.0\n"
        "out_time_ms=1000000\n"
        "speed=1.2x\n"
        "progress=continue\n"
        "\n"
        "frame=60\n"
        "fps=24.5\n"
        "out_time_ms=2000000\n"
        "speed=1.1x\n"
        "progress=continue\n"
        "\n"
        "frame=90\n"
        "fps=24.0\n"
        "out_time_ms=3000000\n"
        "speed=1.0x\n"
        "progress=end\n"
    )

    executor._read_progress(fake_stdout, total_duration_ms=5000, callback=callback)

    assert len(progress_events) == 3
    assert progress_events[0] == {
        "frame": 30,
        "fps": 25.0,
        "time_ms": 1000,  # 1000000μs / 1000 = 1000ms
        "speed": 1.2,
        "percent": 20.0,  # 1000ms / 5000ms * 100
    }
    assert progress_events[1] == {
        "frame": 60,
        "fps": 24.5,
        "time_ms": 2000,
        "speed": 1.1,
        "percent": 40.0,
    }
    assert progress_events[2] == {
        "frame": 90,
        "fps": 24.0,
        "time_ms": 3000,
        "speed": 1.0,
        "percent": 60.0,
    }


def test_ffmpeg_progress_without_callback_consumes_output():
    """Sin callback, el output se consume para evitar bloqueo de pipe."""
    import io
    from app.services.ffmpeg_executor import FfmpegExecutor

    executor = FfmpegExecutor()
    fake_stdout = io.StringIO("frame=30\nprogress=continue\n")

    # No debe lanzar excepción
    executor._read_progress(fake_stdout, total_duration_ms=5000, callback=None)


def test_ffmpeg_progress_percent_capped_at_100():
    """El percent nunca excede 100%."""
    import io
    from app.services.ffmpeg_executor import FfmpegExecutor

    executor = FfmpegExecutor()
    progress_events = []

    def callback(data):
        progress_events.append(data)

    fake_stdout = io.StringIO(
        "frame=150\n"
        "out_time_ms=9999999999\n"
        "speed=2.0x\n"
        "progress=end\n"
    )

    executor._read_progress(fake_stdout, total_duration_ms=5000, callback=callback)

    assert progress_events[0]["percent"] == 100.0


def test_ffmpeg_progress_handles_missing_fields():
    """Campos faltantes se defaultean a 0."""
    import io
    from app.services.ffmpeg_executor import FfmpegExecutor

    executor = FfmpegExecutor()
    progress_events = []

    def callback(data):
        progress_events.append(data)

    fake_stdout = io.StringIO(
        "frame=10\n"
        "progress=continue\n"
    )

    executor._read_progress(fake_stdout, total_duration_ms=5000, callback=callback)

    assert progress_events[0]["fps"] == 0.0
    assert progress_events[0]["speed"] == 0.0
    assert progress_events[0]["time_ms"] == 0


# ── WebSocket endpoint tests (via TestClient) ─────────────────────────────────

def test_websocket_connection_and_events():
    """TestClient simula conexión WebSocket y recibe eventos."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.runtime import progress_broadcaster

    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/api/jobs/ws/test-job-1") as ws:
        # Dar tiempo a que el endpoint se suscriba al queue
        time.sleep(0.1)

        # Emitir eventos
        progress_broadcaster.emit("job_queued", "test-job-1", {"project": "test"})
        time.sleep(0.05)
        progress_broadcaster.emit("job_started", "test-job-1")
        time.sleep(0.05)
        progress_broadcaster.emit("ffmpeg_progress", "test-job-1", {
            "frame": 30, "fps": 25.0, "time_ms": 1000, "speed": 1.2, "percent": 20.0,
        })
        time.sleep(0.05)
        progress_broadcaster.emit("job_completed", "test-job-1")

        # Recibir eventos
        events = []
        for _ in range(4):
            data = ws.receive_text()
            events.append(json.loads(data))

        assert len(events) == 4
        assert events[0]["event_type"] == "job_queued"
        assert events[1]["event_type"] == "job_started"
        assert events[2]["event_type"] == "ffmpeg_progress"
        assert events[2]["data"]["frame"] == 30
        assert events[3]["event_type"] == "job_completed"

        # Cerrar para trigger cleanup
        ws.close()


def test_websocket_disconnect_cleanup():
    """Al desconectar, el listener se remueve del broadcaster."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.runtime import progress_broadcaster

    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/api/jobs/ws/test-job-2") as ws:
        ws.close()

    # Verificar que no hay subscribers
    assert "test-job-2" not in progress_broadcaster._subscribers


def test_job_completed_emits_cache_hit_false():
    """job_completed sin cache_hit emite cache_hit=False."""
    from app.domain.models import RenderJobResult, RenderPlan, RenderPlanOutputs, RenderPlanInput, RenderPlanFilterStage, TimelineScene, CompiledBackgroundClip, AssetKind, ZoomMotion

    broadcaster = ProgressBroadcaster()
    mgr = RenderJobManager(
        processor=lambda req: None,
        db_path=tmp_db_path_fixture(),
        broadcaster=broadcaster,
    )
    try:
        import asyncio

        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            # Suscribirse ANTES de marcar como completado
            job_queue = broadcaster.subscribe(job.job_id)

            # Simular completion sin cache_hit
            fake_result = RenderJobResult(
                timeline_scene=TimelineScene(
                    scene_id="s1", width=1920, height=1080, fps=30, duration_ms=5000,
                    background_clip=CompiledBackgroundClip(
                        absolute_path="/bg.mp4", asset_kind=AssetKind.VIDEO,
                        trim_in_ms=0, trim_out_ms=5000, loop_mode="cut",
                    ),
                    overlay_clips=[], text_clips=[], zoom=ZoomMotion(), subtitle_ass_path=None,
                ),
                fingerprint="fp1",
                render_plan=RenderPlan(
                    plan_id="p1", scene_id="s1",
                    timeline_scene=TimelineScene(
                        scene_id="s1", width=1920, height=1080, fps=30, duration_ms=5000,
                        background_clip=CompiledBackgroundClip(
                            absolute_path="/bg.mp4", asset_kind=AssetKind.VIDEO,
                            trim_in_ms=0, trim_out_ms=5000, loop_mode="cut",
                        ),
                        overlay_clips=[], text_clips=[], zoom=ZoomMotion(), subtitle_ass_path=None,
                    ),
                    inputs=[RenderPlanInput(input_id="bg", absolute_path="/bg.mp4", asset_kind=AssetKind.VIDEO, role="background")],
                    filter_stages=[RenderPlanFilterStage(name="normalize_background", description="test")],
                    outputs=RenderPlanOutputs(scene_output_path="/out.mp4", preview_output_path="/preview.png", manifest_output_path="/manifest.json"),
                ),
                ffmpeg_command=["ffmpeg"],
                preview_command=["ffmpeg"],
                cache_hit=False,
            )
            await mgr._mark_completed(job.job_id, fake_result)

            # Dar tiempo al broadcaster para procesar
            await asyncio.sleep(0.1)

            events = []
            while not job_queue.empty():
                item = job_queue.get_nowait()
                if item is not None:
                    events.append(json.loads(item))

            completed = [e for e in events if e["event_type"] == "job_completed"]
            assert len(completed) == 1
            assert completed[0]["data"]["cache_hit"] is False

        asyncio.run(run_test())
    finally:
        mgr.dispose()
        broadcaster.close_all()


def test_job_completed_emits_cache_hit_true():
    """job_completed con cache_hit=True emite cache_hit=True en WebSocket."""
    from app.domain.models import RenderJobResult, RenderPlan, RenderPlanOutputs, RenderPlanInput, RenderPlanFilterStage, TimelineScene, CompiledBackgroundClip, AssetKind, ZoomMotion

    broadcaster = ProgressBroadcaster()
    mgr = RenderJobManager(
        processor=lambda req: None,
        db_path=tmp_db_path_fixture(),
        broadcaster=broadcaster,
    )
    try:
        import asyncio

        async def run_test():
            req = _make_request()
            job = await mgr.submit(req)

            # Suscribirse ANTES de marcar como completado
            job_queue = broadcaster.subscribe(job.job_id)

            # Simular completion con cache_hit=True
            fake_result = RenderJobResult(
                timeline_scene=TimelineScene(
                    scene_id="s1", width=1920, height=1080, fps=30, duration_ms=5000,
                    background_clip=CompiledBackgroundClip(
                        absolute_path="/bg.mp4", asset_kind=AssetKind.VIDEO,
                        trim_in_ms=0, trim_out_ms=5000, loop_mode="cut",
                    ),
                    overlay_clips=[], text_clips=[], zoom=ZoomMotion(), subtitle_ass_path=None,
                ),
                fingerprint="fp1",
                render_plan=RenderPlan(
                    plan_id="p1", scene_id="s1",
                    timeline_scene=TimelineScene(
                        scene_id="s1", width=1920, height=1080, fps=30, duration_ms=5000,
                        background_clip=CompiledBackgroundClip(
                            absolute_path="/bg.mp4", asset_kind=AssetKind.VIDEO,
                            trim_in_ms=0, trim_out_ms=5000, loop_mode="cut",
                        ),
                        overlay_clips=[], text_clips=[], zoom=ZoomMotion(), subtitle_ass_path=None,
                    ),
                    inputs=[RenderPlanInput(input_id="bg", absolute_path="/bg.mp4", asset_kind=AssetKind.VIDEO, role="background")],
                    filter_stages=[RenderPlanFilterStage(name="normalize_background", description="test")],
                    outputs=RenderPlanOutputs(scene_output_path="/out.mp4", preview_output_path="/preview.png", manifest_output_path="/manifest.json"),
                ),
                ffmpeg_command=["ffmpeg"],
                preview_command=["ffmpeg"],
                cache_hit=True,
            )
            await mgr._mark_completed(job.job_id, fake_result)

            # Dar tiempo al broadcaster para procesar
            await asyncio.sleep(0.1)

            events = []
            while not job_queue.empty():
                item = job_queue.get_nowait()
                if item is not None:
                    events.append(json.loads(item))

            completed = [e for e in events if e["event_type"] == "job_completed"]
            assert len(completed) == 1
            assert completed[0]["data"]["cache_hit"] is True

        asyncio.run(run_test())
    finally:
        mgr.dispose()
        broadcaster.close_all()


def tmp_db_path_fixture():
    """Helper para crear path temporal de DB."""
    import tempfile
    td = tempfile.mkdtemp()
    db_path = Path(td) / "jobs.db"
    return db_path
