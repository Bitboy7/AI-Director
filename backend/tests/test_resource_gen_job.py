from app.jobs import queue as queue_module
from app.jobs.tasks import run_resource_gen
from app.models import Job, JobStatus, ResourceType
from app.schemas.script import ResourcesDraft, ResourceDraft, VariantDraft
from app.services import scripting


async def _setup_project_with_kai(client):
    r = await client.post(
        "/api/v1/projects",
        json={"name": "Neon Rebellion", "synopsis": "historia", "video_style": "cyberpunk"},
    )
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/resources",
        json={
            "type": "character",
            "name": "Kai",
            "profile": {"description": "joven hacker", "tags": ["hero"]},
        },
    )
    rid = r.json()["id"]
    r = await client.post(
        f"/api/v1/resources/{rid}/variants", json={"name": "Base Appearance"}
    )
    return pid


async def test_resource_gen_job_end_to_end(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    pid = await _setup_project_with_kai(client)

    draft = ResourcesDraft(
        resources=[
            ResourceDraft(
                type=ResourceType.character,
                name="Mira",
                description="aliada de Kai",
                variants=[VariantDraft(name="Base Appearance", description="aliada")],
            ),
            ResourceDraft(
                type=ResourceType.character,
                name="Kai",
                description="",
                variants=[
                    VariantDraft(
                        name="Transcendent Guardian", description="forma final"
                    )
                ],
            ),
        ]
    )

    async def fake_generate(provider, script_context, retries):
        return draft

    monkeypatch.setattr(scripting, "generate_resources_draft", fake_generate)

    r = await client.post(f"/api/v1/projects/{pid}/generate-resources", json={})
    assert r.status_code == 202
    job_id = r.json()["id"]

    await run_resource_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded

    r = await client.get(f"/api/v1/projects/{pid}/resources")
    resources = r.json()
    by_name = {res["name"]: res for res in resources}
    assert "Mira" in by_name
    kai = by_name["Kai"]
    variant_names = {v["name"] for v in kai["variants"]}
    assert variant_names == {"Base Appearance", "Transcendent Guardian"}


async def test_resource_gen_job_duplicate_variant_skipped(
    client, db_session, fake_redis, monkeypatch
):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    pid = await _setup_project_with_kai(client)

    draft = ResourcesDraft(
        resources=[
            ResourceDraft(
                type=ResourceType.character,
                name="Kai",
                description="",
                variants=[
                    VariantDraft(name="Base Appearance", description="duplicada")
                ],
            )
        ]
    )

    async def fake_generate(provider, script_context, retries):
        return draft

    monkeypatch.setattr(scripting, "generate_resources_draft", fake_generate)

    r = await client.post(f"/api/v1/projects/{pid}/generate-resources", json={})
    job_id = r.json()["id"]
    await run_resource_gen({"redis": fake_redis}, job_id)

    db_session.expire_all()
    job = await db_session.get(Job, job_id)
    assert job.status == JobStatus.succeeded
    assert any("Base Appearance" in item for item in job.result.get("skipped", []))

    r = await client.get(f"/api/v1/projects/{pid}/resources")
    kai = next(res for res in r.json() if res["name"] == "Kai")
    assert len(kai["variants"]) == 1
