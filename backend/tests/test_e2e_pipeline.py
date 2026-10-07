from sqlalchemy import select

from app.config import get_settings
from app.jobs import queue as queue_module
from app.jobs.tasks import run_episode_assembly, run_script_gen, run_video_gen
from app.models import Job, JobStatus
from app.schemas.script import (
    ScriptCharacter,
    ScriptDialogue,
    ScriptDraft,
    ScriptEpisode,
    ScriptScene,
    ScriptShot,
)
from app.services import scripting


def _draft_two_shots() -> ScriptDraft:
    shots = [
        ScriptShot(
            shot_number=1,
            time_place="Azotea, noche",
            cast=["Kai"],
            action="Kai mira la ciudad",
            dialogues=[ScriptDialogue(character="Kai", text="La ciudad nunca duerme.")],
        ),
        ScriptShot(
            shot_number=2,
            time_place="Calle, noche",
            cast=["Kai"],
            action="Kai salta al vacío",
            dialogues=[ScriptDialogue(character="Kai", text="Es mi momento.")],
        ),
    ]
    return ScriptDraft(
        synopsis="Un hacker contra el sistema",
        characters=[ScriptCharacter(name="Kai", description="hacker", tags=["hero"])],
        scenes=[ScriptScene(name="Azotea", description="neón", tags=[])],
        props=[],
        episodes=[ScriptEpisode(number=1, title="Piloto", shots=shots)],
    )


async def test_full_pipeline_e2e(client, fake_redis, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)

    async def fake_generate(provider, req, retries):
        return _draft_two_shots()

    monkeypatch.setattr(scripting, "generate_script_draft", fake_generate)

    # 1. proyecto + guion
    r = await client.post(
        "/api/v1/projects", json={"name": "Neon Rebellion", "video_style": "cyberpunk"}
    )
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/generate-script",
        json={"synopsis": "un hacker", "num_episodes": 1},
    )
    script_job_id = r.json()["id"]
    await run_script_gen({"redis": fake_redis}, script_job_id)

    # confirmar el guion materializa episodios/fragmentos/recursos
    r = await client.post(f"/api/v1/projects/{pid}/confirm-script")
    assert r.status_code == 200

    r = await client.get(f"/api/v1/projects/{pid}/episodes")
    episodes = r.json()
    assert len(episodes) == 1
    assert len(episodes[0]["fragments"]) == 2
    eid = episodes[0]["id"]

    # 2. generar episodio (mock de video real con ffmpeg)
    r = await client.post(f"/api/v1/episodes/{eid}/generate", json={})
    assert r.status_code == 202
    body = r.json()
    for video_job_id in body["video_job_ids"]:
        await run_video_gen({"redis": fake_redis}, video_job_id)

    # 3. ensamblaje con TTS fake
    await run_episode_assembly({"redis": fake_redis}, body["assembly_job_id"])

    db_session.expire_all()
    jobs = (
        await db_session.execute(select(Job))
    ).scalars().all()

    storage = get_settings().storage_dir.resolve()
    final = storage / str(pid) / "episodes" / str(eid) / "final.mp4"
    assert final.exists() and final.stat().st_size > 1000

    r = await client.get(f"/api/v1/episodes/{eid}/final")
    assert r.status_code == 200

    r = await client.get(f"/api/v1/episodes/{eid}/final?download=1")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")

    r = await client.get(f"/api/v1/projects/{pid}/cover")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")

    assembly_job = next(j for j in jobs if j.id == body["assembly_job_id"])
    assert assembly_job.status == JobStatus.succeeded
