import asyncio
import sys

from arq.worker import Worker

from app.jobs.settings import QUEUES, WorkerSettings


async def _run(queue: str) -> None:
    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup,
        queue_name=queue,
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
    )
    await worker.async_run()


def main() -> None:
    queue = sys.argv[1] if len(sys.argv) > 1 else "default"
    if queue not in QUEUES:
        raise SystemExit(f"cola desconocida: {queue}. Opciones: {', '.join(QUEUES)}")
    asyncio.run(_run(queue))


if __name__ == "__main__":
    main()
