import httpx
import pytest

from app.providers.base import ProviderAuthError, ProviderRateLimitError, ProviderUnavailableError
from app.providers.llm.openai import OpenAILLM


def make_provider(handler, credentials=None):
    return OpenAILLM(
        credentials=credentials or {"api_key": "test-key"},
        transport=httpx.MockTransport(handler),
    )


async def test_complete_sends_chat_request_with_json_mode():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": '{"ok": 1}'}}]},
        )

    provider = make_provider(handler)
    result = await provider.complete("sistema", "usuario", json_mode=True)

    assert result == '{"ok": 1}'
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["headers"].get("authorization") == "Bearer test-key"
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["model"] == "gpt-4o-mini"
    assert body["messages"][0] == {"role": "system", "content": "sistema"}
    assert body["messages"][1] == {"role": "user", "content": "usuario"}
    assert body["response_format"] == {"type": "json_object"}


async def test_complete_without_json_mode_omits_response_format():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "hola"}}]}
        )

    provider = make_provider(handler)
    await provider.complete("s", "u", json_mode=False)
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert "response_format" not in body


async def test_custom_endpoint_and_model():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "x"}}]}
        )

    provider = OpenAILLM(
        credentials={"api_key": "k", "endpoint": "https://proxy.example.com"},
        model="gpt-4.1",
        transport=httpx.MockTransport(handler),
    )
    await provider.complete("s", "u", json_mode=False)
    assert captured["url"] == "https://proxy.example.com/v1/chat/completions"
    assert httpx.Response(200, content=captured["body"].encode()).json()["model"] == "gpt-4.1"


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
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError):
        OpenAILLM(credentials={})


async def test_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["key"] = request.headers.get("authorization")
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "x"}}]}
        )

    provider = OpenAILLM(credentials={}, transport=httpx.MockTransport(handler))
    await provider.complete("s", "u", json_mode=False)
    assert captured["key"] == "Bearer env-key"