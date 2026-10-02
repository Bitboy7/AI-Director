from sqlalchemy import select

from app.jobs import queue as queue_module
from app.models import Job, JobStatus, JobType


async def _setup_episode_with_fragments(client, n=3):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    eid = r.json()["id"]
    for i in range(1, n + 1):
        r = await client.post(
            f"/api/v1/episodes/{eid}/fragments",
            json={"shot_number": i, "duration": 3, "time_place": "calle"},
        )
        assert r.status_code == 200
    return pid, eid


async def test_episode_generate_creates_jobs(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    pid, eid = await _setup_episode_with_fragments(client)

    r = await client.post(f"/api/v1/episodes/{eid}/generate", json={})
    assert r.status_code == 202
    body = r.json()
    assert len(body["video_job_ids"]) == 3
    assert body["assembly_job_id"] is not None

    db_session.expire_all()
    video_jobs = (
        await db_session.execute(select(Job).where(Job.type == JobType.video_gen))
    ).scalars().all()
    assembly_jobs = (
        await db_session.execute(
            select(Job).where(Job.type == JobType.episode_assembly)
        )
    ).scalars().all()
    assert len(video_jobs) == 3
    assert all(j.status == JobStatus.queued for j in video_jobs)
    assert len(assembly_jobs) == 1
