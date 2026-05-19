from pathlib import Path
from unittest.mock import patch

from app.core.settings import AppSettings
from app.services.runtime_diagnostics import RuntimeDiagnosticsService


class _CompletedProcess:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_runtime_diagnostics_reports_ready_environment() -> None:
    settings = AppSettings(
        runtime_root=str(Path.cwd()),
        default_cache_root=str(Path.cwd() / ".cache"),
        default_logs_root=str(Path.cwd() / ".logs"),
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
    )

    with (
        patch("app.services.runtime_diagnostics.shutil.which") as which_mock,
        patch("app.services.runtime_diagnostics.os.access", return_value=True),
        patch("app.services.runtime_diagnostics.subprocess.run") as run_mock,
    ):
        which_mock.side_effect = lambda binary: f"C:/bin/{binary}.exe"
        run_mock.return_value = _CompletedProcess(
            returncode=0,
            stdout="ffmpeg version 7.0\nbuilt for tests",
        )

        report = RuntimeDiagnosticsService(settings).build_report()

    assert report.status == "ok"
    assert report.ready_for_render is True
    assert report.ffmpeg.available is True
    assert report.ffprobe.executable is True
    assert report.issues == []


def test_runtime_diagnostics_reports_missing_binaries() -> None:
    settings = AppSettings(
        runtime_root=str(Path.cwd()),
        default_cache_root=str(Path.cwd() / ".cache"),
        default_logs_root=str(Path.cwd() / ".logs"),
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
    )

    with (
        patch("app.services.runtime_diagnostics.shutil.which", return_value=None),
        patch("app.services.runtime_diagnostics.os.access", return_value=True),
    ):
        report = RuntimeDiagnosticsService(settings).build_report()

    assert report.status == "degraded"
    assert report.ready_for_render is False
    assert "ffmpeg binary is not available" in report.issues
    assert "ffprobe binary is not available" in report.issues
