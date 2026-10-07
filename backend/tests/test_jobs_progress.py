import asyncio
from collections.abc import Awaitable, Callable

from app.jobs import queue as queue_module
from app.jobs import tasks
from app.jobs.progress import run_resource_progress
from app.jobs.tasks import run_script_gen
from app.models import Job, JobStatus
from app.schemas.script import (
    ScriptCharacter,
    ScriptDialogue,
    ScriptDraft,
    ScriptEpisode,
    ScriptShot,
)
from app.services import scripting

ProgressSink = Callable[[int], Awaitable[None]]


def _draft() -> ScriptDraft:
    return ScriptDraft(
        synopsis="x",
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


def _fake_cpu(monkeypatch, values: list[float]):
    calls = {"n": 0}

    def cpu_percent(interval=None):
        value = values[min(calls["n"], len(values) - 1)]
        calls["n"] += 1
        return value

    monkeypatch.setattr("app.jobs.progress.psutil.cpu_percent", cpu_percent)


async def test_run_resource_progress_advances_up_to_cap(monkeypatch):
    _fake_cpu(monkeypatch, [80.0, 80.0, 80.0, 80.0, 80.0])
    emitted: list[int] = []
    calls = {"n": 0}

    def stopped():
        calls["n"] += 1
        return calls["n"] > 3

    async def sink(progress: int):
        emitted.append(progress)

    await run_resource_progress(sink, budget_seconds=2.0, stopped=stopped, interval=0.01)

    assert emitted, "debió emitir progreso"
    assert emitted[-1] <= 90
    assert emitted[-1] > 0


async def test_run_resource_progress_stays_low_without_cpu(monkeypatch):
    _fake_cpu(monkeypatch, [0.0, 0.0, 0.0, 0.0])
    emitted: list[int] = []
    calls = {"n": 0}

    def stopped():
        calls["n"] += 1
        return calls["n"] > 3

    async def sink(progress: int):
        emitted.append(progress)

    await run_resource_progress(sink, budget_seconds=2.0, stopped=stopped, interval=0.01)

    assert emitted[-1] < 30


async def test_script_gen_updates_progress_while_running(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    from app.config import Settings

    monkeypatch.setattr(
        tasks, "get_settings", lambda: Settings(script_gen_budget_seconds=5)
    )
    _fake_cpu(monkeypatch, [80.0] * 20)

    async def slow_generate(provider, req, retries):
        await asyncio.sleep(1.5)
        return _draft()

    monkeypatch.setattr(scripting, "generate_script_draft", slow_generate)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/generate-script",
        json={"synopsis": "x", "num_episodes": 1},
    )
    job_id = r.json()["id"]

    task = asyncio.create_task(run_script_gen({"redis": fake_redis}, job_id))
    job = None
    for _ in range(30):
        await asyncio.sleep(0.1)
        db_session.expire_all()
        job = await db_session.get(Job, job_id)
        if job.status == JobStatus.running and job.progress > 0:
            break
    assert job is not None
    assert job.status == JobStatus.running
    assert job.progress > 0

    await asyncio.wait_for(task, timeout=5)
    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded
    assert job.progress == 100