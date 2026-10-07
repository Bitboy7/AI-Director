import json
import tempfile
from pathlib import Path
from uuid import uuid4

from app.jobs import queue as queue_module
from app.jobs.tasks import run_storyboard_gen, run_video_gen
from app.providers import register_provider
from app.providers.base import VideoTaskStatus


class _FakeImage:
    async def generate(self, prompt, model, style, aspect, count):
        path = Path(tempfile.mkdtemp(prefix="ref-")) / f"{uuid4().hex}.png"
        path.write_bytes(b"ref-img")
        return [path]


class _FakeLLM:
    async def complete(self, system, user, json_mode=False):
        return json.dumps(
            {
                "panels": [
                    {"title": "Inicio", "start_seconds": 0, "end_seconds": 4, "prompt": "wide shot @Kai"},
                    {"title": "Cierre", "start_seconds": 4, "end_seconds": 10, "prompt": "close up"},
                ]
            }
        )


class _FakeVideo:
    def __init__(self):
        self.payloads = []

    async def submit(self, payload):
        self.payloads.append(payload)
        return "task-1"

    async def poll(self, task_id):
        return VideoTaskStatus(state="succeeded", video_url="http://example/v.mp4")

    async def download(self, url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"video")
        return dest


async def _setup(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}",
        json={
            "settings": {
                "image_provider": "fake_img",
                "video_provider": "fake_video",
                "llm_provider": "fake_llm",
            }
        },
    )
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    eid = r.json()["id"]
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments",
        json={"shot_number": 1, "duration": 10, "prompt_video": "Kai camina"},
    )
    fid = r.json()["id"]
    return pid, eid, fid


async def test_generate_fragment_reference_image(client):
    register_provider("image", "fake_img", lambda credentials=None: _FakeImage())
    _pid, eid, fid = await _setup(client)

    r = await client.post(f"/api/v1/fragments/{fid}/reference-images/generate")
    assert r.status_code == 200
    assert r.json()["origin"] == "generated"

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    assert len(r.json()[0]["reference_images"]) == 1


async def test_video_gen_keeps_history_and_selection(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    fake_video = _FakeVideo()
    register_provider("video", "fake_video", lambda credentials=None, model=None: fake_video)
    _pid, eid, fid = await _setup(client)

    for _ in range(2):
        r = await client.post(f"/api/v1/fragments/{fid}/generate")
        await run_video_gen({"redis": fake_redis}, r.json()["id"])

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    fragment = r.json()[0]
    assert len(fragment["videos"]) == 2
    assert fragment["video_path"] == fragment["videos"][0]["path"]

    older = fragment["videos"][1]
    r = await client.post(f"/api/v1/fragments/{fid}/videos/{older['id']}/select")
    assert r.status_code == 200
    assert r.json()["video_path"] == older["path"]


async def test_video_gen_uses_storyboard_prompt_and_reference(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    register_provider("image", "fake_img", lambda credentials=None: _FakeImage())
    register_provider("llm", "fake_llm", lambda credentials=None, model=None: _FakeLLM())
    fake_video = _FakeVideo()
    register_provider("video", "fake_video", lambda credentials=None, model=None: fake_video)
    pid, _eid, fid = await _setup(client)

    r = await client.post(f"/api/v1/projects/{pid}/storyboards", json={})
    await run_storyboard_gen({"redis": fake_redis}, r.json()["id"])

    r = await client.post(f"/api/v1/fragments/{fid}/reference-images/generate")
    assert r.status_code == 200

    r = await client.post(f"/api/v1/fragments/{fid}/generate")
    assert r.status_code == 202
    await run_video_gen({"redis": fake_redis}, r.json()["id"])

    assert fake_video.payloads
    payload = fake_video.payloads[0]
    assert "wide shot @Kai" in payload.prompt
    assert "close up" in payload.prompt
    assert len(payload.reference_images) >= 1
