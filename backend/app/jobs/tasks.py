import asyncio

from app.jobs.state import mark_succeeded


async def run_ping(ctx: dict, job_id: int) -> None:
    await asyncio.sleep(0.1)
    await mark_succeeded(job_id, {"pong": True})
