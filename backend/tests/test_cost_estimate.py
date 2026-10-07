async def test_cost_estimate_uses_resolution(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}",
        json={
            "settings": {
                "video_model": "google/gemini-omni-flash/v1.1/text-to-video",
                "resolution": "720p",
            }
        },
    )
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    eid = r.json()["id"]
    for shot in (1, 2):
        await client.post(
            f"/api/v1/episodes/{eid}/fragments", json={"shot_number": shot, "duration": 10}
        )

    r = await client.get(f"/api/v1/projects/{pid}/cost-estimate")
    body = r.json()
    assert body["total"]["fragments"] == 2
    assert body["total"]["seconds"] == 20
    assert abs(body["total"]["cost_usd"] - 2.0) < 0.001
    assert body["episodes"][0]["number"] == 1


async def test_cost_estimate_excludes_generated_fragments(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}",
        json={"settings": {"video_model": "google/gemini-omni-flash", "resolution": "360p"}},
    )
    r = await client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1})
    eid = r.json()["id"]
    r = await client.post(
        f"/api/v1/episodes/{eid}/fragments", json={"shot_number": 1, "duration": 10}
    )
    fid = r.json()["id"]
    await client.patch(f"/api/v1/fragments/{fid}", json={"status": "generated"})

    r = await client.get(f"/api/v1/projects/{pid}/cost-estimate")
    assert r.json()["total"]["fragments"] == 0
