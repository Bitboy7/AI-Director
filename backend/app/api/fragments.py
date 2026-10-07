import time
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import SessionDep
from app.api.episodes import get_episode_or_404
from app.jobs import queue as queue_module
from app.models import (
    AssetKind,
    DialogueLine,
    Episode,
    Fragment,
    FragmentReferenceImage,
    FragmentVideo,
    ImageOrigin,
    Job,
    JobStatus,
    JobType,
    Project,
    StoryboardPanel,
)
from app.providers import default_provider, get_provider
from app.providers.base import ProviderAuthError, ProviderError, ProviderRateLimitError
from app.schemas import (
    FragmentCreate,
    FragmentRead,
    FragmentReferenceImageRead,
    FragmentUpdate,
    JobRead,
    StoryboardPanelCreate,
    StoryboardPanelRead,
    StoryboardPanelUpdate,
)
from app.services.credentials import get_credentials
from app.services.storage import save_generated, save_upload
from app.services.storyboards import fragment_prompt
from app.services.styles import style_prompt
from app.services.usage import record_api_call

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


@router.delete("/fragments/{fragment_id}", status_code=204)
async def delete_fragment(fragment_id: int, session: SessionDep):
    fragment = await get_fragment_or_404(session, fragment_id)
    await session.delete(fragment)
    await session.commit()


@router.patch("/storyboard-panels/{panel_id}", response_model=StoryboardPanelRead)
async def update_storyboard_panel(
    panel_id: int, payload: StoryboardPanelUpdate, session: SessionDep
):
    panel = await session.get(StoryboardPanel, panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail="storyboard panel not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(panel, field, value)
    await session.commit()
    await session.refresh(panel)
    return panel


MAX_STORYBOARD_PANELS = 4


@router.post(
    "/fragments/{fragment_id}/storyboard-panels", response_model=StoryboardPanelRead
)
async def create_storyboard_panel(
    fragment_id: int, payload: StoryboardPanelCreate, session: SessionDep
):
    await get_fragment_or_404(session, fragment_id)
    existing = (
        await session.execute(
            select(StoryboardPanel).where(StoryboardPanel.fragment_id == fragment_id)
        )
    ).scalars().all()
    if len(existing) >= MAX_STORYBOARD_PANELS:
        raise HTTPException(
            status_code=400,
            detail=f"máximo {MAX_STORYBOARD_PANELS} storyboards por fragmento",
        )
    panel = StoryboardPanel(
        fragment_id=fragment_id,
        order=len(existing),
        title=payload.title,
        start_seconds=payload.start_seconds,
        end_seconds=payload.end_seconds,
        prompt=payload.prompt,
    )
    session.add(panel)
    await session.commit()
    await session.refresh(panel)
    return panel


@router.delete("/storyboard-panels/{panel_id}", status_code=204)
async def delete_storyboard_panel(panel_id: int, session: SessionDep):
    panel = await session.get(StoryboardPanel, panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail="storyboard panel not found")
    await session.delete(panel)
    await session.commit()


async def _fragment_project(session: SessionDep, fragment: Fragment) -> Project:
    episode = await session.get(Episode, fragment.episode_id)
    project = await session.get(Project, episode.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.post(
    "/fragments/{fragment_id}/reference-images/generate",
    response_model=FragmentReferenceImageRead,
)
async def generate_fragment_reference(fragment_id: int, session: SessionDep):
    fragment = await get_fragment_or_404(session, fragment_id)
    project = await _fragment_project(session, fragment)
    provider_name = (project.settings or {}).get("image_provider") or default_provider("image")
    credentials = await get_credentials(session, provider_name)
    prompt = fragment_prompt(fragment)
    started = time.monotonic()
    try:
        provider = get_provider("image", provider_name, credentials=credentials)
        paths = await provider.generate(
            prompt,
            model=(project.settings or {}).get("image_model") or None,
            style=style_prompt(project.video_style) or None,
            aspect=project.aspect_ratio or "16:9",
            count=1,
        )
    except ProviderAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ProviderRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    rel = await save_generated(session, project.id, AssetKind.image, paths[0])
    image = FragmentReferenceImage(
        fragment_id=fragment_id, path=rel, origin=ImageOrigin.generated
    )
    session.add(image)
    record_api_call(
        session,
        kind="image",
        provider=provider_name,
        model=(project.settings or {}).get("image_model") or "",
        duration_ms=(time.monotonic() - started) * 1000,
        project_id=project.id,
        units=len(paths),
    )
    await session.commit()
    await session.refresh(image)
    return image


@router.post(
    "/fragments/{fragment_id}/reference-images",
    response_model=FragmentReferenceImageRead,
)
async def upload_fragment_reference(
    fragment_id: int, session: SessionDep, file: UploadFile = File(...)
):
    fragment = await get_fragment_or_404(session, fragment_id)
    project = await _fragment_project(session, fragment)
    try:
        rel, _asset = await save_upload(session, project.id, AssetKind.image, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    image = FragmentReferenceImage(
        fragment_id=fragment_id, path=rel, origin=ImageOrigin.uploaded
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


@router.post(
    "/fragments/{fragment_id}/videos/{video_id}/select", response_model=FragmentRead
)
async def select_fragment_video(fragment_id: int, video_id: int, session: SessionDep):
    fragment = await get_fragment_or_404(session, fragment_id)
    video = await session.get(FragmentVideo, video_id)
    if video is None or video.fragment_id != fragment_id:
        raise HTTPException(status_code=404, detail="video not found")
    fragment.video_path = video.path
    await session.commit()
    return await load_fragment(session, fragment_id)


@router.post("/fragments/{fragment_id}/generate", response_model=JobRead, status_code=202)
async def generate_fragment(fragment_id: int, session: SessionDep):
    fragment = await get_fragment_or_404(session, fragment_id)
    job = Job(
        type=JobType.video_gen,
        status=JobStatus.queued,
        payload={"fragment_id": fragment_id},
    )
    session.add(job)
    await session.commit()
    try:
        await queue_module.enqueue("video", "run_video_gen", job.id)
    except queue_module.QueueUnavailableError as exc:
        job.status = JobStatus.failed
        job.error = "queue_unavailable"
        job.updated_at = datetime.now()
        await session.commit()
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    return job
