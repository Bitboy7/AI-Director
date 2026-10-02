import subprocess
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.jobs import queue as queue_module
from app.jobs.tasks import run_episode_assembly, run_script_gen, run_video_gen
from app.models import Job, JobStatus
from app.providers.base import TTSResult
from app.schemas.script import (
    ScriptCharacter,
    ScriptDialogue,
    ScriptDraft,
    ScriptEpisode,
    ScriptScene,
    ScriptShot,
)
from app.services import assembly as assembly_module
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


class FakeTTS:
    def __init__(self, wav: Path):
        self.wav = wav

    async def synthesize(self, text: str, voice: str) -> TTSResult:
        return TTSResult(path=self.wav, duration_seconds=1.0)


async def test_full_pipeline_e2e(client, fake_redis, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)

    async def fake_generate(provider, req, retries):
        return _draft_two_shots()

    monkeypatch.setattr(scripting, "generate_script_draft", fake_generate)

    wav = tmp_path / "one.wav"
    subprocess.run(
        [
            get_settings().ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-ar",
            "16000",
            str(wav),
        ],
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(
        assembly_module, "get_provider", lambda kind, name=None: FakeTTS(wav)
    )

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
    srt = storage / str(pid) / "episodes" / str(eid) / "final.srt"
    assert final.exists() and final.stat().st_size > 1000
    assert srt.exists()
    content = srt.read_text(encoding="utf-8")
    assert "La ciudad nunca duerme." in content
    assert "Es mi momento." in content

    r = await client.get(f"/api/v1/episodes/{eid}/final")
    assert r.status_code == 200

    assembly_job = next(j for j in jobs if j.id == body["assembly_job_id"])
    assert assembly_job.status == JobStatus.succeeded
