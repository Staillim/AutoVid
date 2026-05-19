from fastapi import APIRouter

from app.domain.models import RuntimeHealthReport
from app.runtime import app_settings
from app.services.runtime_diagnostics import RuntimeDiagnosticsService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=RuntimeHealthReport)
def healthcheck() -> RuntimeHealthReport:
    return RuntimeDiagnosticsService(app_settings).build_report()
