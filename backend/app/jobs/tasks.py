import asyncio

from app.config import get_settings
from app.db import get_session_factory
from app.jobs.state import mark_failed, mark_running, mark_succeeded
from app.models import Job, Project
from app.providers import get_provider
from app.schemas.script import ScriptGenerationRequest
from app.services import scripting
from app.services.persist import apply_script_draft


async def run_ping(ctx: dict, job_id: int) -> None:
    await asyncio.sleep(0.1)
    await mark_succeeded(job_id, {"pong": True})


async def run_script_gen(ctx: dict, job_id: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        project_id = job.payload["project_id"]
        request = ScriptGenerationRequest.model_validate(job.payload["request"])

    await mark_running(job_id)
    try:
        provider = get_provider("llm", "ollama")
        draft = await scripting.generate_script_draft(
            provider, request, get_settings().script_gen_retries
        )
    except scripting.ScriptValidationError as exc:
        await mark_failed(job_id, str(exc))
        return
    except Exception as exc:
        await mark_failed(job_id, f"error del proveedor LLM: {exc}")
        return

    async with get_session_factory()() as session:
        project = await session.get(Project, project_id)
        if project is None:
            await mark_failed(job_id, "proyecto no encontrado")
            return
        summary = await apply_script_draft(session, project, draft)
        await session.commit()
    await mark_succeeded(job_id, summary)


async def run_video_gen(ctx: dict, job_id: int) -> None:
    raise NotImplementedError


async def run_episode_assembly(ctx: dict, job_id: int) -> None:
    raise NotImplementedError
