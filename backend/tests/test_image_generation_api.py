import tempfile
from pathlib import Path
from uuid import uuid4

from app.models import ImageOrigin, ReferenceImage
from app.providers import register_provider
from app.providers.base import ProviderAuthError, ProviderRateLimitError


class _FakeImage:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, model, style, aspect, count):
        self.calls.append(
            {"prompt": prompt, "model": model, "style": style, "aspect": aspect, "count": count}
        )
        paths = []
        for _ in range(count):
            path = Path(tempfile.mkdtemp(prefix="fake-img-")) / f"{uuid4().hex}.png"
            path.write_bytes(b"fake-png")
            paths.append(path)
        return paths


async def _setup_variant(client):
    r = await client.post("/api/v1/projects", json={"name": "P", "aspect_ratio": "9:16"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}", json={"settings": {"image_provider": "fake_img"}}
    )
    r = await client.post(
        f"/api/v1/projects/{pid}/resources", json={"type": "character", "name": "Kai"}
    )
    rid = r.json()["id"]
    r = await client.post(
        f"/api/v1/resources/{rid}/variants",
        json={"name": "Base", "description": "joven hacker con chaqueta neón"},
    )
    return pid, r.json()["id"]


async def test_generate_image_uses_variant_description(client, db_session):
    fake = _FakeImage()
    register_provider("image", "fake_img", lambda credentials=None: fake)
    __pid, vid = await _setup_variant(client)

    r = await client.post(f"/api/v1/variants/{vid}/images/generate", json={})
    assert r.status_code == 200
    images = r.json()
    assert len(images) == 1
    assert images[0]["origin"] == "generated"

    call = fake.calls[0]
    assert call["prompt"] == "joven hacker con chaqueta neón"
    assert call["aspect"] == "9:16"
    assert call["count"] == 1

    result = await db_session.execute(
        ReferenceImage.__table__.select().where(ReferenceImage.variant_id == vid)
    )
    rows = result.all()
    assert len(rows) == 1
    assert rows[0].origin == ImageOrigin.generated
    assert Path(rows[0].path).name.endswith(".png")


async def test_generate_image_with_custom_prompt_and_count(client, db_session):
    fake = _FakeImage()
    register_provider("image", "fake_img", lambda credentials=None: fake)
    _pid, vid = await _setup_variant(client)

    r = await client.post(
        f"/api/v1/variants/{vid}/images/generate",
        json={"prompt": "héroe con espada", "count": 2, "style": "noir", "model": "custom-model"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 2

    call = fake.calls[0]
    assert call["prompt"] == "héroe con espada"
    assert call["style"] == "noir"
    assert call["model"] == "custom-model"
    assert call["count"] == 2


async def test_generate_image_requires_prompt_or_description(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/resources", json={"type": "scene", "name": "Calle"})
    rid = r.json()["id"]
    r = await client.post(f"/api/v1/resources/{rid}/variants", json={"name": "V"})
    vid = r.json()["id"]

    r = await client.post(f"/api/v1/variants/{vid}/images/generate", json={})
    assert r.status_code == 400


async def test_generate_image_maps_auth_error_to_502(client):
    class _AuthFail:
        async def generate(self, prompt, model, style, aspect, count):
            raise ProviderAuthError("clave inválida")

    register_provider("image", "fake_img", lambda credentials=None: _AuthFail())
    _pid, vid = await _setup_variant(client)

    r = await client.post(f"/api/v1/variants/{vid}/images/generate", json={})
    assert r.status_code == 502
    assert "clave inválida" in r.json()["detail"]


async def test_generate_image_maps_rate_limit_to_429(client):
    class _RateLimited:
        async def generate(self, prompt, model, style, aspect, count):
            raise ProviderRateLimitError("cuota agotada")

    register_provider("image", "fake_img", lambda credentials=None: _RateLimited())
    _pid, vid = await _setup_variant(client)

    r = await client.post(f"/api/v1/variants/{vid}/images/generate", json={})
    assert r.status_code == 429


async def test_generate_image_uses_project_image_model(client):
    fake = _FakeImage()
    register_provider("image", "fake_img", lambda credentials=None, model=None: fake)
    pid, vid = await _setup_variant(client)
    await client.patch(
        f"/api/v1/projects/{pid}",
        json={"settings": {"image_provider": "fake_img", "image_model": "fal-ai/flux/dev"}},
    )

    r = await client.post(f"/api/v1/variants/{vid}/images/generate", json={})
    assert r.status_code == 200
    assert fake.calls[0]["model"] == "fal-ai/flux/dev"
