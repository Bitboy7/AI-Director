from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models import Project
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate

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
