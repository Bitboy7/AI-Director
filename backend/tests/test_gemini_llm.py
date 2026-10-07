import httpx
import pytest

from app.providers.base import ProviderAuthError, ProviderRateLimitError, ProviderUnavailableError
from app.providers.llm.gemini import GeminiLLM


def text_interaction_response(text: str) -> dict:
    return {
        "id": "v1_x",
        "object": "interaction",
        "model": "gemini-3.8-flash",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def make_provider(handler, credentials=None):
    return GeminiLLM(
        credentials=credentials or {"api_key": "test-key"},
        transport=httpx.MockTransport(handler),
    )


async def test_complete_sends_system_user_and_json_mode():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=text_interaction_response('{"ok": true}'))

    provider = make_provider(handler)
    result = await provider.complete("sistema", "usuario", json_mode=True)

    assert result == '{"ok": true}'
    assert captured["url"].endswith("/v1beta/interactions")
    assert captured["headers"].get("x-goog-api-key") == "test-key"
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["model"] == "gemini-3.8-flash"
    assert body["system_instruction"] == "sistema"
    assert body["input"] == "usuario"
    assert body["response_format"] == {"type": "object"}


async def test_complete_without_json_mode_omits_response_format():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=text_interaction_response("hola"))

    provider = make_provider(handler)
    await provider.complete("s", "u", json_mode=False)
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert "response_format" not in body


async def test_custom_model_from_constructor():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=text_interaction_response("x"))

    provider = GeminiLLM(
        credentials={"api_key": "k"},
        model="gemini-3.8-flash",
        transport=httpx.MockTransport(handler),
    )
    await provider.complete("s", "u", json_mode=False)
    assert httpx.Response(200, content=captured["body"].encode()).json()["model"] == "gemini-3.8-flash"


async def test_auth_error_maps_to_provider_auth_error():
    provider = make_provider(lambda request: httpx.Response(401, json={}))
    with pytest.raises(ProviderAuthError):
        await provider.complete("s", "u", json_mode=False)


async def test_rate_limit_maps_to_provider_rate_limit_error():
    provider = make_provider(lambda request: httpx.Response(429, json={}))
    with pytest.raises(ProviderRateLimitError):
        await provider.complete("s", "u", json_mode=False)


async def test_server_error_maps_to_provider_unavailable_error():
    provider = make_provider(lambda request: httpx.Response(500, json={}))
    with pytest.raises(ProviderUnavailableError):
        await provider.complete("s", "u", json_mode=False)


async def test_missing_api_key_raises_auth_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError):
        GeminiLLM(credentials={})


async def test_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json=text_interaction_response("x"))

    provider = GeminiLLM(credentials={}, transport=httpx.MockTransport(handler))
    await provider.complete("s", "u", json_mode=False)
    assert captured["key"] == "env-key"