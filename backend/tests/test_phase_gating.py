async def test_phase_ordering(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]

    r = await client.put(f"/api/v1/projects/{pid}/phases/2", json={"completed": True})
    assert r.status_code == 400

    r = await client.put(f"/api/v1/projects/{pid}/phases/4", json={"completed": True})
    assert r.status_code == 400

    r = await client.put(f"/api/v1/projects/{pid}/phases/1", json={"completed": True})
    assert r.status_code == 200
    assert r.json()["settings"]["completed_phases"] == [1]

    r = await client.put(f"/api/v1/projects/{pid}/phases/2", json={"completed": True})
    assert r.status_code == 200
    assert r.json()["settings"]["completed_phases"] == [1, 2]

    r = await client.put(f"/api/v1/projects/{pid}/phases/1", json={"completed": False})
    assert r.status_code == 400

    r = await client.put(f"/api/v1/projects/{pid}/phases/2", json={"completed": False})
    assert r.status_code == 200
    assert r.json()["settings"]["completed_phases"] == [1]

    r = await client.put(f"/api/v1/projects/{pid}/phases/1", json={"completed": False})
    assert r.status_code == 200
    assert r.json()["settings"]["completed_phases"] == []
