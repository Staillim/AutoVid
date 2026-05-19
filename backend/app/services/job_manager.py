from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

from app.domain.models import RenderJobRecord, RenderJobStatus, RenderJobResult, RenderSceneRequest


# ── ORM ───────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class JobRow(Base):
    """Fila de la tabla `jobs` en la base de datos de jobs."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    scene_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_record(self) -> RenderJobRecord:
        result = None
        if self.result_json is not None:
            result = RenderJobResult.model_validate(json.loads(self.result_json))
        return RenderJobRecord(
            job_id=self.job_id,
            project_id=self.project_id,
            scene_id=self.scene_id,
            status=RenderJobStatus(self.status),
            created_at=self.created_at,
            updated_at=self.updated_at,
            error_message=self.error_message,
            result=result,
        )


# ── errores ───────────────────────────────────────────────────────────────────

class JobPersistenceError(Exception):
    """Error al persistir o recuperar un job."""


# ── servicio ──────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class _QueuedJob:
    job_id: str
    request: RenderSceneRequest


class RenderJobManager:
    """Cola local de jobs con persistencia en SQLite.

    Los jobs se almacenan en una tabla SQLite para sobrevivir reinicios
    del backend. El worker loop sigue usando asyncio.Queue para la
    ejecución asíncrona, pero cada transición de estado se persiste.
    """

    def __init__(
        self,
        *,
        processor: Callable[[RenderSceneRequest], object],
        db_path: str | Path,
    ) -> None:
        self._processor = processor
        self._queue: asyncio.Queue[_QueuedJob] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._worker_task: asyncio.Task | None = None

        self._db_path = Path(db_path)
        self._engine = create_engine(f"sqlite:///{self._db_path}", echo=False)
        Base.metadata.create_all(self._engine)

    def dispose(self) -> None:
        """Libera todas las conexiones del engine (necesario en Windows)."""
        self._engine.dispose()

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop(), name="nodeav-render-worker")

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._worker_task
        self._worker_task = None

    async def submit(self, request: RenderSceneRequest) -> RenderJobRecord:
        timestamp = self._utcnow()
        job = RenderJobRecord(
            job_id=str(self._uuid4()),
            project_id=request.project.project_id,
            scene_id=request.scene_id,
            status=RenderJobStatus.QUEUED,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._persist_job(job)
        await self._queue.put(_QueuedJob(job_id=job.job_id, request=request))
        return job

    async def get(self, job_id: str) -> RenderJobRecord | None:
        return self._get_job(job_id)

    async def list(self) -> list[RenderJobRecord]:
        return self._list_jobs()

    async def _worker_loop(self) -> None:
        while True:
            queued = await self._queue.get()
            await self._mark_running(queued.job_id)
            try:
                result = await asyncio.to_thread(self._processor, queued.request)
            except Exception as exc:  # noqa: BLE001
                await self._mark_failed(queued.job_id, str(exc))
            else:
                await self._mark_completed(queued.job_id, result)
            finally:
                self._queue.task_done()

    # ── persistencia ──────────────────────────────────────────────────────

    def _persist_job(self, job: RenderJobRecord) -> None:
        result_json = None
        if job.result is not None:
            result_json = job.result.model_dump_json()

        row = JobRow(
            job_id=job.job_id,
            project_id=job.project_id,
            scene_id=job.scene_id,
            status=job.status.value,
            created_at=job.created_at,
            updated_at=job.updated_at,
            error_message=job.error_message,
            result_json=result_json,
        )
        with Session(self._engine) as session:
            session.merge(row)
            session.commit()

    def _get_job(self, job_id: str) -> RenderJobRecord | None:
        with Session(self._engine) as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return None
            return row.to_record()

    def _list_jobs(self) -> list[RenderJobRecord]:
        with Session(self._engine) as session:
            stmt = select(JobRow).order_by(JobRow.created_at.desc())
            rows = session.execute(stmt).scalars().all()
            return [row.to_record() for row in rows]

    async def _mark_running(self, job_id: str) -> None:
        self._update_job_fields(job_id, {
            "status": RenderJobStatus.RUNNING,
            "updated_at": self._utcnow(),
        })

    async def _mark_completed(self, job_id: str, result: object) -> None:
        render_result = None
        if isinstance(result, RenderJobResult):
            render_result = result
        self._update_job_fields(job_id, {
            "status": RenderJobStatus.COMPLETED,
            "updated_at": self._utcnow(),
            "result": render_result,
            "error_message": None,
        })

    async def _mark_failed(self, job_id: str, error_message: str) -> None:
        self._update_job_fields(job_id, {
            "status": RenderJobStatus.FAILED,
            "updated_at": self._utcnow(),
            "error_message": error_message,
        })

    def _update_job_fields(self, job_id: str, fields: dict) -> None:
        with Session(self._engine) as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise JobPersistenceError(f"job not found for update: {job_id}")
            for key, value in fields.items():
                if key == "result" and value is not None:
                    row.result_json = value.model_dump_json()
                elif key == "status" and isinstance(value, RenderJobStatus):
                    row.status = value.value
                else:
                    setattr(row, key, value)
            session.commit()

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _uuid4(self) -> str:
        from uuid import uuid4
        return str(uuid4())
