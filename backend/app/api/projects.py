import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import SessionDep
from app.config import get_settings
from app.jobs import queue as queue_module
from app.models import Episode, Job, JobStatus, JobType, Project
from app.schemas import JobRead, ProjectCreate, ProjectRead, ProjectUpdate, ScriptGenerationRequest
from app.schemas.script import ScriptDraft
from app.services.persist import materialize_script_draft
from app.services.usage import video_price

router = APIRouter(prefix="/api/v1")


async def get_project_or_404(session: SessionDep, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.post("/projects", response_model=ProjectRead)
async def create_project(payload: ProjectCreate, session: SessionDep):
    project = Project(
        name=payload.name,
        synopsis=payload.synopsis,
        video_style=payload.video_style,
        aspect_ratio=payload.aspect_ratio,
    )
    session.add(project)
    await session.commit()
    return project


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(session: SessionDep):
    result = await session.execute(select(Project).order_by(Project.id.desc()))
    return list(result.scalars())


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, session: SessionDep):
    return await get_project_or_404(session, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(project_id: int, payload: ProjectUpdate, session: SessionDep):
    project = await get_project_or_404(session, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.updated_at = datetime.now()
    await session.commit()
    return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: int, session: SessionDep):
    project = await get_project_or_404(session, project_id)
    await session.delete(project)
    await session.commit()


@router.put("/projects/{project_id}/phases/{phase}", response_model=ProjectRead)
async def update_phase(
    project_id: int,
    phase: int,
    session: SessionDep,
    payload: dict = Body(default={}),
):
    if phase not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="fase inválida (1-3)")
    project = await get_project_or_404(session, project_id)
    settings = dict(project.settings or {})
    completed = set(settings.get("completed_phases", []))
    if payload.get("completed"):
        if phase > 1 and (phase - 1) not in completed:
            raise HTTPException(
                status_code=400, detail="completa primero la fase anterior"
            )
        completed.add(phase)
    else:
        if any(p > phase for p in completed):
            raise HTTPException(
                status_code=400, detail="reabre primero las fases posteriores"
            )
        completed.discard(phase)
    settings["completed_phases"] = sorted(completed)
    project.settings = settings
    project.updated_at = datetime.now()
    await session.commit()
    return project


@router.post(
    "/projects/{project_id}/generate-script", response_model=JobRead, status_code=202
)
async def generate_script(
    project_id: int, payload: ScriptGenerationRequest, session: SessionDep
):
    project = await get_project_or_404(session, project_id)
    job = Job(
        type=JobType.script_gen,
        status=JobStatus.queued,
        payload={"project_id": project_id, "request": payload.model_dump()},
        project_id=project_id,
    )
    session.add(job)
    await session.commit()
    try:
        await queue_module.enqueue("default", "run_script_gen", job.id)
    except queue_module.QueueUnavailableError as exc:
        job.status = JobStatus.failed
        job.error = "queue_unavailable"
        job.updated_at = datetime.now()
        await session.commit()
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    return job


@router.get("/projects/{project_id}/script-draft")
async def get_script_draft(project_id: int, session: SessionDep):
    project = await get_project_or_404(session, project_id)
    settings = project.settings or {}
    return {
        "draft": settings.get("script_draft"),
        "confirmed": bool(settings.get("script_confirmed")),
    }


@router.post("/projects/{project_id}/confirm-script", response_model=ProjectRead)
async def confirm_script(project_id: int, session: SessionDep):
    project = await get_project_or_404(session, project_id)
    draft_data = (project.settings or {}).get("script_draft")
    if not draft_data:
        raise HTTPException(status_code=400, detail="no hay guion generado para confirmar")
    draft = ScriptDraft.model_validate(draft_data)
    await materialize_script_draft(session, project, draft)
    completed = set((project.settings or {}).get("completed_phases", []))
    completed.add(1)
    settings = dict(project.settings or {})
    settings["completed_phases"] = sorted(completed)
    project.settings = settings
    project.updated_at = datetime.now()
    await session.commit()
    return project


@router.post(
    "/projects/{project_id}/generate-resources", response_model=JobRead, status_code=202
)
async def generate_resources(project_id: int, session: SessionDep, payload: dict = Body(default={})):
    project = await get_project_or_404(session, project_id)
    job = Job(
        type=JobType.resource_gen,
        status=JobStatus.queued,
        payload={"project_id": project_id},
        project_id=project_id,
    )
    session.add(job)
    await session.commit()
    try:
        await queue_module.enqueue("default", "run_resource_gen", job.id)
    except queue_module.QueueUnavailableError as exc:
        job.status = JobStatus.failed
        job.error = "queue_unavailable"
        job.updated_at = datetime.now()
        await session.commit()
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    return job


