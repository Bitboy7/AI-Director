import asyncio
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.jobs.progress import run_resource_progress
from app.jobs.state import (
    is_cancelled,
    mark_cancelled,
    mark_failed,
    mark_progress,
    mark_running,
    mark_succeeded,
)
from app.models import (
    AssetKind,
    Episode,
    Fragment,
    FragmentReferenceImage,
    FragmentVideo,
    ImageOrigin,
    Job,
    JobStatus,
    JobType,
    Project,
    ReferenceImage,
    Resource,
    ResourceVariant,
    StoryboardPanel,
)
from app.providers import default_provider, get_provider
from app.providers.base import VideoSubmitPayload
from app.schemas.script import ScriptGenerationRequest
from app.services import scripting
from app.services.assembly import AssemblyMissingFragmentsError, assemble_episode
from app.services.credentials import get_credentials
from app.services.mentions import extract_mentions
from app.services.persist import store_script_draft
from app.services.storage import asset_dir, save_generated
from app.services.storyboards import fragment_prompt
from app.services.styles import style_prompt
from app.services.usage import record_api_call


async def record_llm_call(
    provider,
    provider_name: str,
    model: str | None,
    project_id: int | None,
    job_id: int | None,
    started: float,
    status: str = "ok",
    error: str | None = None,
) -> None:
    usage = (getattr(provider, "last_usage", {}) or {}) if provider is not None else {}
    resolved_model = (
        getattr(provider, "default_model", None)
        or getattr(provider, "model", None)
        or model
        or ""
    )
    async with get_session_factory()() as session:
        record_api_call(
            session,
            kind="llm",
            provider=provider_name,
            model=resolved_model,
            duration_ms=(time.monotonic() - started) * 1000,
            project_id=project_id,
            job_id=job_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            status=status,
            error=error,
        )
        await session.commit()


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
        project = await session.get(Project, project_id)
        provider_name = (
            (project.settings or {}).get("llm_provider")
            if project is not None
            else None
        ) or default_provider("llm")
        model = (project.settings or {}).get("llm_model") if project is not None else None
        credentials = await get_credentials(session, provider_name)

    await mark_running(job_id)
    box = {"stopped": False}
    monitor = asyncio.create_task(
        run_resource_progress(
            lambda progress: mark_progress(job_id, progress),
            budget_seconds=get_settings().script_gen_budget_seconds,
            stopped=lambda: box["stopped"],
        )
    )
    try:
        started = time.monotonic()
        provider = None
        try:
            provider = get_provider(
                "llm", provider_name, credentials=credentials, model=model or None
            )
            draft = await scripting.generate_script_draft(
                provider, request, get_settings().script_gen_retries
            )
        except scripting.ScriptValidationError as exc:
            await record_llm_call(
                provider, provider_name, model, project_id, job_id, started,
                status="error", error=str(exc),
            )
            await mark_failed(job_id, str(exc))
            return
        except Exception as exc:
            await record_llm_call(
                provider, provider_name, model, project_id, job_id, started,
                status="error", error=str(exc),
            )
            await mark_failed(job_id, f"error del proveedor LLM: {exc}")
            return
        await record_llm_call(provider, provider_name, model, project_id, job_id, started)

        try:
            async with get_session_factory()() as session:
                project = await session.get(Project, project_id)
                if project is None:
                    await mark_failed(job_id, "proyecto no encontrado")
                    return
                summary = store_script_draft(project, draft)
                await session.commit()
        except Exception as exc:
            await mark_failed(job_id, f"falló al guardar el guion: {exc}")
            return
        await mark_succeeded(job_id, summary)
    finally:
        box["stopped"] = True
        if not monitor.done():
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor


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
        provider_name = (project.settings or {}).get("llm_provider") or default_provider("llm")
        model = (project.settings or {}).get("llm_model")
        credentials = await get_credentials(session, provider_name)
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

    box = {"stopped": False}
    monitor = asyncio.create_task(
        run_resource_progress(
            lambda progress: mark_progress(job_id, progress),
            budget_seconds=get_settings().resource_gen_budget_seconds,
            stopped=lambda: box["stopped"],
        )
    )
    try:
        started = time.monotonic()
        provider = None
        try:
            provider = get_provider(
                "llm", provider_name, credentials=credentials, model=model or None
            )
            draft = await scripting.generate_resources_draft(
                provider, context, get_settings().script_gen_retries
            )
        except scripting.ScriptValidationError as exc:
            await record_llm_call(
                provider, provider_name, model, project_id, job_id, started,
                status="error", error=str(exc),
            )
            await mark_failed(job_id, str(exc))
            return
        except Exception as exc:
            await record_llm_call(
                provider, provider_name, model, project_id, job_id, started,
                status="error", error=str(exc),
            )
            await mark_failed(job_id, f"error del proveedor LLM: {exc}")
            return
        await record_llm_call(provider, provider_name, model, project_id, job_id, started)

        try:
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
                        select(ResourceVariant).where(
                            ResourceVariant.resource_id == resource.id
                        )
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
        except Exception as exc:
            await mark_failed(job_id, f"falló al guardar los recursos: {exc}")
            return

        await mark_succeeded(
            job_id, {"created_variants": created_variants, "skipped": skipped}
        )
    finally:
        box["stopped"] = True
        if not monitor.done():
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor


