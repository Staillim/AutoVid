from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    app_name: str = "NodeAV"
    runtime_root: str = Field(default_factory=lambda: str(Path.cwd()))
    default_cache_root: str = Field(default_factory=lambda: str(Path.cwd() / ".cache"))
    default_logs_root: str = Field(default_factory=lambda: str(Path.cwd() / ".logs"))
    library_db_path: str = Field(default_factory=lambda: str(Path.cwd() / "library.db"))
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    font_root: str | None = None

    @classmethod
    def from_env(cls) -> "AppSettings":
        cwd = Path.cwd()
        runtime_root = Path(os.getenv("NODEAV_RUNTIME_ROOT", str(cwd)))
        default_cache_root = Path(
            os.getenv("NODEAV_CACHE_ROOT", str(runtime_root / ".cache"))
        )
        default_logs_root = Path(
            os.getenv("NODEAV_LOGS_ROOT", str(runtime_root / ".logs"))
        )
        library_db_path = Path(
            os.getenv("NODEAV_LIBRARY_DB", str(runtime_root / "library.db"))
        )
        ffmpeg_path = os.getenv("NODEAV_FFMPEG_PATH", "ffmpeg")
        ffprobe_path = os.getenv("NODEAV_FFPROBE_PATH", "ffprobe")
        font_root = os.getenv("NODEAV_FONT_ROOT")

        return cls(
            runtime_root=str(runtime_root),
            default_cache_root=str(default_cache_root),
            default_logs_root=str(default_logs_root),
            library_db_path=str(library_db_path),
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            font_root=font_root,
        )

    def resolve_ffmpeg_path(self, override: str | None = None) -> str:
        return self._normalize_path_like(override or self.ffmpeg_path)

    def resolve_ffprobe_path(self, override: str | None = None) -> str:
        return self._normalize_path_like(override or self.ffprobe_path)

    def resolve_cache_root(self, *, override: str | None = None, project_id: str) -> str:
        base = Path(override or self.default_cache_root)
        return str((base / project_id).resolve())

    def resolve_logs_root(self) -> str:
        return str(Path(self.default_logs_root).resolve())

    def as_runtime_dict(self) -> dict[str, str | None]:
        return {
            "runtime_root": str(Path(self.runtime_root).resolve()),
            "default_cache_root": str(Path(self.default_cache_root).resolve()),
            "default_logs_root": str(Path(self.default_logs_root).resolve()),
            "ffmpeg_path": self.resolve_ffmpeg_path(),
            "ffprobe_path": self.resolve_ffprobe_path(),
            "font_root": self._normalize_optional_path(self.font_root),
        }

    def _normalize_path_like(self, value: str) -> str:
        candidate = Path(value)
        if candidate.is_absolute():
            return str(candidate)
        return value

    def _normalize_optional_path(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._normalize_path_like(value)
