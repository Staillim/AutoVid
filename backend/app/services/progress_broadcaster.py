"""ProgressBroadcaster — pub/sub event bus para eventos de progreso de jobs.

Gestiona colas de WebSocket por job_id. Los emisores (job_manager) llaman
`emit()` con eventos estructurados; los listeners (endpoints WebSocket)
se suscriben con `subscribe()` y reciben eventos hasta que se desconectan.

Thread-safe: `emit()` puede llamarse desde cualquier thread (incluyendo
el thread de FFmpeg ejecutado via asyncio.to_thread). Internamente usa
`asyncio.run_coroutine_threadsafe` cuando se llama desde fuera del event
loop, y `put_nowait` directo cuando se llama desde dentro.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.domain.models import JobProgressEvent, JobProgressEventType


class ProgressBroadcaster:
    """Event bus pub/sub para progreso de jobs.

    Mantiene un mapa job_id → set de asyncio.Queue. Cada queue representa
    un listener WebSocket conectado. Cuando se emite un evento, se copia
    a todas las queues suscritas para ese job_id.

    Backpressure: cada queue tiene maxsize. Si está llena, se descarta
    el evento más antiguo antes de insertar el nuevo. Esto evita que
    un listener lento bloquee la ejecución de FFmpeg.
    """

    QUEUE_MAXSIZE = 64

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is not None:
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Registra un nuevo listener para un job_id.

        Returns:
            asyncio.Queue que recibirá eventos serializados como JSON.
            El último item será None (sentinel) indicando cierre del stream.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_MAXSIZE)
        self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        """Remueve un listener. Idempotente."""
        self._subscribers.get(job_id, set()).discard(queue)
        if job_id in self._subscribers and not self._subscribers[job_id]:
            del self._subscribers[job_id]

    def emit(self, event_type: JobProgressEventType, job_id: str, data: dict[str, Any] | None = None) -> None:
        """Emite un evento a todos los listeners suscritos a job_id.

        Thread-safe: puede llamarse desde cualquier thread.
        """
        event = JobProgressEvent(
            event_type=event_type,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data or {},
        )
        payload = event.model_dump_json()
        self._broadcast(job_id, payload)

    def emit_raw(self, job_id: str, payload: str) -> None:
        """Emite un payload JSON crudo a todos los listeners."""
        self._broadcast(job_id, payload)

    def close(self, job_id: str) -> None:
        """Envía sentinel a todos los listeners de un job_id y los remueve."""
        queues = self._subscribers.pop(job_id, set())
        for queue in queues:
            self._put(queue, None)

    def close_all(self) -> None:
        """Cierra todos los listeners activos."""
        for job_id in list(self._subscribers.keys()):
            self.close(job_id)

    # ── interno ───────────────────────────────────────────────────────────

    def _broadcast(self, job_id: str, payload: str) -> None:
        queues = self._subscribers.get(job_id, set()).copy()
        for queue in queues:
            self._put(queue, payload)

    def _put(self, queue: asyncio.Queue, item: Any) -> None:
        """Inserta en la queue de forma thread-safe."""
        current_loop = self.loop
        if current_loop is None:
            # Sin event loop (ej. tests síncronos): put directo
            self._sync_put(queue, item)
        elif current_loop.is_running():
            # Event loop corriendo: usar thread-safe
            try:
                asyncio.run_coroutine_threadsafe(
                    self._safe_put(queue, item),
                    current_loop,
                ).result(timeout=1.0)
            except Exception:
                pass
        else:
            # Loop existe pero no está corriendo: put directo
            self._sync_put(queue, item)

    def _sync_put(self, queue: asyncio.Queue, item: Any) -> None:
        """Inserta directamente (sin event loop)."""
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(item)

    async def _safe_put(self, queue: asyncio.Queue, item: Any) -> None:
        """Inserta de forma async con backpressure."""
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(item)
