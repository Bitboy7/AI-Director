import httpx

from app.services.verification import VERIFIERS, verify_fal, verify_gemini


async def test_verify_gemini_ok():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"models": []}))
    ok, detail = await verify_gemini({"api_key": "k"}, transport=transport)
    assert ok
    assert "Gemini respondiendo" in detail


async def test_verify_gemini_unauthorized():
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={}))
    ok, detail = await verify_gemini({"api_key": "k"}, transport=transport)
    assert not ok
    assert "401" in detail


async def test_verify_gemini_uses_custom_endpoint():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={})

    await verify_gemini(
        {"api_key": "k", "endpoint": "https://example.com"},
        transport=httpx.MockTransport(handler),
    )
    assert seen["url"] == "https://example.com/v1beta/models"


async def test_verify_gemini_sends_api_key_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json={})

    await verify_gemini({"api_key": "k"}, transport=httpx.MockTransport(handler))
    assert seen["key"] == "k"


async def test_verify_gemini_connection_error():
    class BoomTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.ConnectError("sin conexión")

    ok, detail = await verify_gemini({"api_key": "k"}, transport=BoomTransport())
    assert not ok
    assert "sin conexión" in detail


async def test_verify_fal_ok():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"models": []}))
    ok, detail = await verify_fal({"api_key": "k"}, transport=transport)
    assert ok
    assert "fal" in detail


async def test_verify_fal_missing_key():
    ok, detail = await verify_fal({})
    assert not ok
    assert "key" in detail


async def test_verify_fal_unauthorized():
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={}))
    ok, detail = await verify_fal({"api_key": "k"}, transport=transport)
    assert not ok
    assert "401" in detail


def test_fal_has_verifier_registered():
    assert "fal" in VERIFIERS


def test_gemini_and_omni_have_verifiers_registered():
    assert "gemini" in VERIFIERS
    assert "omni" in VERIFIERS