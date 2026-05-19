from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
import uuid

from app.domain.models import RenderJobRecord, RenderSceneRequest, RenderNodeRequest, ProjectModel, LibraryBinding
from app.runtime import render_job_manager, progress_broadcaster

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[RenderJobRecord])
async def list_jobs() -> list[RenderJobRecord]:
    return await render_job_manager.list()


@router.get("/{job_id}", response_model=RenderJobRecord)
async def get_job(job_id: str) -> RenderJobRecord:
    job = await render_job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/render-scene", response_model=RenderJobRecord, status_code=202)
async def render_scene_job(request: RenderSceneRequest) -> RenderJobRecord:
    return await render_job_manager.submit(request)


@router.post("/render-node", response_model=RenderJobRecord, status_code=202)
async def render_node_job(request: RenderNodeRequest) -> RenderJobRecord:
    mock_project = ProjectModel(
        project_id=f"mock-{uuid.uuid4().hex[:8]}",
        schema_version="1.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        name="Node Preview",
        settings=request.settings,
        library_binding=LibraryBinding(library_id="local"),
        nodes=[request.node],
        scene_order=[request.node.id]
    )

    scene_req = RenderSceneRequest(
        project=mock_project,
        scene_id=request.node.id,
        assets=request.assets,
        cache_root=request.cache_root,
        ffmpeg_path=request.ffmpeg_path
    )
    return await render_job_manager.submit(scene_req)


@router.websocket("/ws/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str) -> None:
    """WebSocket para recibir eventos de progreso de un job.

    Eventos emitidos:
    - job_queued: job creado y en cola
    - job_started: worker comenzó a procesar
    - ffmpeg_progress: progreso del render (frame, fps, time_ms, speed, percent)
    - job_completed: render finalizado exitosamente
    - job_failed: error durante el render

    El cliente recibe mensajes JSON. Para cerrar, enviar un mensaje con
    {"type": "close"} o simplemente desconectar.
    """
    await websocket.accept()

    queue = progress_broadcaster.subscribe(job_id)

    try:
        while True:
            # Leer del broadcaster o del cliente (ping/pong)
            item = await queue.get()

            if item is None:
                # Sentinel: job terminado, cerrar conexión
                break

            await websocket.send_text(item)

    except WebSocketDisconnect:
        pass
    finally:
        progress_broadcaster.unsubscribe(job_id, queue)
