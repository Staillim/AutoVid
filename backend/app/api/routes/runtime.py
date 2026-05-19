from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime import app_settings

router = APIRouter(prefix="/runtime", tags=["runtime"])


class RuntimeSettingsResponse(BaseModel):
    runtime_root: str
    default_cache_root: str
    default_logs_root: str
    ffmpeg_path: str
    ffprobe_path: str
    font_root: str | None = None


@router.get("/settings", response_model=RuntimeSettingsResponse)
def get_runtime_settings() -> RuntimeSettingsResponse:
    return RuntimeSettingsResponse(**app_settings.as_runtime_dict())
