from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.models import ProjectModel, ProjectSettings, RenderJobResult, RenderSceneRequest
from app.services.project_service import (
    ProjectNotFoundError,
    ProjectParseError,
    ProjectSaveError,
    ProjectService,
)
from app.services.render_compiler import RenderCompilerError
from app.services.render_pipeline import RenderPipeline

router = APIRouter(prefix="/projects", tags=["projects"])

_project_service = ProjectService()


class ValidateProjectResponse(BaseModel):
    project_id: str
    schema_version: str
    node_count: int
    enabled_node_count: int


class OpenProjectRequest(BaseModel):
    path: str


class SaveProjectRequest(BaseModel):
    project: ProjectModel
    path: str


class CreateProjectRequest(BaseModel):
    name: str
    library_id: str = "default-local-library"
    settings: ProjectSettings | None = None


class CompatibilityResponse(BaseModel):
    compatible: bool
    reason: str


@router.post("/validate", response_model=ValidateProjectResponse)
def validate_project(project: ProjectModel) -> ValidateProjectResponse:
    enabled_count = sum(1 for node in project.nodes if node.enabled)
    return ValidateProjectResponse(
        project_id=project.project_id,
        schema_version=project.schema_version,
        node_count=len(project.nodes),
        enabled_node_count=enabled_count,
    )


@router.post("/open", response_model=ProjectModel)
def open_project(payload: OpenProjectRequest) -> ProjectModel:
    """Abre un archivo .avproj desde disco y retorna el proyecto validado."""
    try:
        return _project_service.open(payload.path)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProjectParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/save", response_model=dict)
def save_project(payload: SaveProjectRequest) -> dict:
    """Guarda un ProjectModel en disco como archivo .avproj."""
    try:
        saved_path = _project_service.save(payload.project, payload.path)
        return {"saved": True, "path": str(saved_path)}
    except ProjectSaveError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/create", response_model=ProjectModel)
def create_project(payload: CreateProjectRequest) -> ProjectModel:
    """Crea un nuevo proyecto en memoria con valores iniciales."""
    return _project_service.create(
        name=payload.name,
        library_id=payload.library_id,
        settings=payload.settings,
    )


@router.post("/check-compatibility", response_model=CompatibilityResponse)
def check_compatibility(payload: OpenProjectRequest) -> CompatibilityResponse:
    """Verifica si un archivo .avproj es compatible con el schema actual."""
    ok, reason = _project_service.is_compatible(payload.path)
    return CompatibilityResponse(compatible=ok, reason=reason)


@router.post("/compile-scene", response_model=RenderJobResult)
def compile_scene(payload: RenderSceneRequest) -> RenderJobResult:
    try:
        return RenderPipeline().prepare_scene_render(payload)
    except RenderCompilerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
