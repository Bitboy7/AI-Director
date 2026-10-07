from sqlalchemy import select

from app.jobs import queue as queue_module
from app.models import Fragment, Job, JobStatus, JobType


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


async def _mark_fragments_generated(db_session, episode_id):
    fragments = (
        await db_session.execute(
            select(Fragment).where(Fragment.episode_id == episode_id)
        )
    ).scalars().all()
    for fragment in fragments:
        fragment.video_path = f"1/videos/{fragment.id}.mp4"
        fragment.status = "generated"
    await db_session.commit()


async def test_assemble_endpoint_creates_only_assembly_job(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    _pid, eid = await _setup_episode_with_fragments(client)
    await _mark_fragments_generated(db_session, eid)

    r = await client.post(f"/api/v1/episodes/{eid}/assemble", json={})
    assert r.status_code == 202
    assert r.json()["type"] == "episode_assembly"

    db_session.expire_all()
    video_jobs = (
        await db_session.execute(select(Job).where(Job.type == JobType.video_gen))
    ).scalars().all()
    assembly_jobs = (
        await db_session.execute(
            select(Job).where(Job.type == JobType.episode_assembly)
        )
    ).scalars().all()
    assert video_jobs == []
    assert len(assembly_jobs) == 1


async def test_assemble_endpoint_requires_generated_fragments(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    _pid, eid = await _setup_episode_with_fragments(client)

    r = await client.post(f"/api/v1/episodes/{eid}/assemble", json={})
    assert r.status_code == 400


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


async def test_episode_generate_dedupes_video_jobs(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    _pid, eid = await _setup_episode_with_fragments(client)

    r1 = await client.post(f"/api/v1/episodes/{eid}/generate", json={})
    r2 = await client.post(f"/api/v1/episodes/{eid}/generate", json={})
    assert r1.status_code == 202
    assert r2.status_code == 202

    db_session.expire_all()
    video_jobs = (
        await db_session.execute(select(Job).where(Job.type == JobType.video_gen))
    ).scalars().all()
    assert len(video_jobs) == 3


async def test_episode_generate_redis_down_midway_marks_all_failed(
    client, db_session, fake_redis, monkeypatch
):
    _pid, eid = await _setup_episode_with_fragments(client)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] >= 2:
            raise queue_module.QueueUnavailableError("boom")
        return fake_redis

    monkeypatch.setattr(queue_module, "get_redis", flaky)

    r = await client.post(f"/api/v1/episodes/{eid}/generate", json={})
    assert r.status_code == 503

    db_session.expire_all()
    video_jobs = (
        await db_session.execute(select(Job).where(Job.type == JobType.video_gen))
    ).scalars().all()
    assembly_jobs = (
        await db_session.execute(
            select(Job).where(Job.type == JobType.episode_assembly)
        )
    ).scalars().all()
    assert all(j.status == JobStatus.failed for j in video_jobs)
    assert all(j.status == JobStatus.failed for j in assembly_jobs)
