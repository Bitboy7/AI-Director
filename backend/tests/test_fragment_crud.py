from sqlalchemy import select

from app.models import DialogueLine, Fragment, StoryboardPanel


async def _episode(client) -> tuple[int, int]:
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    return pid, r.json()["id"]


async def test_create_fragment(client):
    _pid, eid = await _episode(client)
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments",
        json={"shot_number": 1, "time_place": "Calle", "duration": 8, "prompt_video": "algo"},
    )
    assert r.status_code == 200
    assert r.json()["shot_number"] == 1

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    assert len(r.json()) == 1


async def test_delete_fragment_cascades(client, db_session):
    _pid, eid = await _episode(client)
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments", json={"shot_number": 1, "duration": 10}
    )
    fid = r.json()["id"]
    await client.post(
        f"/api/v1/fragments/{fid}/storyboard-panels",
        json={"title": "Inicio", "start_seconds": 0, "end_seconds": 4, "prompt": "x"},
    )

    r = await client.delete(f"/api/v1/fragments/{fid}")
    assert r.status_code == 204

    r = await client.get(f"/api/v1/episodes/{eid}/fragments")
    assert r.json() == []

    db_session.expire_all()
    assert (await db_session.get(Fragment, fid)) is None
    panels = (
        await db_session.execute(select(StoryboardPanel).where(StoryboardPanel.fragment_id == fid))
    ).scalars().all()
    assert panels == []
    lines = (
        await db_session.execute(select(DialogueLine).where(DialogueLine.fragment_id == fid))
    ).scalars().all()
    assert lines == []


async def test_delete_missing_fragment_returns_404(client):
    r = await client.delete("/api/v1/fragments/9999")
    assert r.status_code == 404
