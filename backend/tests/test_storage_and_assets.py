import base64

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


async def _create_variant(client):
    r = await client.post("/api/v1/projects", json={"name": "P", "synopsis": "s"})
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/resources", json={"type": "character", "name": "Kai"}
    )
    rid = r.json()["id"]
    r = await client.post(
        f"/api/v1/resources/{rid}/variants", json={"name": "Base Appearance"}
    )
    return r.json()["id"]


async def test_upload_image_creates_reference_image(client):
    vid = await _create_variant(client)
    r = await client.post(
        f"/api/v1/variants/{vid}/images",
        files={"file": ("kai.png", PNG_1X1, "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["origin"] == "uploaded"
    assert r.json()["path"].endswith(".png")


async def test_upload_rejects_non_image(client):
    vid = await _create_variant(client)
    r = await client.post(
        f"/api/v1/variants/{vid}/images",
        files={"file": ("nota.txt", b"hola", "text/plain")},
    )
    assert r.status_code == 400
    assert "png" in r.json()["detail"].lower() or "archivo" in r.json()["detail"].lower()


async def test_upload_rejects_oversize(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    vid = await _create_variant(client)
    r = await client.post(
        f"/api/v1/variants/{vid}/images",
        files={"file": ("big.png", b"0" * (2 * 1024 * 1024), "image/png")},
    )
    assert r.status_code == 400


async def test_asset_path_traversal_blocked(client):
    r = await client.get("/api/v1/assets/../../data.db")
    assert r.status_code in (400, 404)
    r = await client.get("/api/v1/assets/%2e%2e/%2e%2e/data.db")
    assert r.status_code in (400, 404)


async def test_asset_serves_uploaded_file(client):
    vid = await _create_variant(client)
    r = await client.post(
        f"/api/v1/variants/{vid}/images",
        files={"file": ("kai.png", PNG_1X1, "image/png")},
    )
    rel = r.json()["path"]
    r = await client.get(f"/api/v1/assets/{rel}")
    assert r.status_code == 200
    assert r.content == PNG_1X1
