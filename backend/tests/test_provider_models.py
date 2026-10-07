import httpx
import pytest

from app.providers.base import ProviderAuthError
from app.services.models import list_provider_models


def _fal_handler(captured):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "endpoint_id": "fal-ai/flux/dev",
                        "status": "active",
                        "metadata": {
                            "display_name": "Flux Dev",
                            "category": "text-to-image",
                            "description": "modelo rápido",
                        },
                    },
                    {
                        "endpoint_id": "fal-ai/old-model",
                        "status": "deprecated",
                        "metadata": {"display_name": "Old", "category": "text-to-image", "description": ""},
                    },
                ]
            },
        )

    return handler


async def test_fal_image_models_uses_text_to_image_category():
    captured = {}
    models = await list_provider_models(
        "image", "fal", {"api_key": "k"}, transport=httpx.MockTransport(_fal_handler(captured))
    )

    assert captured["params"]["category"] == "text-to-image"
    assert captured["headers"].get("authorization") == "Key k"
    assert models[0]["id"] == "fal-ai/flux/dev"
    assert models[0]["name"] == "Flux Dev"
    assert all(m["id"] != "fal-ai/old-model" for m in models)


async def test_fal_video_models_uses_video_categories():
    categories = []
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["c"] = request.url.params.get("category")
        categories.append(request.url.params.get("category"))
        if request.url.params.get("category") == "image-to-video":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "endpoint_id": "fal-ai/kling-video/v2.1/pro/text-to-video",
                        "status": "active",
                        "metadata": {"display_name": "Kling 2.1 Pro", "category": "text-to-video", "description": ""},
                    }
                ]
            },
        )

    models = await list_provider_models(
        "video", "fal", {"api_key": "k"}, transport=httpx.MockTransport(handler)
    )

    assert set(categories) == {"text-to-video", "image-to-video"}
    assert models[0]["id"] == "fal-ai/kling-video/v2.1/pro/text-to-video"


async def test_fal_models_requires_api_key():
    with pytest.raises(ProviderAuthError):
        await list_provider_models("image", "fal", {})


async def test_gemini_image_models_filters_by_image():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "models/gemini-3.1-flash-image", "displayName": "Nano Banana 2"},
                    {"name": "models/gemini-3.8-flash", "displayName": "Gemini 3.8"},
                ]
            },
        )

    models = await list_provider_models(
        "image", "gemini", {"api_key": "k"}, transport=httpx.MockTransport(handler)
    )
    ids = [m["id"] for m in models]
    assert ids == ["gemini-3.1-flash-image"]


async def test_gemini_video_models_filters_by_video():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "models/gemini-omni-1.1-flash", "displayName": "Omni"},
                    {"name": "models/gemini-3.8-flash", "displayName": "Flash"},
                ]
            },
        )

    models = await list_provider_models(
        "video", "gemini", {"api_key": "k"}, transport=httpx.MockTransport(handler)
    )
    assert [m["id"] for m in models] == ["gemini-omni-1.1-flash"]


async def test_ollama_models_from_tags(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen2.5:14b"}, {"name": "llama3:8b"}]},
        )

    models = await list_provider_models(
        "llm", "ollama", {}, transport=httpx.MockTransport(handler)
    )
    assert [m["id"] for m in models] == ["qwen2.5:14b", "llama3:8b"]


async def test_gemini_llm_models_filters_to_text_only():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "models/gemini-3.7-flash", "displayName": "Gemini 3.7 Flash"},
                    {"name": "models/gemini-3.5-flash", "displayName": "Gemini 3.5 Flash"},
                    {"name": "models/gemini-3.1-flash-image", "displayName": "Nano Banana 2"},
                    {"name": "models/gemini-omni-1.1-flash", "displayName": "Omni"},
                    {"name": "models/gemini-3.5-transcribe", "displayName": "Transcribe"},
                    {"name": "models/gemini-embedding-001", "displayName": "Embedding"},
                ]
            },
        )

    models = await list_provider_models(
        "llm", "gemini", {"api_key": "k"}, transport=httpx.MockTransport(handler)
    )
    assert [m["id"] for m in models] == ["gemini-3.7-flash", "gemini-3.5-flash"]


async def test_openai_llm_models_filters_non_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4o"},
                    {"id": "gpt-4o-mini"},
                    {"id": "text-embedding-3-small"},
                    {"id": "whisper-1"},
                    {"id": "tts-1"},
                    {"id": "dall-e-3"},
                    {"id": "omni-moderation-latest"},
                ]
            },
        )

    models = await list_provider_models(
        "llm", "openai", {"api_key": "k"}, transport=httpx.MockTransport(handler)
    )
    assert [m["id"] for m in models] == ["gpt-4o", "gpt-4o-mini"]


async def test_openai_llm_models_lists_chat_models():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4o-mini", "object": "model"},
                    {"id": "gpt-4o", "object": "model"},
                ]
            },
        )

    models = await list_provider_models(
        "llm", "openai", {"api_key": "k"}, transport=httpx.MockTransport(handler)
    )

    assert seen["auth"] == "Bearer k"
    assert seen["url"] == "https://api.openai.com/v1/models"
    assert [m["id"] for m in models] == ["gpt-4o-mini", "gpt-4o"]
    assert models[0]["name"] == "gpt-4o-mini"


async def test_openai_models_requires_api_key():
    with pytest.raises(ProviderAuthError):
        await list_provider_models("llm", "openai", {})


async def test_mock_provides_static_models():
    models = await list_provider_models("video", "mock", {})
    assert models[0]["id"] == "mock"


async def test_unknown_provider_returns_empty():
    models = await list_provider_models("llm", "seedance", {})
    assert models == []