import asyncio
from datetime import datetime

from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.jobs.state import (
    is_cancelled,
    mark_cancelled,
    mark_failed,
    mark_running,
    mark_succeeded,
)
from app.models import (
    AssetKind,
    Episode,
    Fragment,
    Job,
    JobStatus,
    JobType,
    Project,
    Resource,
    ResourceVariant,
)
from app.providers import get_provider
from app.providers.base import VideoSubmitPayload
from app.schemas.script import ScriptGenerationRequest
from app.services import scripting
from app.services.assembly import AssemblyMissingFragmentsError, assemble_episode
from app.services.persist import apply_script_draft
from app.services.storage import asset_dir


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
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        fragment_id = job.payload["fragment_id"]
        fragment = await session.get(Fragment, fragment_id)
        if fragment is None:
            await mark_failed(job_id, "fragmento no encontrado")
            return
        episode = await session.get(Episode, fragment.episode_id)
        project = await session.get(Project, episode.project_id)
        settings = get_settings()
        storage = settings.storage_dir.resolve()

        reference_images: list[Path] = []
        for cast_entry in fragment.cast or []:
            variant_id = cast_entry.get("variant_id") if isinstance(cast_entry, dict) else None
            if variant_id is None:
                continue
            variant = await session.get(ResourceVariant, variant_id)
            if variant is None:
                continue
            for img in variant.reference_images:
                path = storage / img.path
                if path.exists():
                    reference_images.append(path)

        payload = VideoSubmitPayload(
            prompt=fragment.prompt_video or f"Plano {fragment.shot_number}",
            duration_seconds=fragment.duration or 10,
            aspect_ratio=project.aspect_ratio or "16:9",
            style=project.video_style or "",
            reference_images=reference_images,
        )
        dest_dir = asset_dir(project.id, AssetKind.video)
        dest = dest_dir / f"{fragment_id}.mp4"
        dest_rel = f"{project.id}/videos/{fragment_id}.mp4"

    await mark_running(job_id)
    provider = get_provider("video", None)
    task_id = await provider.submit(payload)
    status = await provider.poll(task_id)
    while status.state not in ("succeeded", "failed"):
        if await is_cancelled(job_id):
            await mark_cancelled(job_id)
            return
        await asyncio.sleep(1)
        status = await provider.poll(task_id)
    if status.state == "failed":
        await mark_failed(job_id, status.error or "el proveedor de video falló")
        return

    dest_dir.mkdir(parents=True, exist_ok=True)
    await provider.download(status.video_url, dest)

    async with get_session_factory()() as session:
        fragment = await session.get(Fragment, fragment_id)
        fragment.video_path = dest_rel
        fragment.status = "generated"
        await session.commit()
        episode_id = fragment.episode_id
        frags = (
            await session.execute(
                select(Fragment).where(Fragment.episode_id == episode_id)
            )
        ).scalars().all()

    await mark_succeeded(job_id, {"video_path": dest_rel})

    async with get_session_factory()() as session:
        existing = (
            await session.execute(
                select(Job).where(Job.type == JobType.episode_assembly)
            )
        ).scalars().all()
        has_pending_assembly = any(
            j.payload.get("episode_id") == episode_id
            and j.status in (JobStatus.queued, JobStatus.running)
            for j in existing
        )
        if all(f.video_path for f in frags) and not has_pending_assembly:
            assembly_job = Job(
                type=JobType.episode_assembly,
                status=JobStatus.queued,
                payload={"episode_id": episode_id, "subtitle_burn": False},
            )
            session.add(assembly_job)
            await session.commit()
            await _enqueue_safe(ctx, "assembly", "run_episode_assembly", assembly_job.id)


async def _enqueue_safe(ctx: dict, queue: str, func_name: str, job_id: int) -> None:
    redis = ctx.get("redis")
    if redis is not None:
        await redis.enqueue_job(
            func_name, job_id, _queue_name=queue, _job_id=str(job_id)
        )


async def run_episode_assembly(ctx: dict, job_id: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        if job.status == JobStatus.cancelled:
            return
        episode_id = job.payload["episode_id"]
        subtitle_burn = job.payload.get("subtitle_burn", False)
        episode = await session.get(Episode, episode_id)
        if episode is None:
            await mark_failed(job_id, "episodio no encontrado")
            return
        pending = any(not f.video_path for f in episode.fragments)

    if pending:
        await _enqueue_safe(ctx, "assembly", "run_episode_assembly", job_id)
        async with get_session_factory()() as session:
            job = await session.get(Job, job_id)
            job.status = JobStatus.queued
            job.updated_at = datetime.now()
            await session.commit()
        return

    await mark_running(job_id)
    try:
        async with get_session_factory()() as session:
            result = await assemble_episode(session, episode_id, subtitle_burn)
            await session.commit()
        await mark_succeeded(job_id, result)
    except AssemblyMissingFragmentsError as exc:
        await mark_failed(job_id, str(exc))
    except Exception as exc:
        await mark_failed(job_id, f"assembly falló: {exc}")
