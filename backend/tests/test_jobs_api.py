from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.jobs import queue as queue_module
from app.jobs.state import reclaim_stale
from app.jobs.tasks import run_ping
from app.models import Job, JobStatus, JobType


async def test_enqueue_and_run_ping(db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    job = Job(type=JobType.tts, status=JobStatus.queued, payload={})
    db_session.add(job)
    await db_session.commit()
    job_id = job.id

    await queue_module.enqueue("default", "run_ping", job_id)

    await run_ping({"redis": fake_redis}, job_id)

    db_session.expire_all()
    j = await db_session.get(Job, job_id)
    assert j.status == JobStatus.succeeded
    assert j.result == {"pong": True}


async def test_cancel_job(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    job = Job(type=JobType.tts, status=JobStatus.queued, payload={})
    db_session.add(job)
    await db_session.commit()

    r = await client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


async def test_enqueue_redis_down_raises(db_session, monkeypatch):
    def _boom():
        raise queue_module.QueueUnavailableError("redis caído")

    monkeypatch.setattr(queue_module, "get_redis", _boom)
    job = Job(type=JobType.tts, status=JobStatus.queued, payload={})
    db_session.add(job)
    await db_session.commit()
    with pytest.raises(queue_module.QueueUnavailableError):
        await queue_module.enqueue("default", "run_ping", job.id)


async def test_reclaim_stale_running(db_session):
    job = Job(type=JobType.tts, status=JobStatus.running, payload={})
    db_session.add(job)
    await db_session.commit()
    job_id = job.id
    job.updated_at = datetime.now() - timedelta(minutes=10)
    await db_session.commit()

    await reclaim_stale({})

    db_session.expire_all()
    j = await db_session.get(Job, job_id)
    assert j.status == JobStatus.queued
