from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import DialogueLine, Episode, Fragment, Project


async def test_project_episode_fragment_dialogue_chain(db_session):
    p = Project(name="Neon Rebellion")
    db_session.add(p)
    await db_session.flush()
    e = Episode(project_id=p.id, number=1)
    db_session.add(e)
    await db_session.flush()
    f = Fragment(episode_id=e.id, shot_number=1, duration=10)
    db_session.add(f)
    await db_session.flush()
    d = DialogueLine(fragment_id=f.id, text="Hola", order=0)
    db_session.add(d)
    await db_session.commit()

    ep = (
        await db_session.execute(
            select(Episode)
            .options(selectinload(Episode.fragments).selectinload(Fragment.dialogue_lines))
            .where(Episode.id == e.id)
        )
    ).scalar_one()
    assert ep.fragments[0].shot_number == 1
    assert ep.fragments[0].dialogue_lines[0].text == "Hola"


async def test_delete_project_cascades(db_session):
    p = Project(name="Neon Rebellion")
    db_session.add(p)
    await db_session.flush()
    e = Episode(project_id=p.id, number=1)
    db_session.add(e)
    await db_session.flush()
    f = Fragment(episode_id=e.id, shot_number=1, duration=10)
    db_session.add(f)
    await db_session.commit()

    await db_session.delete(p)
    await db_session.commit()

    assert await db_session.get(Project, p.id) is None
    assert await db_session.get(Episode, e.id) is None
    assert await db_session.get(Fragment, f.id) is None
