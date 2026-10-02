from arq.connections import RedisSettings

from app.config import get_settings
from app.jobs.state import reclaim_stale
from app.jobs.tasks import run_ping

QUEUES = ("default", "video", "assembly")


class WorkerSettings:
    functions = [run_ping]
    on_startup = reclaim_stale
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 2
    job_timeout = 3600
