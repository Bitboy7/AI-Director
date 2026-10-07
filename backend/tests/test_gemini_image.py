import base64

import httpx
import pytest

from app.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.providers.image.gemini import GeminiImageProvider

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-data"


def image_interaction_response(model: str) -> dict:
    return {
        "id": "v1_img_1",
        "object": "interaction",
        "model": model,
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "image",
                        "mime_type": "image/png",
                        "data": base64.b64encode(PNG_BYTES).decode(),
                    }
                ],
            }
        ],
    }


def make_provider(
    handler: httpx.AsyncBaseTransport | None = None, credentials: dict | None = None
) -> GeminiImageProvider:
    return GeminiImageProvider(
        credentials=credentials or {"api_key": "test-key"},
        transport=handler or httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )


async def test_generate_returns_png_files_and_uses_default_model():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=image_interaction_response("gemini-3.1-flash-image"))

    provider = make_provider(httpx.MockTransport(handler))
    paths = await provider.generate("un personaje heroico", model=None, style=None, aspect="16:9", count=1)

    assert len(paths) == 1
    assert paths[0].read_bytes() == PNG_BYTES
    assert captured["url"].endswith("/v1beta/interactions")
    assert captured["headers"].get("x-goog-api-key") == "test-key"
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["model"] == "gemini-3.1-flash-image"
    assert body["response_format"]["mime_type"] == "image/jpeg"


async def test_generate_uses_custom_model_style_and_aspect():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=image_interaction_response("gemini-3-pro-image"))

    provider = make_provider(httpx.MockTransport(handler))
    await provider.generate(
        "un personaje", model="gemini-3-pro-image", style="noir", aspect="9:16", count=1
    )

    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["model"] == "gemini-3-pro-image"
    assert body["input"][0]["text"].startswith("noir")
    assert body["response_format"]["aspect_ratio"] == "9:16"


async def test_generate_multiple_images_calls_api_once_per_image():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=image_interaction_response("gemini-3.1-flash-image"))

    provider = make_provider(httpx.MockTransport(handler))
    paths = await provider.generate("personaje", model=None, style=None, aspect="16:9", count=3)

    assert len(calls) == 3
    assert len(paths) == 3


async def test_auth_error_maps_to_provider_auth_error():
    provider = make_provider(
        httpx.MockTransport(lambda request: httpx.Response(401, json={"error": {"message": "no"}}))
    )
    with pytest.raises(ProviderAuthError):
        await provider.generate("x", model=None, style=None, aspect="16:9", count=1)


async def test_rate_limit_maps_to_provider_rate_limit_error():
    provider = make_provider(
        httpx.MockTransport(lambda request: httpx.Response(429, json={"error": {"message": "quota"}}))
    )
    with pytest.raises(ProviderRateLimitError):
        await provider.generate("x", model=None, style=None, aspect="16:9", count=1)


async def test_server_error_maps_to_provider_unavailable_error():
    provider = make_provider(
        httpx.MockTransport(lambda request: httpx.Response(500, json={"error": {"message": "boom"}}))
    )
    with pytest.raises(ProviderUnavailableError):
        await provider.generate("x", model=None, style=None, aspect="16:9", count=1)


async def test_missing_api_key_raises_auth_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError):
        GeminiImageProvider(credentials={})


async def test_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json=image_interaction_response("gemini-3.1-flash-image"))

    provider = GeminiImageProvider(credentials={}, transport=httpx.MockTransport(handler))
    await provider.generate("x", model=None, style=None, aspect="16:9", count=1)
    assert captured["key"] == "env-key"
