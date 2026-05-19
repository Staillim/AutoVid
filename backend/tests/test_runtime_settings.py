from pathlib import Path

from app.core.settings import AppSettings


def test_app_settings_resolve_cache_root_by_project() -> None:
    settings = AppSettings(
        runtime_root="C:/nodeav",
        default_cache_root="C:/nodeav/.cache",
        default_logs_root="C:/nodeav/.logs",
        ffmpeg_path="C:/bin/ffmpeg.exe",
        ffprobe_path="C:/bin/ffprobe.exe",
        font_root="C:/fonts",
    )

    cache_root = settings.resolve_cache_root(project_id="project-001")

    assert cache_root.endswith(str(Path("nodeav/.cache/project-001")))


def test_app_settings_allow_request_override() -> None:
    settings = AppSettings(
        runtime_root="C:/nodeav",
        default_cache_root="C:/nodeav/.cache",
        default_logs_root="C:/nodeav/.logs",
        ffmpeg_path="C:/bin/ffmpeg.exe",
        ffprobe_path="C:/bin/ffprobe.exe",
    )

    cache_root = settings.resolve_cache_root(
        override="D:/custom-cache",
        project_id="project-999",
    )
    ffmpeg_path = settings.resolve_ffmpeg_path("D:/portable/ffmpeg.exe")

    assert cache_root.endswith(str(Path("custom-cache/project-999")))
    assert Path(ffmpeg_path) == Path("D:/portable/ffmpeg.exe")


def test_runtime_dict_exposes_resolved_fields() -> None:
    settings = AppSettings(
        runtime_root="C:/nodeav",
        default_cache_root="C:/nodeav/.cache",
        default_logs_root="C:/nodeav/.logs",
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        font_root=None,
    )

    runtime_dict = settings.as_runtime_dict()

    assert runtime_dict["runtime_root"] is not None
    assert runtime_dict["default_cache_root"] is not None
    assert runtime_dict["ffmpeg_path"] == "ffmpeg"
