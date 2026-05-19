from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from app.domain.models import RenderJobRecord, RenderJobStatus, RenderSceneRequest


@dataclass(slots=True)
class _QueuedJob:
    job_id: str
    request: RenderSceneRequest


class RenderJobManager:
    def __init__(
        self,
        *,
        processor: Callable[[RenderSceneRequest], object],
    ) -> None:
        self._processor = processor
        self._queue: asyncio.Queue[_QueuedJob] = asyncio.Queue()
        self._jobs: dict[str, RenderJobRecord] = {}
        self._worker_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

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
            job_id=str(uuid4()),
            project_id=request.project.project_id,
            scene_id=request.scene_id,
            status=RenderJobStatus.QUEUED,
            created_at=timestamp,
            updated_at=timestamp,
        )
        async with self._lock:
            self._jobs[job.job_id] = job
        await self._queue.put(_QueuedJob(job_id=job.job_id, request=request))
        return job

    async def get(self, job_id: str) -> RenderJobRecord | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def list(self) -> list[RenderJobRecord]:
        async with self._lock:
            return sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)

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

    async def _mark_running(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": RenderJobStatus.RUNNING,
                    "updated_at": self._utcnow(),
                }
            )

    async def _mark_completed(self, job_id: str, result: object) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": RenderJobStatus.COMPLETED,
                    "updated_at": self._utcnow(),
                    "result": result,
                    "error_message": None,
                }
            )

    async def _mark_failed(self, job_id: str, error_message: str) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": RenderJobStatus.FAILED,
                    "updated_at": self._utcnow(),
                    "error_message": error_message,
                }
            )

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat()
