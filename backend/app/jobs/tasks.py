import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.jobs.state import mark_failed, mark_running, mark_succeeded
from app.models import Job, Project, Resource, ResourceVariant
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


async def run_resource_gen(ctx: dict, job_id: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        project_id = job.payload["project_id"]

    await mark_running(job_id)

    async with get_session_factory()() as session:
        project = await session.get(Project, project_id)
        if project is None:
            await mark_failed(job_id, "proyecto no encontrado")
            return
        resources = (
            await session.execute(
                select(Resource).where(Resource.project_id == project_id)
            )
        ).scalars()
        context = {
            "synopsis": project.synopsis,
            "video_style": project.video_style,
            "resources": [
                {
                    "type": r.type.value,
                    "name": r.name,
                    "description": (r.profile or {}).get("description", ""),
                    "variants": [v.name for v in r.variants],
                }
                for r in resources
            ],
        }

    try:
        provider = get_provider("llm", "ollama")
        draft = await scripting.generate_resources_draft(
            provider, context, get_settings().script_gen_retries
        )
    except scripting.ScriptValidationError as exc:
        await mark_failed(job_id, str(exc))
        return
    except Exception as exc:
        await mark_failed(job_id, f"error del proveedor LLM: {exc}")
        return

    async with get_session_factory()() as session:
        created_variants = 0
        skipped: list[str] = []
        for rd in draft.resources:
            result = await session.execute(
                select(Resource).where(
                    Resource.project_id == project_id,
                    Resource.type == rd.type,
                    Resource.name == rd.name,
                )
            )
            resource = result.scalar_one_or_none()
            if resource is None:
                resource = Resource(
                    project_id=project_id,
                    type=rd.type,
                    name=rd.name,
                    profile={"description": rd.description, "tags": []},
                )
                session.add(resource)
                await session.flush()
            var_result = await session.execute(
                select(ResourceVariant).where(ResourceVariant.resource_id == resource.id)
            )
            existing_names = {v.name for v in var_result.scalars()}
            for vd in rd.variants:
                if vd.name in existing_names:
                    skipped.append(f"{rd.name}: {vd.name}")
                    continue
                session.add(
                    ResourceVariant(
                        resource_id=resource.id,
                        name=vd.name,
                        description=vd.description,
                    )
                )
                created_variants += 1
        await session.commit()

    await mark_succeeded(job_id, {"created_variants": created_variants, "skipped": skipped})


async def run_video_gen(ctx: dict, job_id: int) -> None:
    raise NotImplementedError


async def run_episode_assembly(ctx: dict, job_id: int) -> None:
    raise NotImplementedError
