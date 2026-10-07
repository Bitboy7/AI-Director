from pathlib import Path

from sqlalchemy import select

from app.jobs import tasks as tasks_module
from app.jobs.tasks import run_video_gen
from app.models import Fragment, FragmentVideo
from app.providers.base import VideoTaskStatus
from app.services.usage import model_pricing


class _FakeVideoProvider:
    def __init__(self, source: Path, captured: list) -> None:
        self._source = source
        self._captured = captured

    async def submit(self, payload) -> str:
        self._captured.append(payload)
        return "task-1"

    async def poll(self, task_id: str) -> VideoTaskStatus:
        return VideoTaskStatus(state="succeeded", video_url=str(self._source))

    async def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"video-bytes" * 300)
        return dest


async def _make_fragment(client) -> tuple[int, int]:
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    eid = r.json()["id"]
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments",
        json={"shot_number": 1, "duration": 10, "time_place": "calle"},
    )
    return pid, r.json()["id"]


async def test_fragment_settings_roundtrip(client):
    _pid, fid = await _make_fragment(client)

    r = await client.patch(
        f"/api/v1/fragments/{fid}",
        json={
            "video_provider": "omni",
            "video_model": "gemini-omni-1.1-flash",
            "resolution": "720p",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["video_provider"] == "omni"
    assert body["video_model"] == "gemini-omni-1.1-flash"
    assert body["resolution"] == "720p"
    assert body["cost_usd"] == 0.0


async def test_video_gen_uses_fragment_overrides_and_records_cost(
    client, db_session, tmp_path, monkeypatch
):
    _pid, fid = await _make_fragment(client)
    await client.patch(
        f"/api/v1/fragments/{fid}",
        json={
            "video_provider": "omni",
            "video_model": "gemini-omni-1.1-flash",
            "resolution": "1080p",
        },
    )

    captured: list = []
    source = tmp_path / "src.mp4"
    source.write_bytes(b"source")
    monkeypatch.setattr(
        tasks_module,
        "get_provider",
        lambda kind, name=None, **kwargs: _FakeVideoProvider(source, captured),
    )

    r = await client.post(f"/api/v1/fragments/{fid}/generate")
    assert r.status_code == 202
    job_id = r.json()["id"]

    await run_video_gen({"redis": None}, job_id)

    assert captured and captured[0].resolution == "1080p"

    db_session.expire_all()
    fragment = await db_session.get(Fragment, fid)
    assert fragment is not None
    assert fragment.status == "generated"
    # 0.15 USD/s (1080p) * 10 s
    assert fragment.cost_usd == 1.5

    videos = (
        await db_session.execute(select(FragmentVideo).where(FragmentVideo.fragment_id == fid))
    ).scalars().all()
    assert len(videos) == 1
    assert videos[0].provider == "omni"
    assert videos[0].model == "gemini-omni-1.1-flash"
    assert videos[0].resolution == "1080p"
    assert videos[0].cost_usd == 1.5


def test_model_pricing_units():
    assert model_pricing("video", "gemini-omni-1.1-flash") == {
        "unit": "second",
        "usd": 0.10,
        "by_resolution": {"360p": 0.03, "720p": 0.10, "1080p": 0.15, "4k": 0.30},
    }
    assert model_pricing("image", "nano-banana") == {"unit": "image", "usd": 0.04}
    assert model_pricing("llm", "gpt-4o-mini") == {
        "unit": "1m_tokens",
        "input": 0.15,
        "output": 0.60,
    }
    assert model_pricing("video", "modelo-desconocido") is None
