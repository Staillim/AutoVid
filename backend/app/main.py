from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.projects import router as projects_router
from app.api.routes.runtime import router as runtime_router
from app.runtime import render_job_manager, progress_broadcaster


@asynccontextmanager
async def lifespan(_: FastAPI):
    await render_job_manager.start()
    try:
        yield
    finally:
        await render_job_manager.stop()
        render_job_manager.dispose()
        progress_broadcaster.close_all()


def create_app() -> FastAPI:
    app = FastAPI(
        title="NodeAV Backend",
        version="0.1.0",
        description="API local para validacion de proyectos y compilacion de escenas.",
        lifespan=lifespan,
    )
    from fastapi import APIRouter
    api_router = APIRouter(prefix="/api")
    from app.api.routes.assets import router as assets_router
    api_router.include_router(health_router)
    api_router.include_router(projects_router)
    api_router.include_router(jobs_router)
    api_router.include_router(runtime_router)
    api_router.include_router(assets_router)
    app.include_router(api_router)
    return app


app = create_app()
