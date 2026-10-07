import tempfile
from pathlib import Path
from uuid import uuid4

from app.jobs import queue as queue_module
from app.jobs.tasks import run_resource_image_gen
from app.models import Job, JobStatus, ReferenceImage, Resource
from app.providers import register_provider


class _FakeImage:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, model, style, aspect, count):
        self.calls.append({"prompt": prompt, "model": model, "style": style, "count": count})
        paths = []
        for _ in range(count):
            path = Path(tempfile.mkdtemp(prefix="fake-img-")) / f"{uuid4().hex}.png"
            path.write_bytes(b"fake-png")
            paths.append(path)
        return paths


async def _setup(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}", json={"settings": {"image_provider": "fake_img"}}
    )
    ids = []
    for name in ("Kai", "Calle"):
        r = await client.post(
            f"/api/v1/projects/{pid}/resources",
            json={"type": "character", "name": name, "profile": {"description": f"desc {name}"}},
        )
        ids.append(r.json()["id"])
    return pid, ids


async def test_generate_resource_images_batch(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    fake = _FakeImage()
    register_provider("image", "fake_img", lambda credentials=None: fake)
    pid, ids = await _setup(client)

    r = await client.post(
        f"/api/v1/projects/{pid}/resources/generate-images",
        json={"resource_ids": ids},
    )
    assert r.status_code == 202
    job_id = r.json()["id"]

    await run_resource_image_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded
    assert job.result["generated"] == 2
    assert job.result["failed"] == []

    assert len(fake.calls) == 2
    assert {call["prompt"] for call in fake.calls} == {"desc Kai", "desc Calle"}

    for rid in ids:
        resource = await db_session.get(Resource, rid)
        assert len(resource.variants) == 1
        assert resource.variants[0].name == "Principal"
        images = await db_session.execute(
            ReferenceImage.__table__.select().where(
                ReferenceImage.variant_id == resource.variants[0].id
            )
        )
        assert len(images.all()) == 1


async def test_generate_resource_images_requires_selection(client):
    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/resources/generate-images", json={"resource_ids": []}
    )
    assert r.status_code == 400
