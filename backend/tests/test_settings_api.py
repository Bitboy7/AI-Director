from app.models import ProviderCredential
from app.services.credentials import get_credentials


async def test_credentials_crud(client):
    r = await client.put(
        "/api/v1/settings/credentials/seedance",
        json={"credentials": {"api_key": "sk-123", "endpoint": "https://ark.cn"}},
    )
    assert r.status_code == 200

    r = await client.get("/api/v1/settings/credentials")
    assert r.status_code == 200
    assert r.json()["providers"]["seedance"]["api_key"] == "sk-123"

    r = await client.put(
        "/api/v1/settings/credentials/seedance",
        json={"credentials": {"api_key": "nuevo"}},
    )
    assert r.status_code == 200
    r = await client.get("/api/v1/settings/credentials")
    seedance = r.json()["providers"]["seedance"]
    assert "endpoint" not in seedance
    assert seedance["api_key"] == "nuevo"

    r = await client.delete("/api/v1/settings/credentials/seedance/api_key")
    assert r.status_code == 204
    r = await client.get("/api/v1/settings/credentials")
    assert "seedance" not in r.json()["providers"]


async def test_get_credentials_env_fallback(db_session, monkeypatch):
    monkeypatch.setenv("SEEDANCE_API_KEY", "env-key")
    creds = await get_credentials(db_session, "seedance")
    assert creds["api_key"] == "env-key"


async def test_get_credentials_db_overrides_env(db_session, monkeypatch):
    monkeypatch.setenv("SEEDANCE_API_KEY", "env-key")
    db_session.add(ProviderCredential(provider="seedance", key="api_key", value="db-key"))
    await db_session.commit()
    creds = await get_credentials(db_session, "seedance")
    assert creds["api_key"] == "db-key"
