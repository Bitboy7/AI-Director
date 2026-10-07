from app.models import (
    DialogueLine,
    Episode,
    Fragment,
    Project,
    Resource,
    ResourceType,
)
from app.schemas.script import ScriptDraft


def store_script_draft(project: Project, draft: ScriptDraft) -> dict:
    """Guarda el guion generado como borrador pendiente de confirmar.

    No crea recursos ni episodios: eso ocurre al confirmar el guion.
    """
    settings = dict(project.settings or {})
    settings["script_draft"] = draft.model_dump()
    settings["script_confirmed"] = False
    project.settings = settings
    if draft.synopsis:
        project.synopsis = draft.synopsis
    project.status = "scripted"
    fragments = sum(len(episode.shots) for episode in draft.episodes)
    resources = len(draft.characters) + len(draft.scenes) + len(draft.props)
    return {
        "episodes": len(draft.episodes),
        "fragments": fragments,
        "resources": resources,
        "confirmed": False,
    }


async def materialize_script_draft(session, project: Project, draft: ScriptDraft) -> dict:
    """Crea recursos (nombre+descripción), episodios, fragmentos y diálogos.

    Idempotente: elimina los recursos y episodios existentes del proyecto antes
    de recrearlos, de modo que reconfirmar un guion regenerado no duplica nada.
    """
    for episode in list(project.episodes):
        await session.delete(episode)
    for resource in list(project.resources):
        await session.delete(resource)
    await session.flush()

    resources_created = 0
    draft_resources = [
        (ResourceType.character, draft.characters),
        (ResourceType.scene, draft.scenes),
        (ResourceType.prop, draft.props),
    ]
    for rtype, items in draft_resources:
        for item in items:
            resource = Resource(
                project_id=project.id,
                type=rtype,
                name=item.name,
                profile={"description": item.description, "tags": item.tags},
            )
            session.add(resource)
            resources_created += 1
    await session.flush()

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
                cast=[{"name": name, "variant_id": None} for name in shot.cast],
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
                        character_variant_id=None,
                        text=dialogue.text,
                        order=order,
                    )
                )

    settings = dict(project.settings or {})
    settings["script_confirmed"] = True
    project.settings = settings
    project.status = "scripted"

    return {
        "episodes": len(draft.episodes),
        "fragments": fragments_created,
        "resources": resources_created,
        "confirmed": True,
    }
