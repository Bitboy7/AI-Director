from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings


class QueueUnavailableError(Exception):
    pass


_redis_pool: ArqRedis | None = None


async def get_redis() -> ArqRedis:
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        try:
            _redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        except Exception as exc:
            raise QueueUnavailableError(f"redis no disponible: {exc}") from exc
    return _redis_pool


async def enqueue(queue: str, func_name: str, job_id: int) -> None:
    try:
        redis = await get_redis()
        await redis.enqueue_job(func_name, job_id, _queue_name=queue, _job_id=str(job_id))
    except (ConnectionError, OSError, QueueUnavailableError) as exc:
        if isinstance(exc, QueueUnavailableError):
            raise
        raise QueueUnavailableError(f"redis no disponible: {exc}") from exc
