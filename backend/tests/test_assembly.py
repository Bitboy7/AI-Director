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
from app.services.assembly import (
    AssemblyMissingFragmentsError,
    _ffprobe_duration,
    assemble_episode,
)
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


def _probe_audio(path: Path) -> str:
    proc = subprocess.run(
        [
            get_settings().ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


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
    _pid, eid = await _setup_episode(db_session, tmp_path)

    result = await assemble_episode(db_session, eid, subtitle_burn=False)
    await db_session.commit()

    storage = get_settings().storage_dir
    final = storage / result["final"]
    assert final.exists() and final.stat().st_size > 1000

    # El video final conserva la duración de los fragmentos (2×3s).
    duration = await _ffprobe_duration(final)
    assert duration == pytest.approx(6.0, abs=0.6)

    db_session.expire_all()
    ep = await db_session.get(Episode, eid)
    assert ep.status == "assembled"


async def test_assemble_reports_progress(db_session, tmp_path, monkeypatch):
    _pid, eid = await _setup_episode(db_session, tmp_path)

    values: list[int] = []

    async def on_progress(value: int) -> None:
        values.append(value)

    await assemble_episode(db_session, eid, subtitle_burn=False, on_progress=on_progress)
    await db_session.commit()

    assert values == [50, 99]


async def test_assemble_mixed_dialogue_keeps_audio(db_session, tmp_path, monkeypatch):
    _pid, eid = await _setup_episode(db_session, tmp_path)

    # Deja el fragmento 2 sin diálogo; el ensamblaje ya no sintetiza voz, así
    # que solo debe concatenar conservando/normalizando el audio.
    result = await db_session.execute(
        select(DialogueLine).join(Fragment).where(
            Fragment.episode_id == eid, Fragment.shot_number == 2
        )
    )
    for line in result.scalars().all():
        await db_session.delete(line)
    await db_session.commit()

    res = await assemble_episode(db_session, eid, subtitle_burn=False)
    await db_session.commit()

    final = get_settings().storage_dir / res["final"]
    output = _probe_audio(final)
    assert "aac" in output
    assert "48000" in output


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


class FailingDownloadProvider:
    async def submit(self, payload):
        return "t1"

    async def poll(self, task_id):
        return VideoTaskStatus(state="succeeded", video_url="x")

    async def download(self, url, dest):
        raise RuntimeError("disco lleno")


async def test_video_job_marks_failed_on_provider_error(
    db_session, tmp_path, monkeypatch, fake_redis
):
    pid, eid = await _setup_episode(db_session, tmp_path, with_videos=False)
    frag = (await db_session.execute(select(Fragment).where(Fragment.episode_id == eid))).scalars().first()
    job = Job(
        type=JobType.video_gen,
        status=JobStatus.queued,
        payload={"fragment_id": frag.id},
    )
    db_session.add(job)
    await db_session.commit()
    job_id = job.id

    from app.jobs import tasks

    monkeypatch.setattr(
        tasks, "get_provider", lambda kind, name=None, **kwargs: FailingDownloadProvider()
    )

    await run_video_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    j = await db_session.get(Job, job_id)
    assert j.status == JobStatus.failed
    assert "disco lleno" in j.error


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
        tasks, "get_provider", lambda kind, name=None, **kwargs: SlowVideoProvider()
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


async def test_assembly_job_fails_when_all_video_jobs_terminal(
    db_session, tmp_path, fake_redis
):
    from app.jobs.tasks import run_episode_assembly

    _pid, eid = await _setup_episode(db_session, tmp_path, with_videos=False)
    frags = (
        await db_session.execute(select(Fragment).where(Fragment.episode_id == eid))
    ).scalars().all()
    for frag in frags:
        db_session.add(
            Job(
                type=JobType.video_gen,
                status=JobStatus.failed,
                payload={"fragment_id": frag.id},
            )
        )
    job = Job(
        type=JobType.episode_assembly,
        status=JobStatus.queued,
        payload={"episode_id": eid, "subtitle_burn": False},
    )
    db_session.add(job)
    await db_session.commit()
    job_id = job.id

    await run_episode_assembly({"redis": fake_redis}, job_id)

    db_session.expire_all()
    j = await db_session.get(Job, job_id)
    assert j.status == JobStatus.failed
    assert "[1-1]" in j.error and "[1-2]" in j.error


async def test_assembly_job_requeues_with_defer_when_videos_pending(
    db_session, tmp_path, fake_redis
):
    from app.jobs.tasks import run_episode_assembly

    _pid, eid = await _setup_episode(db_session, tmp_path, with_videos=False)
    frags = (
        await db_session.execute(select(Fragment).where(Fragment.episode_id == eid))
    ).scalars().all()
    for frag in frags:
        db_session.add(
            Job(
                type=JobType.video_gen,
                status=JobStatus.running,
                payload={"fragment_id": frag.id},
            )
        )
    job = Job(
        type=JobType.episode_assembly,
        status=JobStatus.queued,
        payload={"episode_id": eid, "subtitle_burn": False},
    )
    db_session.add(job)
    await db_session.commit()
    job_id = job.id

    calls: list[dict] = []

    class SpyRedis:
        def __init__(self, real):
            self.real = real

        async def enqueue_job(self, *args, **kwargs):
            calls.append(kwargs)
            await self.real.enqueue_job(*args, **kwargs)

    await run_episode_assembly({"redis": SpyRedis(fake_redis)}, job_id)

    db_session.expire_all()
    j = await db_session.get(Job, job_id)
    assert j.status == JobStatus.queued
    assert calls and calls[-1].get("_defer_by") == 5
