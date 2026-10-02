async def test_full_crud_flow(client):
    r = await client.post(
        "/api/v1/projects",
        json={
            "name": "Neon Rebellion",
            "synopsis": "Ciudad futurista",
            "video_style": "cyberpunk",
            "aspect_ratio": "16:9",
        },
    )
    assert r.status_code == 200
    assert r.json()["id"] == 1
    pid = r.json()["id"]

    r = await client.patch(f"/api/v1/projects/{pid}", json={"video_style": "neon"})
    assert r.status_code == 200
    assert r.json()["video_style"] == "neon"

    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "Piloto"})
    assert r.status_code == 200
    eid = r.json()["id"]

    r = await client.post(
        f"/api/v1/projects/{pid}/resources", json={"type": "character", "name": "Kai"}
    )
    assert r.status_code == 200
    rid = r.json()["id"]

    r = await client.post(
        f"/api/v1/resources/{rid}/variants",
        json={"name": "Base Appearance", "description": "chico cyberpunk"},
    )
    assert r.status_code == 200
    vid = r.json()["id"]

    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments",
        json={
            "shot_number": 1,
            "time_place": "Calle, noche",
            "duration": 10,
            "dialogues": [{"character_variant_id": vid, "text": "Hola", "order": 0}],
        },
    )
    assert r.status_code == 200
    fid = r.json()["id"]

    r = await client.get(f"/api/v1/projects/{pid}/episodes")
    assert r.status_code == 200
    assert r.json()[0]["fragments"][0]["dialogue_lines"][0]["text"] == "Hola"

    r = await client.patch(
        f"/api/v1/fragments/{fid}",
        json={
            "prompt_video": "plano cinematográfico",
            "dialogues": [{"character_variant_id": vid, "text": "Adiós", "order": 0}],
        },
    )
    assert r.status_code == 200
    assert r.json()["dialogue_lines"][0]["text"] == "Adiós"

    r = await client.delete(f"/api/v1/resources/{rid}")
    assert r.status_code == 204

    r = await client.delete(f"/api/v1/projects/{pid}")
    assert r.status_code == 204
    r = await client.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404
