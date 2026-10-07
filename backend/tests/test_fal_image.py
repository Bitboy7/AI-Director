import httpx
import pytest

from app.providers.base import ProviderAuthError, ProviderRateLimitError
from app.providers.image.fal import FalImageProvider

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image"
IMAGE_URL = "https://v3.fal.media/files/abc/image.png"


def image_result(url: str = IMAGE_URL) -> dict:
    return {
        "images": [
            {"url": url, "width": 1024, "height": 1024, "content_type": "image/png"}
        ]
    }


def make_provider(handler, credentials=None):
    return FalImageProvider(
        credentials=credentials or {"api_key": "test-key"},
        transport=httpx.MockTransport(handler),
    )


def capture_handler(captured):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=PNG_BYTES)
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=image_result())

    return handler


async def test_generate_returns_png_and_uses_default_model_and_key():
    captured = {}
    provider = make_provider(capture_handler(captured))

    paths = await provider.generate("un dragón", model=None, style=None, aspect="16:9", count=1)

    assert len(paths) == 1
    assert paths[0].read_bytes() == PNG_BYTES
    assert captured["url"] == "https://fal.run/fal-ai/flux/dev"
    assert captured["headers"].get("authorization") == "Key test-key"
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["prompt"] == "un dragón"
    assert body["image_size"] == "landscape_16_9"


async def test_generate_custom_model_style_and_aspect():
    captured = {}
    provider = make_provider(capture_handler(captured))

    await provider.generate(
        "héroe", model="fal-ai/nano-banana-2", style="noir", aspect="9:16", count=1
    )

    assert captured["url"] == "https://fal.run/fal-ai/nano-banana-2"
    body = httpx.Response(200, content=captured["body"].encode()).json()
    assert body["prompt"].startswith("noir.")
    assert body["image_size"] == "portrait_16_9"


async def test_generate_requests_once_per_image():
    run_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=PNG_BYTES)
        run_calls.append(request)
        return httpx.Response(200, json=image_result())

    provider = make_provider(handler)
    paths = await provider.generate("x", model=None, style=None, aspect="1:1", count=3)

    assert len(run_calls) == 3
    assert len(paths) == 3


async def test_retries_with_prompt_only_when_args_rejected():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=PNG_BYTES)
        calls.append(httpx.Response(200, content=request.content.decode()).json())
        if len(calls) == 1:
            return httpx.Response(
                422, json={"detail": "unexpected keyword argument 'image_size'"}
            )
        return httpx.Response(200, json=image_result())

    provider = make_provider(handler)
    paths = await provider.generate("x", model=None, style=None, aspect="16:9", count=1)

    assert len(calls) == 2
    assert "image_size" not in calls[1]
    assert calls[1]["prompt"] == "x"
    assert len(paths) == 1


async def test_auth_error_maps_to_provider_auth_error():
    provider = make_provider(lambda request: httpx.Response(401, json={}))
    with pytest.raises(ProviderAuthError):
        await provider.generate("x", model=None, style=None, aspect="16:9", count=1)


async def test_rate_limit_maps_to_provider_rate_limit_error():
    provider = make_provider(lambda request: httpx.Response(429, json={}))
    with pytest.raises(ProviderRateLimitError):
        await provider.generate("x", model=None, style=None, aspect="16:9", count=1)


async def test_missing_api_key_raises_auth_error(monkeypatch):
    monkeypatch.delenv("FAL_API_KEY", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(ProviderAuthError):
        FalImageProvider(credentials={})


async def test_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("FAL_API_KEY", "env-key")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["key"] = request.headers.get("authorization")
        return httpx.Response(200, json=image_result())

    provider = FalImageProvider(credentials={}, transport=httpx.MockTransport(handler))
    await provider.generate("x", model=None, style=None, aspect="16:9", count=1)
    assert captured["key"] == "Key env-key"