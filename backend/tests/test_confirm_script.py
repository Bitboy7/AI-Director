from app.schemas.script import (
    ScriptCharacter,
    ScriptDialogue,
    ScriptDraft,
    ScriptEpisode,
    ScriptScene,
    ScriptShot,
)


def _draft_dict() -> dict:
    return ScriptDraft(
        synopsis="Un drama",
        characters=[ScriptCharacter(name="Kai", description="hacker")],
        scenes=[ScriptScene(name="Calle", description="calle nocturna")],
        props=[],
        episodes=[
            ScriptEpisode(
                number=1,
                title="Piloto",
                shots=[
                    ScriptShot(
                        shot_number=1,
                        time_place="Calle",
                        cast=["Kai"],
                        action="Kai camina",
                        dialogues=[ScriptDialogue(character="Kai", text="Hola")],
                    )
                ],
            )
        ],
    ).model_dump()


async def test_confirm_script_without_draft_returns_400(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/confirm-script")
    assert r.status_code == 400


async def test_confirm_script_is_idempotent(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}", json={"settings": {"script_draft": _draft_dict()}}
    )

    await client.post(f"/api/v1/projects/{pid}/confirm-script")
    await client.post(f"/api/v1/projects/{pid}/confirm-script")

    r = await client.get(f"/api/v1/projects/{pid}/episodes")
    assert len(r.json()) == 1
    assert len(r.json()[0]["fragments"]) == 1
    r = await client.get(f"/api/v1/projects/{pid}/resources")
    names = sorted(resource["name"] for resource in r.json())
    assert names == ["Calle", "Kai"]
