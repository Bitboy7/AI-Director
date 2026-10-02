from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.db import get_session_factory
from app.models import Job, JobStatus


async def _get_job(job_id: int) -> Job | None:
    async with get_session_factory()() as session:
        return await session.get(Job, job_id)


async def mark_running(job_id: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.running
            job.progress = 0
            job.error = None
            job.updated_at = datetime.now()
            await session.commit()


async def mark_progress(job_id: int, progress: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.progress = max(0, min(progress, 100))
            job.updated_at = datetime.now()
            await session.commit()


async def mark_succeeded(job_id: int, result: dict) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.succeeded
            job.progress = 100
            job.result = result
            job.error = None
            job.updated_at = datetime.now()
            await session.commit()


async def mark_failed(job_id: int, error: str) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error = error
            job.updated_at = datetime.now()
            await session.commit()


async def mark_cancelled(job_id: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.cancelled
            job.updated_at = datetime.now()
            await session.commit()


async def is_cancelled(job_id: int) -> bool:
    job = await _get_job(job_id)
    return job is not None and job.status == JobStatus.cancelled


async def reclaim_stale(ctx: dict) -> None:
    cutoff = datetime.now() - timedelta(minutes=5)
    async with get_session_factory()() as session:
        await session.execute(
            update(Job)
            .where(Job.status == JobStatus.running, Job.updated_at < cutoff)
            .values(status=JobStatus.queued)
        )
        await session.commit()
