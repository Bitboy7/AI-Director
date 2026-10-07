import httpx

from app.services.verification import VERIFIERS, verify_openai


async def test_verify_openai_ok():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"data": []}))
    ok, detail = await verify_openai({"api_key": "k"}, transport=transport)
    assert ok
    assert "OpenAI respondiendo" in detail


async def test_verify_openai_unauthorized():
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={}))
    ok, detail = await verify_openai({"api_key": "k"}, transport=transport)
    assert not ok
    assert "401" in detail


async def test_verify_openai_missing_key():
    ok, detail = await verify_openai({})
    assert not ok
    assert "key" in detail


async def test_verify_openai_sends_bearer_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(200, json={})

    await verify_openai({"api_key": "k"}, transport=httpx.MockTransport(handler))
    assert seen["auth"] == "Bearer k"
    assert seen["url"] == "https://api.openai.com/v1/models"


async def test_verify_openai_connection_error():
    class BoomTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.ConnectError("sin conexión")

    ok, detail = await verify_openai({"api_key": "k"}, transport=BoomTransport())
    assert not ok
    assert "sin conexión" in detail


def test_openai_has_verifier_registered():
    assert "openai" in VERIFIERS