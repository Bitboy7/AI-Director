from app.jobs import queue as queue_module
from app.jobs.tasks import run_script_gen
from app.models import Episode, Fragment, Job, JobStatus, Resource
from app.schemas.script import (
    ScriptCharacter,
    ScriptDialogue,
    ScriptDraft,
    ScriptEpisode,
    ScriptScene,
    ScriptShot,
)
from app.services import scripting


def _draft() -> ScriptDraft:
    shots = []
    for i in range(1, 10):
        shots.append(
            ScriptShot(
                shot_number=i,
                time_place=f"Calle {i}, noche",
                cast=["Kai"] if i == 1 else [],
                action="Kai camina y observa la ciudad",
                dialogues=[ScriptDialogue(character="Kai", text="Hola")] if i == 1 else [],
            )
        )
    return ScriptDraft(
        synopsis="Un hacker descubre un secreto en la ciudad",
        characters=[ScriptCharacter(name="Kai", description="joven hacker", tags=["hero"])],
        scenes=[ScriptScene(name="Calle", description="calle nocturna neón", tags=[])],
        props=[],
        episodes=[ScriptEpisode(number=1, title="Piloto", shots=shots)],
    )


async def test_generate_script_job_end_to_end(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)

    async def fake_generate(provider, req, retries):
        return _draft()

    monkeypatch.setattr(scripting, "generate_script_draft", fake_generate)

    r = await client.post("/api/v1/projects", json={"name": "Neon Rebellion"})
    pid = r.json()["id"]

    r = await client.post(
        f"/api/v1/projects/{pid}/generate-script",
        json={
            "synopsis": "Un hacker descubre un secreto",
            "video_style": "cyberpunk",
            "num_episodes": 1,
            "episode_duration_seconds": 90,
        },
    )
    assert r.status_code == 202
    job_id = r.json()["id"]

    await run_script_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded
    assert job.result["fragments"] == 9

    r = await client.get(f"/api/v1/projects/{pid}/episodes")
    episodes = r.json()
    assert len(episodes) == 1
    assert len(episodes[0]["fragments"]) == 9
    assert episodes[0]["fragments"][0]["dialogue_lines"][0]["text"] == "Hola"

    r = await client.get(f"/api/v1/projects/{pid}/resources")
    resources = r.json()
    assert len(resources) == 2
    kai = next(res for res in resources if res["name"] == "Kai")
    assert kai["variants"][0]["name"] == "Base Appearance"


async def test_generate_script_job_invalid_json_fails(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)

    async def boom(provider, req, retries):
        raise scripting.ScriptValidationError("JSON roto del LLM")

    monkeypatch.setattr(scripting, "generate_script_draft", boom)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/generate-script", json={"synopsis": "x", "num_episodes": 1}
    )
    job_id = r.json()["id"]

    await run_script_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.failed
    assert "JSON roto" in job.error


async def test_generate_script_redis_down_returns_503(client, monkeypatch):
    def _boom():
        raise queue_module.QueueUnavailableError("redis caído")

    monkeypatch.setattr(queue_module, "get_redis", _boom)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/generate-script", json={"synopsis": "x", "num_episodes": 1}
    )
    assert r.status_code == 503
    assert "queue_unavailable" in r.json()["detail"]
    r = await client.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200
