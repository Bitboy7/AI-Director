import asyncio
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.jobs.state import mark_cancelled
from app.jobs.tasks import run_video_gen
from app.models import DialogueLine, Episode, Fragment, Job, JobStatus, JobType, Project
from app.providers.base import TTSResult, VideoTaskStatus
from app.services.assembly import AssemblyMissingFragmentsError, assemble_episode
from app.services.srt import SrtEntry, build_srt


def _make_wav_1s(tmp_path: Path) -> Path:
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
    return wav


def _make_mp4(tmp_path: Path, name: str, seconds: int = 3) -> Path:
    out = tmp_path / name
    subprocess.run(
        [
            get_settings().ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x2255aa:s=320x180:r=24",
            "-t",
            str(seconds),
            "-pix_fmt",
            "yuv420p",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


class FakeTTS:
    def __init__(self, wav: Path):
        self.wav = wav

    async def synthesize(self, text: str, voice: str) -> TTSResult:
        return TTSResult(path=self.wav, duration_seconds=1.0)


async def _setup_episode(db_session, tmp_path, with_videos=True):
    p = Project(name="P", synopsis="s", video_style="cyberpunk")
    db_session.add(p)
    await db_session.flush()
    e = Episode(project_id=p.id, number=1, title="Ep1")
    db_session.add(e)
    await db_session.flush()
    storage = get_settings().storage_dir
    for i in (1, 2):
        f = Fragment(
            episode_id=e.id,
            shot_number=i,
            time_place="calle",
            cast=[],
            prompt_video=f"plano {i}",
            duration=3,
            status="generated" if with_videos else "pending",
        )
        db_session.add(f)
        await db_session.flush()
        db_session.add(DialogueLine(fragment_id=f.id, text=f"línea {i}", order=0))
        if with_videos:
            src = _make_mp4(tmp_path, f"f{i}.mp4", seconds=3)
            dest_dir = storage / str(p.id) / "videos"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"f{i}.mp4"
            dest.write_bytes(src.read_bytes())
            f.video_path = f"{p.id}/videos/f{i}.mp4"
    await db_session.commit()
    return p.id, e.id


def test_build_srt_format():
    assert (
        build_srt([SrtEntry(start_seconds=0.0, end_seconds=2.0, text="Hola")])
        == "1\n00:00:00,000 --> 00:00:02,000\nHola\n\n"
    )


async def test_assemble_two_fragments(db_session, tmp_path, monkeypatch):
    wav = _make_wav_1s(tmp_path)
    pid, eid = await _setup_episode(db_session, tmp_path)

    from app.services import assembly

    monkeypatch.setattr(assembly, "get_provider", lambda kind, name=None: FakeTTS(wav))

    result = await assemble_episode(db_session, eid, subtitle_burn=False)
    await db_session.commit()

    storage = get_settings().storage_dir
    final = storage / result["final"]
    srt = storage / result["srt"]
    assert final.exists() and final.stat().st_size > 1000
    assert srt.exists()
    content = srt.read_text(encoding="utf-8")
    assert content.count("-->") == 2

    db_session.expire_all()
    ep = await db_session.get(Episode, eid)
    assert ep.status == "assembled"


async def test_assemble_missing_fragment_raises(db_session, tmp_path):
    _pid, eid = await _setup_episode(db_session, tmp_path, with_videos=False)
    with pytest.raises(AssemblyMissingFragmentsError) as excinfo:
        await assemble_episode(db_session, eid, subtitle_burn=False)
    assert "[1-1]" in str(excinfo.value) and "[1-2]" in str(excinfo.value)


class SlowVideoProvider:
    async def submit(self, payload):
        return "t1"

    async def poll(self, task_id):
        return VideoTaskStatus(state="processing")

    async def download(self, url, dest):
        return dest


async def test_video_job_cancel_stops_polling(db_session, tmp_path, monkeypatch, fake_redis):
    pid, eid = await _setup_episode(db_session, tmp_path, with_videos=False)
    result = await db_session.execute(select(Fragment).where(Fragment.episode_id == eid))
    frag = result.scalars().first()
    job = Job(
        type=JobType.video_gen, status=JobStatus.queued, payload={"fragment_id": frag.id}
    )
    db_session.add(job)
    await db_session.commit()
    job_id = job.id
    frag_id = frag.id

    from app.jobs import tasks

    monkeypatch.setattr(
        tasks, "get_provider", lambda kind, name=None: SlowVideoProvider()
    )

    task = asyncio.create_task(run_video_gen({"redis": fake_redis}, job_id))
    await asyncio.sleep(0.3)
    await mark_cancelled(job_id)
    await asyncio.wait_for(task, timeout=5)

    db_session.expire_all()
    j = await db_session.get(Job, job_id)
    assert j.status == JobStatus.cancelled
    f = await db_session.get(Fragment, frag_id)
    assert f.video_path is None
