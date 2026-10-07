from app.jobs import queue as queue_module
from app.models import Job, JobStatus, JobType


async def _setup(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    eid = r.json()["id"]
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments", json={"shot_number": 1, "duration": 3}
    )
    fid = r.json()["id"]
    await client.patch(
        f"/api/v1/fragments/{fid}",
        json={"status": "generated", "video_path": f"{pid}/videos/{fid}.mp4"},
    )
    return pid, eid


async def test_assemble_reenqueues_orphan_queued_job(client, db_session, monkeypatch):
    calls: list[tuple] = []

    async def fake_enqueue(queue, func_name, job_id):
        calls.append((queue, func_name, job_id))

    monkeypatch.setattr(queue_module, "enqueue", fake_enqueue)

    pid, eid = await _setup(client)
    orphan = Job(
        type=JobType.episode_assembly,
        status=JobStatus.queued,
        payload={"episode_id": eid},
        project_id=pid,
    )
    db_session.add(orphan)
    await db_session.commit()

    r = await client.post(f"/api/v1/episodes/{eid}/assemble")
    assert r.status_code == 202
    assert r.json()["id"] == orphan.id
    assert ("assembly", "run_episode_assembly", orphan.id) in calls


async def test_assemble_requires_all_fragments(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    eid = r.json()["id"]
    await client.post(f"/api/v1/episodes/{eid}/fragments", json={"shot_number": 1})

    r = await client.post(f"/api/v1/episodes/{eid}/assemble")
    assert r.status_code == 400
