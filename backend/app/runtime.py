from app.core.settings import AppSettings
from app.services.job_manager import RenderJobManager
from app.services.render_pipeline import RenderPipeline
from app.services.asset_library import AssetLibrary
from app.services.progress_broadcaster import ProgressBroadcaster

app_settings = AppSettings.from_env()
render_pipeline = RenderPipeline(settings=app_settings)

progress_broadcaster = ProgressBroadcaster()

render_job_manager = RenderJobManager(
    processor=render_pipeline.execute_scene_render,
    db_path=app_settings.jobs_db_path,
    broadcaster=progress_broadcaster,
)

asset_library = AssetLibrary(
    db_path=app_settings.library_db_path,
    ffprobe_path=app_settings.resolve_ffprobe_path()
)
