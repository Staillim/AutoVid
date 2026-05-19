from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from app.core.settings import AppSettings
from app.domain.models import (
    RuntimeBinaryCheck,
    RuntimeDirectoryCheck,
    RuntimeHealthReport,
)


class RuntimeDiagnosticsService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def build_report(self) -> RuntimeHealthReport:
        cache_root = self._check_directory("cache_root", self.settings.default_cache_root)
        logs_root = self._check_directory("logs_root", self.settings.default_logs_root)
        ffmpeg = self._check_binary("ffmpeg", self.settings.resolve_ffmpeg_path())
        ffprobe = self._check_binary("ffprobe", self.settings.resolve_ffprobe_path())

        issues: list[str] = []
        if not cache_root.writable:
            issues.append("cache root is not writable")
        if not logs_root.writable:
            issues.append("logs root is not writable")
        if not ffmpeg.available:
            issues.append("ffmpeg binary is not available")
        elif not ffmpeg.executable:
            issues.append("ffmpeg binary is not executable")
        if not ffprobe.available:
            issues.append("ffprobe binary is not available")
        elif not ffprobe.executable:
            issues.append("ffprobe binary is not executable")

        ready_for_render = (
            cache_root.writable
            and logs_root.writable
            and ffmpeg.available
            and ffmpeg.executable
            and ffprobe.available
            and ffprobe.executable
        )
        status = "ok" if ready_for_render else "degraded"

        return RuntimeHealthReport(
            status=status,
            ready_for_render=ready_for_render,
            runtime_root=str(Path(self.settings.runtime_root).resolve()),
            cache_root=cache_root,
            logs_root=logs_root,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            issues=issues,
        )

    def _check_directory(self, label: str, path_value: str) -> RuntimeDirectoryCheck:
        path = Path(path_value).resolve()
        exists = path.exists()
        writable = self._is_directory_writable(path)
        return RuntimeDirectoryCheck(
            label=label,
            path=str(path),
            exists=exists,
            writable=writable,
        )

    def _check_binary(self, label: str, configured_path: str) -> RuntimeBinaryCheck:
        resolved_path = self._resolve_binary_path(configured_path)
        if resolved_path is None:
            return RuntimeBinaryCheck(
                label=label,
                configured_path=configured_path,
                available=False,
                executable=False,
                error_message="binary could not be resolved from configured path",
            )

        candidate = Path(resolved_path)
        executable = self._probe_binary(candidate)
        version = self._probe_version(candidate) if executable else None
        error_message = None if executable else "binary exists but version probe failed"

        return RuntimeBinaryCheck(
            label=label,
            configured_path=configured_path,
            resolved_path=str(candidate),
            available=True,
            executable=executable,
            version=version,
            error_message=error_message,
        )

    def _resolve_binary_path(self, configured_path: str) -> str | None:
        candidate = Path(configured_path)
        if candidate.is_absolute():
            return str(candidate) if candidate.exists() else None
        resolved = shutil.which(configured_path)
        return resolved

    def _probe_binary(self, path: Path) -> bool:
        try:
            completed = subprocess.run(
                [str(path), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    def _probe_version(self, path: Path) -> str | None:
        try:
            completed = subprocess.run(
                [str(path), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return None

        if completed.returncode != 0:
            return None
        first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
        return first_line or None

    def _is_directory_writable(self, path: Path) -> bool:
        target = path if path.exists() else self._nearest_existing_parent(path)
        if target is None:
            return False
        return os.access(target, os.W_OK)

    def _nearest_existing_parent(self, path: Path) -> Path | None:
        current = path
        while not current.exists():
            if current.parent == current:
                return None
            current = current.parent
        return current
