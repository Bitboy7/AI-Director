import asyncio
import sys

import redis.exceptions
from arq.worker import Worker

from app.jobs.settings import QUEUES, WorkerSettings


def build_worker(queue: str) -> Worker:
    return Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup,
        queue_name=queue,
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
    )


async def run_worker_with_retries(queue: str, retry_delay: float = 5.0) -> None:
    while True:
        worker = build_worker(queue)
        try:
            await worker.async_run()
            return
        except (redis.exceptions.RedisError, OSError) as exc:
            print(
                f"[worker:{queue}] Redis no disponible ({exc}); reintentando en {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)


def main() -> None:
    queue = sys.argv[1] if len(sys.argv) > 1 else "default"
    if queue not in QUEUES:
        raise SystemExit(f"cola desconocida: {queue}. Opciones: {', '.join(QUEUES)}")
    asyncio.run(run_worker_with_retries(queue))


if __name__ == "__main__":
    main()
