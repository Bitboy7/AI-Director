import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import SessionDep
from app.jobs import queue as queue_module
from app.models import Job, JobStatus
from app.schemas import JobRead

router = APIRouter(prefix="/api/v1")

_TERMINAL = {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}


async def get_job_or_404(session: SessionDep, job_id: int) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/jobs", response_model=list[JobRead])
async def list_jobs(session: SessionDep, project_id: int | None = Query(default=None)):
    query = select(Job).order_by(Job.id.desc())
    if project_id is not None:
        query = query.where(Job.project_id == project_id)
    result = await session.execute(query)
    return list(result.scalars())


@router.get("/jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: int, session: SessionDep):
    return await get_job_or_404(session, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobRead)
async def cancel_job(job_id: int, session: SessionDep):
    job = await get_job_or_404(session, job_id)
    if job.status in (JobStatus.queued, JobStatus.running):
        try:
            redis = await queue_module.get_redis()
            await redis.abort_job(str(job_id))
        except Exception:
            pass
        job.status = JobStatus.cancelled
        job.updated_at = datetime.now()
        await session.commit()
    return job


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: int, session: SessionDep):
    async def generate():
        while True:
            job = await session.get(Job, job_id)
            if job is None:
                yield "event: error\ndata: {\"error\": \"job not found\"}\n\n"
                return
            payload = JobRead.model_validate(job).model_dump(mode="json")
            yield f"data: {json.dumps(payload)}\n\n"
            if job.status in _TERMINAL:
                return
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")
