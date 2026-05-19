from app.core.settings import AppSettings
from app.services.job_manager import RenderJobManager
from app.services.render_pipeline import RenderPipeline
from app.services.asset_library import AssetLibrary

app_settings = AppSettings.from_env()
render_pipeline = RenderPipeline(settings=app_settings)

render_job_manager = RenderJobManager(
    processor=render_pipeline.execute_scene_render,
    db_path=app_settings.jobs_db_path,
)

asset_library = AssetLibrary(
    db_path=app_settings.library_db_path,
    ffprobe_path=app_settings.resolve_ffprobe_path()
)
