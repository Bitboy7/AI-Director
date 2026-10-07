from app.jobs import queue as queue_module
from app.jobs.tasks import run_script_gen
from app.schemas.script import ScriptCharacter, ScriptDraft, ScriptEpisode, ScriptShot
from app.services import scripting
from app.services.usage import estimate_cost


def test_estimate_cost_llm():
    assert estimate_cost("llm", "gpt-4o-mini", 1_000_000, 1_000_000) == 0.75
    assert estimate_cost("llm", "unknown-model", 1000, 1000) == 0.0


def test_estimate_cost_image_and_video():
    assert estimate_cost("image", "gemini-3.1-flash-image", units=1) == 0.04
    assert estimate_cost("video", "gemini-omni-1.1-flash", units=10, resolution="360p") == 0.3
    assert estimate_cost("video", "gemini-omni-1.1-flash", units=10, resolution="720p") == 1.0
    assert estimate_cost("video", "gemini-omni-1.1-flash", units=10, resolution="1080p") == 1.5


async def test_stats_endpoint_empty(client):
    r = await client.get("/api/v1/stats")
    assert r.status_code == 200
    assert r.json()["calls"] == []
    assert r.json()["totals"]["count"] == 0


async def test_script_gen_records_api_call(client, db_session, fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)

    async def fake_generate(provider, req, retries):
        return ScriptDraft(
            synopsis="x",
            characters=[ScriptCharacter(name="Kai", description="")],
            scenes=[],
            props=[],
            episodes=[ScriptEpisode(number=1, title="t", shots=[ScriptShot(shot_number=1)])],
        )

    monkeypatch.setattr(scripting, "generate_script_draft", fake_generate)

    r = await client.post("/api/v1/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/generate-script", json={"synopsis": "x", "num_episodes": 1}
    )
    await run_script_gen({"redis": fake_redis}, r.json()["id"])

    r = await client.get("/api/v1/stats")
    body = r.json()
    assert body["totals"]["count"] == 1
    assert body["calls"][0]["kind"] == "llm"
    assert body["calls"][0]["status"] == "ok"
    assert body["calls"][0]["project_id"] == pid
