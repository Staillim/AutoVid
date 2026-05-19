"""AssetLibrary — índice local de assets usando SQLite + SQLAlchemy 2.x."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from sqlalchemy import String, Integer, Float, Boolean, Text, create_engine, select, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

from app.domain.models import AssetKind, AssetRecord


# ── ORM ───────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class AssetRow(Base):
    """Fila de la tabla `assets` en la biblioteca local."""

    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    absolute_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    imported_at: Mapped[str] = mapped_column(String, nullable=False)

    def to_record(self) -> AssetRecord:
        return AssetRecord(
            asset_id=self.asset_id,
            kind=AssetKind(self.kind),
            absolute_path=self.absolute_path,
            content_sha256=self.content_sha256,
            size_bytes=self.size_bytes,
            duration_ms=self.duration_ms,
            width=self.width,
            height=self.height,
            fps=self.fps,
        )


# ── errores ───────────────────────────────────────────────────────────────────

class AssetLibraryError(Exception):
    """Error base de AssetLibrary."""


class AssetNotFoundError(AssetLibraryError):
    """El asset_id solicitado no existe en la biblioteca."""


class AssetImportError(AssetLibraryError):
    """No se pudo importar el archivo como asset."""


# ── servicio ──────────────────────────────────────────────────────────────────

class AssetLibrary:
    """Biblioteca local de assets respaldada por SQLite.

    Cada biblioteca tiene su propio archivo `library.db`.
    Se usa SQLAlchemy 2.x con sesiones síncronas (adecuado para sidecar local).
    """

    def __init__(self, db_path: str | Path, ffprobe_path: str = "ffprobe") -> None:
        self.db_path = Path(db_path)
        self.ffprobe_path = ffprobe_path
        self._engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self._engine)

    def dispose(self) -> None:
        """Libera todas las conexiones del engine (necesario en Windows antes de borrar el db)."""
        self._engine.dispose()

    # ---------- importar ----------

    def import_asset(self, file_path: str | Path) -> AssetRecord:
        """Importa un archivo a la biblioteca.

        - Extrae metadata con ffprobe (duración, resolución, fps).
        - Calcula SHA-256 del contenido.
        - Detecta el AssetKind por extensión.
        - Guarda en SQLite.

        Returns:
            El AssetRecord importado (o el existente si ya estaba registrado).

        Raises:
            AssetImportError: si el archivo no existe o no es un tipo reconocido.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise AssetImportError(f"archivo no encontrado: {path}")

        kind = _detect_kind(path)
        if kind is None:
            raise AssetImportError(
                f"extensión no reconocida: {path.suffix!r}. "
                "Tipos soportados: video (.mp4 .mov .mkv .avi .webm), "
                "imagen (.jpg .jpeg .png .webp .gif .bmp), "
                "audio (.mp3 .wav .aac .ogg .flac .m4a)"
            )

        sha256 = _sha256_file(path)

        # Si ya existe (mismo hash y path), retornar el existente
        with Session(self._engine) as session:
            existing = session.execute(
                select(AssetRow).where(AssetRow.content_sha256 == sha256)
            ).scalar_one_or_none()
            if existing is not None:
                return existing.to_record()

        metadata = self._probe_metadata(path, kind)

        row = AssetRow(
            asset_id=str(uuid4()),
            kind=kind.value,
            absolute_path=str(path),
            content_sha256=sha256,
            size_bytes=path.stat().st_size,
            duration_ms=metadata.get("duration_ms"),
            width=metadata.get("width"),
            height=metadata.get("height"),
            fps=metadata.get("fps"),
            imported_at=datetime.now(timezone.utc).isoformat(),
        )

        with Session(self._engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_record()

    # ---------- consultar ----------

    def get(self, asset_id: str) -> AssetRecord:
        """Retorna un asset por su ID.

        Raises:
            AssetNotFoundError: si no existe.
        """
        with Session(self._engine) as session:
            row = session.get(AssetRow, asset_id)
            if row is None:
                raise AssetNotFoundError(f"asset no encontrado: {asset_id!r}")
            return row.to_record()

    def list(self, kind: AssetKind | None = None) -> list[AssetRecord]:
        """Lista todos los assets, opcionalmente filtrados por tipo."""
        with Session(self._engine) as session:
            stmt = select(AssetRow)
            if kind is not None:
                stmt = stmt.where(AssetRow.kind == kind.value)
            rows = session.execute(stmt).scalars().all()
            return [row.to_record() for row in rows]

    def search(self, query: str) -> list[AssetRecord]:
        """Busca assets cuya ruta contenga el texto dado (case-insensitive)."""
        with Session(self._engine) as session:
            rows = session.execute(
                select(AssetRow).where(AssetRow.absolute_path.ilike(f"%{query}%"))
            ).scalars().all()
            return [row.to_record() for row in rows]

    def remove(self, asset_id: str) -> bool:
        """Elimina un asset del índice (no borra el archivo físico).

        Returns:
            True si se eliminó, False si no existía.
        """
        with Session(self._engine) as session:
            result = session.execute(
                delete(AssetRow).where(AssetRow.asset_id == asset_id)
            )
            session.commit()
            return result.rowcount > 0

    def count(self) -> int:
        """Retorna el número total de assets registrados."""
        with Session(self._engine) as session:
            from sqlalchemy import func
            return session.execute(
                select(func.count()).select_from(AssetRow)
            ).scalar_one()

    # ---------- metadata ----------

    def _probe_metadata(self, path: Path, kind: AssetKind) -> dict:
        """Ejecuta ffprobe para extraer metadata del archivo."""
        if kind == AssetKind.AUDIO:
            return self._probe_audio(path)
        return self._probe_av(path)

    def _probe_av(self, path: Path) -> dict:
        try:
            completed = subprocess.run(
                [
                    self.ffprobe_path,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_streams",
                    "-show_format",
                    str(path),
                ],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if completed.returncode != 0:
                return {}
            data = json.loads(completed.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            return {}

        result: dict = {}
        # Duración desde format
        fmt = data.get("format", {})
        duration_sec = float(fmt.get("duration", 0) or 0)
        if duration_sec > 0:
            result["duration_ms"] = int(duration_sec * 1000)

        # Resolución y fps desde el primer stream de video
        for stream in data.get("streams", []):
            if stream.get("codec_type") != "video":
                continue
            result["width"] = stream.get("width")
            result["height"] = stream.get("height")
            # fps como fracción "num/den"
            r_frame_rate = stream.get("r_frame_rate", "")
            if "/" in r_frame_rate:
                num, den = r_frame_rate.split("/")
                try:
                    fps_val = float(num) / float(den)
                    if fps_val > 0:
                        result["fps"] = round(fps_val, 3)
                except (ValueError, ZeroDivisionError):
                    pass
            break

        return result

    def _probe_audio(self, path: Path) -> dict:
        try:
            completed = subprocess.run(
                [
                    self.ffprobe_path,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    str(path),
                ],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if completed.returncode != 0:
                return {}
            data = json.loads(completed.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            return {}

        fmt = data.get("format", {})
        duration_sec = float(fmt.get("duration", 0) or 0)
        if duration_sec > 0:
            return {"duration_ms": int(duration_sec * 1000)}
        return {}


# ── helpers ───────────────────────────────────────────────────────────────────

_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_AUDIO_EXTS = {".mp3", ".wav", ".aac", ".ogg", ".flac", ".m4a"}


def _detect_kind(path: Path) -> AssetKind | None:
    ext = path.suffix.lower()
    if ext in _VIDEO_EXTS:
        return AssetKind.VIDEO
    if ext in _IMAGE_EXTS:
        return AssetKind.IMAGE
    if ext in _AUDIO_EXTS:
        return AssetKind.AUDIO
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
