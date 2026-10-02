from sqlalchemy import select

from app.models import (
    DialogueLine,
    Episode,
    Fragment,
    Project,
    Resource,
    ResourceType,
    ResourceVariant,
)
from app.schemas.script import ScriptDraft


async def apply_script_draft(session, project: Project, draft: ScriptDraft) -> dict:
    if draft.synopsis:
        project.synopsis = draft.synopsis
    project.status = "scripted"

    variant_by_name: dict[str, int] = {}
    resources_created = 0
    draft_resources = [
        (ResourceType.character, draft.characters),
        (ResourceType.scene, draft.scenes),
        (ResourceType.prop, draft.props),
    ]
    for rtype, items in draft_resources:
        for item in items:
            result = await session.execute(
                select(Resource).where(
                    Resource.project_id == project.id,
                    Resource.type == rtype,
                    Resource.name == item.name,
                )
            )
            resource = result.scalar_one_or_none()
            if resource is None:
                resource = Resource(
                    project_id=project.id,
                    type=rtype,
                    name=item.name,
                    profile={"description": item.description, "tags": item.tags},
                )
                session.add(resource)
                await session.flush()
                resources_created += 1

            var_result = await session.execute(
                select(ResourceVariant.id).where(ResourceVariant.resource_id == resource.id)
            )
            has_variants = var_result.first() is not None
            if not has_variants:
                variant = ResourceVariant(
                    resource_id=resource.id,
                    name="Base Appearance",
                    description=item.description or resource.name,
                )
                session.add(variant)
                await session.flush()
                variant_id = variant.id
            else:
                variant_id = var_result.first()[0]
            variant_by_name[item.name] = variant_id

    fragments_created = 0
    for ep in draft.episodes:
        episode = Episode(
            project_id=project.id,
            number=ep.number,
            title=ep.title,
            script=ep.model_dump(),
            status="scripted",
        )
        session.add(episode)
        await session.flush()
        for shot in ep.shots:
            fragment = Fragment(
                episode_id=episode.id,
                shot_number=shot.shot_number,
                time_place=shot.time_place,
                cast=[
                    {"name": name, "variant_id": variant_by_name.get(name)}
                    for name in shot.cast
                ],
                prompt_video=shot.action,
                duration=10,
            )
            session.add(fragment)
            await session.flush()
            fragments_created += 1
            for order, dialogue in enumerate(shot.dialogues):
                session.add(
                    DialogueLine(
                        fragment_id=fragment.id,
                        character_variant_id=variant_by_name.get(dialogue.character),
                        text=dialogue.text,
                        order=order,
                    )
                )
    return {
        "episodes": len(draft.episodes),
        "fragments": fragments_created,
        "resources": resources_created,
    }
