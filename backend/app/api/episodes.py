from datetime import datetime

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import SessionDep
from app.api.projects import get_project_or_404
from app.config import get_settings
from app.jobs import queue as queue_module
from app.models import Episode, Job, JobStatus, JobType
from app.schemas import EpisodeCreate, EpisodeRead, EpisodeUpdate, JobRead

router = APIRouter(prefix="/api/v1")


async def get_episode_or_404(session: SessionDep, episode_id: int) -> Episode:
    episode = await session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return episode


async def load_episode(session: SessionDep, episode_id: int) -> Episode:
    result = await session.execute(select(Episode).where(Episode.id == episode_id))
    return result.scalar_one()


@router.get("/projects/{project_id}/episodes", response_model=list[EpisodeRead])
async def list_episodes(project_id: int, session: SessionDep):
    await get_project_or_404(session, project_id)
    result = await session.execute(
        select(Episode).where(Episode.project_id == project_id).order_by(Episode.number)
    )
    return list(result.scalars())


@router.post("/projects/{project_id}/episodes", response_model=EpisodeRead)
async def create_episode(project_id: int, payload: EpisodeCreate, session: SessionDep):
    await get_project_or_404(session, project_id)
    episode = Episode(project_id=project_id, number=payload.number, title=payload.title)
    session.add(episode)
    await session.commit()
    return await load_episode(session, episode.id)


@router.patch("/episodes/{episode_id}", response_model=EpisodeRead)
async def update_episode(episode_id: int, payload: EpisodeUpdate, session: SessionDep):
    episode = await get_episode_or_404(session, episode_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(episode, field, value)
    await session.commit()
    return await load_episode(session, episode_id)


@router.get("/episodes/{episode_id}/script")
async def get_episode_script(episode_id: int, session: SessionDep):
    episode = await get_episode_or_404(session, episode_id)
    return {"script": episode.script}


@router.post("/episodes/{episode_id}/generate", status_code=202)
async def generate_episode(
    episode_id: int,
    session: SessionDep,
    payload: dict = Body(default={}),
):
    episode = await get_episode_or_404(session, episode_id)
    fragments = sorted(episode.fragments, key=lambda f: f.shot_number)
    if not fragments:
        raise HTTPException(status_code=400, detail="el episodio no tiene fragmentos")
    subtitle_burn = payload.get(
        "subtitle_burn", get_settings().subtitle_burn_default
    )
    project_id = episode.project_id

    existing_video = (
        await session.execute(
            select(Job).where(
                Job.type == JobType.video_gen,
                Job.status.in_([JobStatus.queued, JobStatus.running]),
            )
        )
    ).scalars().all()
    active_fragment_ids = {j.payload.get("fragment_id") for j in existing_video}

    existing_assembly = (
        await session.execute(
            select(Job).where(
                Job.type == JobType.episode_assembly,
                Job.status.in_([JobStatus.queued, JobStatus.running]),
            )
        )
    ).scalars().all()
    active_assembly = next(
        (j for j in existing_assembly if j.payload.get("episode_id") == episode_id),
        None,
    )

    video_job_ids: list[int] = []
    assembly_job = active_assembly
    try:
        for fragment in fragments:
            if fragment.id in active_fragment_ids:
                continue
            job = Job(
                type=JobType.video_gen,
                status=JobStatus.queued,
                payload={"fragment_id": fragment.id},
                project_id=project_id,
            )
            session.add(job)
            await session.flush()
            video_job_ids.append(job.id)
            await queue_module.enqueue("video", "run_video_gen", job.id)
        if assembly_job is None:
            assembly_job = Job(
                type=JobType.episode_assembly,
                status=JobStatus.queued,
                payload={"episode_id": episode_id, "subtitle_burn": subtitle_burn},
                project_id=project_id,
            )
            session.add(assembly_job)
            await session.flush()
            await queue_module.enqueue(
                "assembly", "run_episode_assembly", assembly_job.id
            )
        elif assembly_job.status == JobStatus.queued:
            await queue_module.enqueue(
                "assembly", "run_episode_assembly", assembly_job.id
            )
    except queue_module.QueueUnavailableError as exc:
        for vid in video_job_ids:
            job = await session.get(Job, vid)
            if job:
                job.status = JobStatus.failed
                job.error = "queue_unavailable"
                job.updated_at = datetime.now()
        if assembly_job is not None and assembly_job.status == JobStatus.queued:
            assembly_job.status = JobStatus.failed
            assembly_job.error = "queue_unavailable"
            assembly_job.updated_at = datetime.now()
        await session.commit()
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    await session.commit()
    return {"video_job_ids": video_job_ids, "assembly_job_id": assembly_job.id}


@router.post("/episodes/{episode_id}/assemble", response_model=JobRead, status_code=202)
async def assemble_episode_job(
    episode_id: int,
    session: SessionDep,
    payload: dict = Body(default={}),
):
    episode = await get_episode_or_404(session, episode_id)
    fragments = sorted(episode.fragments, key=lambda f: f.shot_number)
    if not fragments:
        raise HTTPException(status_code=400, detail="el episodio no tiene fragmentos")
    if any(not fragment.video_path for fragment in fragments):
        raise HTTPException(
            status_code=400, detail="faltan planos generados para ensamblar"
        )
    subtitle_burn = payload.get(
        "subtitle_burn", get_settings().subtitle_burn_default
    )

    existing = (
        await session.execute(
            select(Job).where(
                Job.type == JobType.episode_assembly,
                Job.status.in_([JobStatus.queued, JobStatus.running]),
            )
        )
    ).scalars().all()
    active = next(
        (j for j in existing if j.payload.get("episode_id") == episode_id), None
    )
    if active is not None:
        if active.status == JobStatus.queued:
            # Reencola por si el job se perdió de Redis (huérfano). arq deduplica
            # por _job_id, así que si ya está encolado no se duplica.
            try:
                await queue_module.enqueue("assembly", "run_episode_assembly", active.id)
            except queue_module.QueueUnavailableError as exc:
                raise HTTPException(status_code=503, detail="queue_unavailable") from exc
        return active

    job = Job(
        type=JobType.episode_assembly,
        status=JobStatus.queued,
        payload={"episode_id": episode_id, "subtitle_burn": subtitle_burn},
        project_id=episode.project_id,
    )
    session.add(job)
    await session.flush()
    try:
        await queue_module.enqueue("assembly", "run_episode_assembly", job.id)
    except queue_module.QueueUnavailableError as exc:
        job.status = JobStatus.failed
        job.error = "queue_unavailable"
        job.updated_at = datetime.now()
        await session.commit()
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    await session.commit()
    return job


@router.get("/episodes/{episode_id}/final")
async def get_episode_final(
    episode_id: int, session: SessionDep, download: bool = False
):
    episode = await get_episode_or_404(session, episode_id)
    storage = get_settings().storage_dir.resolve()
    final = storage / str(episode.project_id) / "episodes" / str(episode_id) / "final.mp4"
    if not final.exists():
        raise HTTPException(status_code=404, detail="episodio aún no ensamblado")
    if download:
        return FileResponse(
            final,
            media_type="video/mp4",
            filename=f"capitulo-{episode.number}.mp4",
            content_disposition_type="attachment",
        )
    return FileResponse(final)
