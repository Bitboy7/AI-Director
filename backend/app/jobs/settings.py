from arq.connections import RedisSettings

from app.config import get_settings
from app.jobs.state import reclaim_stale
from app.jobs.tasks import (
    run_episode_assembly,
    run_ping,
    run_resource_gen,
    run_resource_image_gen,
    run_script_gen,
    run_storyboard_gen,
    run_video_gen,
)

QUEUES = ("default", "video", "assembly")


class WorkerSettings:
    functions = [
        run_ping,
        run_script_gen,
        run_resource_gen,
        run_resource_image_gen,
        run_storyboard_gen,
        run_video_gen,
        run_episode_assembly,
    ]
    on_startup = reclaim_stale
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 2
    job_timeout = 3600
