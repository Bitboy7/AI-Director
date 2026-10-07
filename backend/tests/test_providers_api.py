async def test_list_providers_endpoint(client):
    r = await client.get("/api/v1/providers")
    assert r.status_code == 200
    providers = r.json()["providers"]
    names = {kind: {item["name"] for item in items} for kind, items in providers.items()}
    assert "ollama" in names["llm"]
    assert "gemini" in names["image"]
    assert "fal" in names["image"]
    assert "mock" in names["video"]
    assert "omni" in names["video"]
    assert "fal" in names["video"]
    assert "edge" in names["tts"]


async def test_providers_configured_without_keys(client):
    r = await client.get("/api/v1/providers")
    data = r.json()["providers"]

    def by_name(items):
        return {item["name"]: item["configured"] for item in items}

    llm = by_name(data["llm"])
    image = by_name(data["image"])
    video = by_name(data["video"])

    assert llm["ollama"] is True
    assert llm["gemini"] is False
    assert llm["openai"] is False
    assert image["gemini"] is False
    assert image["fal"] is False
    assert video["mock"] is True
    assert video["omni"] is False


async def test_providers_configured_with_stored_key(client):
    await client.put(
        "/api/v1/settings/credentials/gemini",
        json={"credentials": {"api_key": "sk-123"}},
    )
    r = await client.get("/api/v1/providers")
    image = {item["name"]: item["configured"] for item in r.json()["providers"]["image"]}
    llm = {item["name"]: item["configured"] for item in r.json()["providers"]["llm"]}
    assert image["gemini"] is True
    assert llm["gemini"] is True


async def test_providers_configured_with_env_key(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    r = await client.get("/api/v1/providers")
    llm = {item["name"]: item["configured"] for item in r.json()["providers"]["llm"]}
    assert llm["openai"] is True


async def test_provider_models_endpoint_mock(client):
    r = await client.get("/api/v1/providers/video/mock/models")
    assert r.status_code == 200
    assert r.json()["models"][0]["id"] == "mock"


async def test_provider_models_endpoint_unknown_returns_empty(client):
    r = await client.get("/api/v1/providers/llm/seedance/models")
    assert r.status_code == 200
    assert r.json()["models"] == []