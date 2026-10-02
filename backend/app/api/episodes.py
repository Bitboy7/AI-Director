from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep
from app.api.projects import get_project_or_404
from app.models import Episode
from app.schemas import EpisodeCreate, EpisodeRead, EpisodeUpdate

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
