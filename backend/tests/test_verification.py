from app.services import verification


async def test_verify_unknown_provider(client):
    r = await client.post("/api/v1/settings/credentials/seedance/verify")
    assert r.status_code == 200
    assert r.json()["status"] == "unavailable"


async def test_verify_ollama_ok(client, monkeypatch):
    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            self.last_url = url
            return FakeResponse()

    monkeypatch.setattr(verification.httpx, "AsyncClient", FakeClient)

    r = await client.post("/api/v1/settings/credentials/ollama/verify")
    body = r.json()
    assert body["status"] == "ok"
    assert "/api/tags" in body["detail"]


async def test_verify_ollama_down(client, monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            raise ConnectionError("no hay conexion")

    monkeypatch.setattr(verification.httpx, "AsyncClient", FakeClient)

    r = await client.post("/api/v1/settings/credentials/ollama/verify")
    body = r.json()
    assert body["status"] == "error"
    assert "no hay conexion" in body["detail"]


async def test_verify_edge_not_needed(client):
    r = await client.post("/api/v1/settings/credentials/edge/verify")
    assert r.json()["status"] == "not_needed"
