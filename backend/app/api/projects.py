from datetime import datetime

from fastapi import APIRouter, Body, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep
from app.jobs import queue as queue_module
from app.models import Job, JobStatus, JobType, Project
from app.schemas import JobRead, ProjectCreate, ProjectRead, ProjectUpdate, ScriptGenerationRequest

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