async def run_resource_image_gen(ctx: dict, job_id: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        project_id = job.payload["project_id"]
        resource_ids = list(job.payload.get("resource_ids") or [])
        provider_override = job.payload.get("provider")
        model_override = job.payload.get("model")
        project = await session.get(Project, project_id)
        if project is None:
            await mark_failed(job_id, "proyecto no encontrado")
            return
        provider_name = (
            provider_override
            or (project.settings or {}).get("image_provider")
            or default_provider("image")
        )
        model = model_override or (project.settings or {}).get("image_model") or None
        credentials = await get_credentials(session, provider_name)
        style = style_prompt(project.video_style)
        aspect = project.aspect_ratio or "16:9"
        pid = project.id

    await mark_running(job_id)
    total = max(1, len(resource_ids))
    done = 0
    errors: list[dict] = []
    try:
        provider = get_provider("image", provider_name, credentials=credentials)
    except Exception as exc:
        await mark_failed(job_id, f"no se pudo crear el proveedor de imagen: {exc}")
        return

    for resource_id in resource_ids:
        started = time.monotonic()
        try:
            async with get_session_factory()() as session:
                resource = await session.get(Resource, resource_id)
                if resource is None:
                    raise ValueError("recurso no encontrado")
                variant = resource.variants[0] if resource.variants else None
                if variant is None:
                    variant = ResourceVariant(
                        resource_id=resource.id,
                        name="Principal",
                        description=(resource.profile or {}).get("description", ""),
                    )
                    session.add(variant)
                    await session.flush()
                prompt = (resource.profile or {}).get("description") or resource.name
                paths = await provider.generate(
                    prompt, model=model, style=style or None, aspect=aspect, count=1
                )
                for path in paths:
                    rel = await save_generated(session, pid, AssetKind.image, path)
                    session.add(
                        ReferenceImage(
                            variant_id=variant.id,
                            path=rel,
                            origin=ImageOrigin.generated,
                            kind="reference",
                        )
                    )
                record_api_call(
                    session,
                    kind="image",
                    provider=provider_name,
                    model=model or "",
                    duration_ms=(time.monotonic() - started) * 1000,
                    project_id=pid,
                    job_id=job_id,
                    units=len(paths),
                )
                await session.commit()
        except Exception as exc:
            errors.append({"resource_id": resource_id, "error": str(exc)})
        done += 1
        await mark_progress(job_id, min(99, int(done / total * 100)))

    if errors and done == len(errors):
        await mark_failed(job_id, f"falló la generación de imágenes: {errors[0]['error']}")
        return
    await mark_succeeded(job_id, {"generated": done - len(errors), "failed": errors})


async def run_storyboard_gen(ctx: dict, job_id: int) -> None:
    async with get_session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        project_id = job.payload["project_id"]
        episode_ids = job.payload.get("episode_ids")
        project = await session.get(Project, project_id)
        if project is None:
            await mark_failed(job_id, "proyecto no encontrado")
            return
        provider_name = (project.settings or {}).get("llm_provider") or default_provider("llm")
        model = (project.settings or {}).get("llm_model")
        credentials = await get_credentials(session, provider_name)
        style = style_prompt(project.video_style)
        synopsis = project.synopsis

        resources = (
            await session.execute(select(Resource).where(Resource.project_id == project_id))
        ).scalars().all()
        resources_by_type: dict[str, list[str]] = {"character": [], "scene": [], "prop": []}
        for resource in resources:
            resources_by_type.setdefault(resource.type.value, []).append(resource.name)

        query = select(Episode).where(Episode.project_id == project_id)
        if episode_ids:
            query = query.where(Episode.id.in_(episode_ids))
        episodes = (await session.execute(query)).scalars().all()
        contexts: list[dict] = []
        for episode in episodes:
            for fragment in episode.fragments:
                contexts.append(
                    {
                        "fragment_id": fragment.id,
                        "episode": episode.number,
                        "shot": fragment.shot_number,
                        "time_place": fragment.time_place,
                        "cast": fragment.cast,
                        "action": fragment.prompt_video,
                        "duration": fragment.duration,
                        "dialogues": [line.text for line in fragment.dialogue_lines],
                        "resources": resources_by_type,
                        "style": style,
                        "synopsis": synopsis,
                    }
                )

    await mark_running(job_id)
    try:
        provider = get_provider(
            "llm", provider_name, credentials=credentials, model=model or None
        )
    except Exception as exc:
        await mark_failed(job_id, f"no se pudo crear el proveedor LLM: {exc}")
        return

    total = max(1, len(contexts))
    done = 0
    errors: list[dict] = []
    total_panels = 0
    for context in contexts:
        fragment_id = context.pop("fragment_id")
        started = time.monotonic()
        try:
            draft = await scripting.generate_storyboard_draft(
                provider, context, get_settings().script_gen_retries
            )
            usage = getattr(provider, "last_usage", {}) or {}
            async with get_session_factory()() as session:
                existing = (
                    await session.execute(
                        select(StoryboardPanel).where(
                            StoryboardPanel.fragment_id == fragment_id
                        )
                    )
                ).scalars().all()
                for panel in existing:
                    await session.delete(panel)
                for order, item in enumerate(draft.panels):
                    session.add(
                        StoryboardPanel(
                            fragment_id=fragment_id,
                            order=order,
                            title=item.title,
                            start_seconds=item.start_seconds,
                            end_seconds=item.end_seconds,
                            prompt=item.prompt,
                        )
                    )
                await session.commit()
                total_panels += len(draft.panels)
                record_api_call(
                    session,
                    kind="llm",
                    provider=provider_name,
                    model=getattr(provider, "default_model", None) or model or "",
                    duration_ms=(time.monotonic() - started) * 1000,
                    project_id=project_id,
                    job_id=job_id,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                )
                await session.commit()
        except Exception as exc:
            errors.append({"fragment_id": fragment_id, "error": str(exc)})
        done += 1
        await mark_progress(job_id, min(99, int(done / total * 100)))

    if errors and done == len(errors):
        await mark_failed(job_id, f"falló la generación de storyboards: {errors[0]['error']}")
        return
    await mark_succeeded(
        job_id,
        {"fragments": done - len(errors), "panels": total_panels, "failed": errors},
    )


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

        provider_name = (
            fragment.video_provider
            or (project.settings or {}).get("video_provider")
            or default_provider("video")
        )
        model = fragment.video_model or (project.settings or {}).get("video_model")
        resolution = fragment.resolution or None
        credentials = await get_credentials(session, provider_name)

        reference_images: list[Path] = []
        for image in fragment.reference_images:
            path = storage / image.path
            if path.exists():
                reference_images.append(path)

        resources = (
            await session.execute(
                select(Resource).where(Resource.project_id == project.id)
            )
        ).scalars().all()
        by_name = {resource.name: resource for resource in resources}
        prompt = fragment_prompt(fragment)
        for name in extract_mentions(prompt, list(by_name)):
            resource = by_name.get(name)
            if resource is None or not resource.variants:
                continue
            for image in resource.variants[0].reference_images:
                path = storage / image.path
                if path.exists():
                    reference_images.append(path)

        payload = VideoSubmitPayload(
            prompt=prompt,
            duration_seconds=fragment.duration or 10,
            aspect_ratio=project.aspect_ratio or "16:9",
            style=style_prompt(project.video_style),
            resolution=resolution,
            reference_images=reference_images,
        )
        stamp = int(time.time() * 1000)
        dest_dir = asset_dir(project.id, AssetKind.video)
        dest = dest_dir / f"{fragment_id}_{stamp}.mp4"
        dest_rel = f"{project.id}/videos/{fragment_id}_{stamp}.mp4"

    await mark_running(job_id)
    try:
        provider = get_provider(
            "video", provider_name, credentials=credentials, model=model or None
        )
        task_id = await provider.submit(payload)
        start = time.monotonic()
        budget = max(1, payload.duration_seconds * 4)
        status = await provider.poll(task_id)
        while status.state not in ("succeeded", "failed"):
            if await is_cancelled(job_id):
                await mark_cancelled(job_id)
                return
            await asyncio.sleep(1)
            elapsed = time.monotonic() - start
            await mark_progress(job_id, min(90, int(elapsed / budget * 100)))
            status = await provider.poll(task_id)
        if status.state == "failed":
            await mark_failed(job_id, status.error or "el proveedor de video falló")
            return

        dest_dir.mkdir(parents=True, exist_ok=True)
        await provider.download(status.video_url, dest)
    except Exception as exc:
        await mark_failed(job_id, f"generación de video falló: {exc}")
        return

    async with get_session_factory()() as session:
        fragment = await session.get(Fragment, fragment_id)
        fragment.video_path = dest_rel
        fragment.status = "generated"
        call = record_api_call(
            session,
            kind="video",
            provider=provider_name,
            model=model or "",
            duration_ms=(time.monotonic() - start) * 1000,
            project_id=project.id,
            job_id=job_id,
            units=payload.duration_seconds,
            resolution=resolution,
        )
        session.add(
            FragmentVideo(
                fragment_id=fragment_id,
                path=dest_rel,
                provider=provider_name,
                model=model or "",
                resolution=resolution,
                cost_usd=call.cost_usd,
            )
        )
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


async def _enqueue_safe(
    ctx: dict, queue: str, func_name: str, job_id: int, defer_by: float = 0
) -> None:
    redis = ctx.get("redis")
    if redis is not None:
        await redis.enqueue_job(
            func_name,
            job_id,
            _queue_name=queue,
            _job_id=str(job_id),
            _defer_by=defer_by,
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
        async with get_session_factory()() as session:
            episode_fragments = (
                await session.execute(
                    select(Fragment).where(Fragment.episode_id == episode_id)
                )
            ).scalars().all()
            fragment_ids = [f.id for f in episode_fragments]
            video_jobs = (
                await session.execute(select(Job).where(Job.type == JobType.video_gen))
            ).scalars().all()
            related = [j for j in video_jobs if j.payload.get("fragment_id") in fragment_ids]
            terminal = {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}
            if related and all(j.status in terminal for j in related):
                missing = [
                    f"{episode.number}-{f.shot_number}"
                    for f in episode_fragments
                    if not f.video_path
                ]
                await mark_failed(
                    job_id,
                    "faltan videos para los planos: "
                    + ", ".join(f"[{m}]" for m in missing),
                )
                return

        await _enqueue_safe(ctx, "assembly", "run_episode_assembly", job_id, defer_by=5)
        async with get_session_factory()() as session:
            job = await session.get(Job, job_id)
            job.status = JobStatus.queued
            job.updated_at = datetime.now()
            await session.commit()
        return

    await mark_running(job_id)
    try:
        async with get_session_factory()() as session:
            result = await assemble_episode(
                session,
                episode_id,
                subtitle_burn,
                on_progress=lambda value: mark_progress(job_id, min(99, value)),
            )
            await session.commit()
        await mark_succeeded(job_id, result)
    except AssemblyMissingFragmentsError as exc:
        await mark_failed(job_id, str(exc))
    except Exception as exc:
        await mark_failed(job_id, f"assembly falló: {exc}")
