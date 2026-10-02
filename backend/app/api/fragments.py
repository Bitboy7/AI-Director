from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep
from app.api.episodes import get_episode_or_404
from app.models import DialogueLine, Fragment
from app.schemas import FragmentCreate, FragmentRead, FragmentUpdate

router = APIRouter(prefix="/api/v1")


async def get_fragment_or_404(session: SessionDep, fragment_id: int) -> Fragment:
    fragment = await session.get(Fragment, fragment_id)
    if fragment is None:
        raise HTTPException(status_code=404, detail="fragment not found")
    return fragment


async def load_fragment(session: SessionDep, fragment_id: int) -> Fragment:
    result = await session.execute(select(Fragment).where(Fragment.id == fragment_id))
    return result.scalar_one()


@router.get("/episodes/{episode_id}/fragments", response_model=list[FragmentRead])
async def list_fragments(episode_id: int, session: SessionDep):
    await get_episode_or_404(session, episode_id)
    result = await session.execute(
        select(Fragment)
        .where(Fragment.episode_id == episode_id)
        .order_by(Fragment.shot_number)
    )
    return list(result.scalars())


@router.post("/episodes/{episode_id}/fragments", response_model=FragmentRead)
async def create_fragment(episode_id: int, payload: FragmentCreate, session: SessionDep):
    await get_episode_or_404(session, episode_id)
    fragment = Fragment(
        episode_id=episode_id,
        shot_number=payload.shot_number,
        time_place=payload.time_place,
        cast=payload.cast,
        prompt_video=payload.prompt_video,
        duration=payload.duration,
    )
    session.add(fragment)
    await session.flush()
    for line in payload.dialogues:
        session.add(
            DialogueLine(
                fragment_id=fragment.id,
                character_variant_id=line.character_variant_id,
                text=line.text,
                order=line.order,
            )
        )
    await session.commit()
    return await load_fragment(session, fragment.id)


@router.patch("/fragments/{fragment_id}", response_model=FragmentRead)
async def update_fragment(fragment_id: int, payload: FragmentUpdate, session: SessionDep):
    fragment = await get_fragment_or_404(session, fragment_id)
    data = payload.model_dump(exclude_unset=True)
    dialogues = data.pop("dialogues", None)
    for field, value in data.items():
        setattr(fragment, field, value)
    if dialogues is not None:
        fragment.dialogue_lines = [
            DialogueLine(
                character_variant_id=line["character_variant_id"],
                text=line["text"],
                order=line["order"],
            )
            for line in dialogues
        ]
    await session.commit()
    return await load_fragment(session, fragment_id)