class ResourceImagesRequest(BaseModel):
    resource_ids: list[int]
    provider: str | None = None
    model: str | None = None


@router.post(
    "/projects/{project_id}/resources/generate-images",
    response_model=JobRead,
    status_code=202,
)
async def generate_resource_images(
    project_id: int, payload: ResourceImagesRequest, session: SessionDep
):
    await get_project_or_404(session, project_id)
    if not payload.resource_ids:
        raise HTTPException(status_code=400, detail="selecciona al menos un recurso")
    job = Job(
        type=JobType.resource_image_gen,
        status=JobStatus.queued,
        payload={
            "project_id": project_id,
            "resource_ids": payload.resource_ids,
            "provider": payload.provider,
            "model": payload.model,
        },
        project_id=project_id,
    )
    session.add(job)
    await session.commit()
    try:
        await queue_module.enqueue("default", "run_resource_image_gen", job.id)
    except queue_module.QueueUnavailableError as exc:
        job.status = JobStatus.failed
        job.error = "queue_unavailable"
        job.updated_at = datetime.now()
        await session.commit()
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    return job


class StoryboardsRequest(BaseModel):
    episode_ids: list[int] | None = None


@router.post(
    "/projects/{project_id}/storyboards", response_model=JobRead, status_code=202
)
async def generate_storyboards(
    project_id: int, payload: StoryboardsRequest, session: SessionDep
):
    await get_project_or_404(session, project_id)
    job = Job(
        type=JobType.storyboard_gen,
        status=JobStatus.queued,
        payload={"project_id": project_id, "episode_ids": payload.episode_ids},
        project_id=project_id,
    )
    session.add(job)
    await session.commit()
    try:
        await queue_module.enqueue("default", "run_storyboard_gen", job.id)
    except queue_module.QueueUnavailableError as exc:
        job.status = JobStatus.failed
        job.error = "queue_unavailable"
        job.updated_at = datetime.now()
        await session.commit()
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    return job


async def _extract_frame(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        get_settings().ffmpeg_path,
        "-y",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-1",
        str(dest),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()


@router.get("/projects/{project_id}/cost-estimate")
async def project_cost_estimate(project_id: int, session: SessionDep):
    project = await get_project_or_404(session, project_id)
    settings = project.settings or {}
    episodes = (
        await session.execute(
            select(Episode)
            .where(Episode.project_id == project_id)
            .order_by(Episode.number)
        )
    ).scalars().all()

    breakdown: list[dict] = []
    total_cost = 0.0
    total_seconds = 0
    total_fragments = 0
    for episode in episodes:
        pending = [
            fragment
            for fragment in sorted(episode.fragments, key=lambda f: f.shot_number)
            if fragment.status != "generated"
        ]
        if not pending:
            continue
        seconds = sum(fragment.duration or 10 for fragment in pending)
        cost = 0.0
        for fragment in pending:
            model = fragment.video_model or settings.get("video_model") or ""
            resolution = fragment.resolution or settings.get("resolution")
            cost += (fragment.duration or 10) * video_price(model, resolution)
        breakdown.append(
            {
                "episode_id": episode.id,
                "number": episode.number,
                "title": episode.title or f"Capítulo {episode.number}",
                "fragments": len(pending),
                "seconds": seconds,
                "cost_usd": round(cost, 4),
            }
        )
        total_cost += cost
        total_seconds += seconds
        total_fragments += len(pending)

    return {
        "episodes": breakdown,
        "total": {
            "fragments": total_fragments,
            "seconds": total_seconds,
            "cost_usd": round(total_cost, 4),
        },
    }


@router.get("/projects/{project_id}/cover")
async def get_project_cover(project_id: int, session: SessionDep):
    await get_project_or_404(session, project_id)
    episodes = (
        await session.execute(
            select(Episode)
            .where(Episode.project_id == project_id)
            .order_by(Episode.number)
        )
    ).scalars().all()

    video_rel: str | None = None
    for episode in episodes:
        for fragment in sorted(episode.fragments, key=lambda f: f.shot_number):
            if fragment.video_path:
                video_rel = fragment.video_path
                break
        if video_rel:
            break
    if video_rel is None:
        raise HTTPException(status_code=404, detail="no hay videos generados")

    storage = get_settings().storage_dir.resolve()
    source = storage / video_rel
    if not source.exists():
        raise HTTPException(status_code=404, detail="video no encontrado")

    cover = storage / str(project_id) / "cover.jpg"
    if not cover.exists() or cover.stat().st_mtime < source.stat().st_mtime:
        await _extract_frame(source, cover)
        if not cover.exists():
            raise HTTPException(status_code=500, detail="no se pudo generar la portada")
    return FileResponse(cover, media_type="image/jpeg")
