import shutil
import tempfile
from pathlib import Path

from app.jobs import queue as queue_module
from app.jobs.tasks import run_resource_gen, run_script_gen, run_video_gen
from app.models import Fragment, Job, JobStatus, ResourceType
from app.providers import get_provider, register_provider
from app.providers.base import VideoTaskStatus
from app.schemas.script import (
    ResourcesDraft,
    ScriptCharacter,
    ScriptDialogue,
    ScriptDraft,
    ScriptEpisode,
    ScriptShot,
)
from app.services import scripting


def test_get_provider_passes_kwargs_to_factory():
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return object()

    register_provider("llm", "fakekw", factory)
    result = get_provider("llm", "fakekw", credentials={"api_key": "x"})
    assert captured["credentials"] == {"api_key": "x"}
    assert result is not None


def _draft() -> ScriptDraft:
    return ScriptDraft(
        synopsis="Un hacker descubre un secreto",
        characters=[ScriptCharacter(name="Kai", description="hacker", tags=["hero"])],
        scenes=[],
        props=[],
        episodes=[
            ScriptEpisode(
                number=1,
                title="Piloto",
                shots=[
                    ScriptShot(
                        shot_number=1,
                        time_place="Calle",
                        cast=["Kai"],
                        action="camina",
                        dialogues=[ScriptDialogue(character="Kai", text="Hola")],
                    )
                ],
            )
        ],
    )


async def test_script_gen_uses_project_llm_provider(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    received = {}
    sentinel = object()
    register_provider("llm", "fake_llm", lambda credentials=None, model=None: sentinel)

    async def fake_generate(provider, req, retries):
        received["provider"] = provider
        return _draft()

    monkeypatch.setattr(scripting, "generate_script_draft", fake_generate)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(f"/api/v1/projects/{pid}", json={"settings": {"llm_provider": "fake_llm"}})
    r = await client.post(
        f"/api/v1/projects/{pid}/generate-script", json={"synopsis": "x", "num_episodes": 1}
    )
    job_id = r.json()["id"]

    await run_script_gen({"redis": fake_redis}, job_id)

    assert received["provider"] is sentinel
    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded


async def test_resource_gen_uses_project_llm_provider(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    received = {}
    sentinel = object()
    register_provider("llm", "fake_llm2", lambda credentials=None, model=None: sentinel)

    async def fake_generate(provider, context, retries):
        received["provider"] = provider
        return ResourcesDraft(
            resources=[
                {
                    "type": ResourceType.character,
                    "name": "Mira",
                    "description": "aliada",
                    "variants": [],
                }
            ]
        )

    monkeypatch.setattr(scripting, "generate_resources_draft", fake_generate)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(f"/api/v1/projects/{pid}", json={"settings": {"llm_provider": "fake_llm2"}})
    r = await client.post(f"/api/v1/projects/{pid}/generate-resources", json={})
    job_id = r.json()["id"]

    await run_resource_gen({"redis": fake_redis}, job_id)

    assert received["provider"] is sentinel
    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded


class _FakeVideo:
    def __init__(self):
        self.received = []
        self._file = Path(tempfile.mkdtemp(prefix="fake-video-")) / "out.mp4"
        self._file.write_bytes(b"fake-mp4")

    async def submit(self, payload):
        self.received.append(payload)
        return "task-1"

    async def poll(self, task_id):
        return VideoTaskStatus(state="succeeded", video_url=str(self._file))

    async def download(self, url, dest):
        shutil.copyfile(url, dest)
        return dest


async def test_video_gen_uses_project_video_provider(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    fake = _FakeVideo()
    register_provider("video", "fake_video", lambda credentials=None, model=None: fake)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}", json={"settings": {"video_provider": "fake_video"}}
    )
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "E1"})
    eid = r.json()["id"]
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments",
        json={"shot_number": 1, "time_place": "calle", "prompt_video": "plano de prueba", "duration": 5},
    )
    fid = r.json()["id"]
    r = await client.post(f"/api/v1/fragments/{fid}/generate")
    job_id = r.json()["id"]

    await run_video_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded
    assert len(fake.received) == 1
    assert fake.received[0].prompt == "plano de prueba"
    fragment = await db_session.get(Fragment, fid)
    assert fragment.video_path is not None
    assert fragment.video_path.startswith(f"{pid}/videos/{fid}_")


async def test_video_gen_passes_settings_model_to_provider(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    received = {}
    fake = _FakeVideo()

    def factory(credentials=None, model=None):
        received["model"] = model
        return fake

    register_provider("video", "fake_video_model", factory)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}",
        json={"settings": {"video_provider": "fake_video_model", "video_model": "kling-pro"}},
    )
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "E1"})
    eid = r.json()["id"]
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments",
        json={"shot_number": 1, "time_place": "calle", "prompt_video": "plano", "duration": 5},
    )
    fid = r.json()["id"]
    r = await client.post(f"/api/v1/fragments/{fid}/generate")
    job_id = r.json()["id"]

    await run_video_gen({"redis": fake_redis}, job_id)

    assert received["model"] == "kling-pro"
    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded
