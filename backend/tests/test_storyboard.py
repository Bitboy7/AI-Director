import json

from app.jobs import queue as queue_module
from app.jobs.tasks import run_storyboard_gen
from app.models import Job, JobStatus
from app.providers import register_provider


class _FakeLLM:
    def __init__(self):
        self.calls = 0

    async def complete(self, system, user, json_mode=False):
        self.calls += 1
        return json.dumps(
            {
                "panels": [
                    {
                        "title": "Inicio",
                        "start_seconds": 0,
                        "end_seconds": 4,
                        "prompt": "wide establishing shot, neon rain",
                    },
                    {
                        "title": "Cierre",
                        "start_seconds": 4,
                        "end_seconds": 10,
                        "prompt": "close up, dramatic lighting",
                    },
                ]
            }
        )


async def _setup(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}", json={"settings": {"llm_provider": "fake_llm"}}
    )
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "Piloto"})
    eid = r.json()["id"]
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments",
        json={
            "shot_number": 1,
            "time_place": "Calle, noche",
            "cast": [{"name": "Kai", "variant_id": None}],
            "prompt_video": "Kai camina bajo la lluvia",
            "duration": 10,
        },
    )
    fid = r.json()["id"]
    return pid, eid, fid


async def test_storyboard_job_creates_panels(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    fake = _FakeLLM()
    register_provider("llm", "fake_llm", lambda credentials=None, model=None: fake)
    pid, eid, _fid = await _setup(client)

    r = await client.post(f"/api/v1/projects/{pid}/storyboards", json={})
    assert r.status_code == 202
    job_id = r.json()["id"]

    await run_storyboard_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded
    assert job.result["panels"] == 2

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    fragments = r.json()
    assert fragments[0]["storyboard"][0]["title"] == "Inicio"
    assert fragments[0]["storyboard"][0]["start_seconds"] == 0
    assert fragments[0]["storyboard"][1]["end_seconds"] == 10


async def test_storyboard_job_is_idempotent(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    register_provider("llm", "fake_llm", lambda credentials=None, model=None: _FakeLLM())
    pid, eid, _fid = await _setup(client)

    for _ in range(2):
        r = await client.post(f"/api/v1/projects/{pid}/storyboards", json={})
        await run_storyboard_gen({"redis": fake_redis}, r.json()["id"])

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    assert len(r.json()[0]["storyboard"]) == 2


async def test_create_storyboard_panel_and_limit(client):
    _pid, _eid, fid = await _setup(client)

    for index in range(4):
        r = await client.post(
            f"/api/v1/fragments/{fid}/storyboard-panels",
            json={
                "title": f"Panel {index}",
                "start_seconds": index * 3,
                "end_seconds": index * 3 + 3,
                "prompt": "prompt",
            },
        )
        assert r.status_code == 200

    r = await client.post(
        f"/api/v1/fragments/{fid}/storyboard-panels",
        json={"title": "Extra", "start_seconds": 12, "end_seconds": 15, "prompt": "x"},
    )
    assert r.status_code == 400
    assert "4" in r.json()["detail"]


async def test_edit_and_delete_storyboard_panel(client):
    _pid, eid, fid = await _setup(client)
    r = await client.post(
        f"/api/v1/fragments/{fid}/storyboard-panels",
        json={"title": "Inicio", "start_seconds": 0, "end_seconds": 3, "prompt": "a"},
    )
    panel_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/storyboard-panels/{panel_id}",
        json={"title": "Nuevo", "start_seconds": 1, "end_seconds": 5},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Nuevo"
    assert r.json()["start_seconds"] == 1

    r = await client.delete(f"/api/v1/storyboard-panels/{panel_id}")
    assert r.status_code == 204

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    assert r.json()[0]["storyboard"] == []


async def test_update_storyboard_panel(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    register_provider("llm", "fake_llm", lambda credentials=None, model=None: _FakeLLM())
    pid, eid, _fid = await _setup(client)
    r = await client.post(f"/api/v1/projects/{pid}/storyboards", json={})
    await run_storyboard_gen({"redis": fake_redis}, r.json()["id"])

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    panel_id = r.json()[0]["storyboard"][0]["id"]

    r = await client.patch(
        f"/api/v1/storyboard-panels/{panel_id}",
        json={"prompt": "plano general épico", "end_seconds": 5},
    )
    assert r.status_code == 200
    assert r.json()["prompt"] == "plano general épico"
    assert r.json()["end_seconds"] == 5
