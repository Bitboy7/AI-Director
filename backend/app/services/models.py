import os

import httpx

from app.config import get_settings
from app.providers.base import ProviderAuthError
from app.providers.fal_client import FalClient
from app.providers.gemini_client import DEFAULT_BASE_URL, raise_for_gemini_status
from app.providers.llm.openai import DEFAULT_OPENAI_ENDPOINT

_IMAGE_CATEGORIES = ["text-to-image"]
_VIDEO_CATEGORIES = ["text-to-video", "image-to-video"]

_GEMINI_NON_TEXT = (
    "image",
    "banana",
    "omni",
    "veo",
    "video",
    "transcribe",
    "tts",
    "audio",
    "embedding",
    "embed",
)

_OPENAI_NON_TEXT = (
    "embedding",
    "embed",
    "whisper",
    "tts",
    "audio",
    "dall-e",
    "dall·e",
    "image",
    "moderation",
    "realtime",
    "transcribe",
    "sora",
)

_STATIC_MODELS: dict[tuple[str, str], list[dict]] = {
    ("image", "mock"): [{"id": "mock", "name": "Mock", "description": "Proveedor simulado"}],
    ("video", "mock"): [{"id": "mock", "name": "Mock", "description": "Proveedor simulado"}],
    ("tts", "edge"): [
        {"id": "edge", "name": "Edge-TTS", "description": "Voz gratuita de Microsoft"}
    ],
}


async def _fal_models(
    credentials: dict, kind: str, transport: httpx.AsyncBaseTransport | None
) -> list[dict]:
    api_key = (
        credentials.get("api_key")
        or os.environ.get("FAL_API_KEY")
        or os.environ.get("FAL_KEY")
        or ""
    )
    if not api_key:
        raise ProviderAuthError("falta la API key de fal")
    client = FalClient(api_key, transport=transport)
    categories = _IMAGE_CATEGORIES if kind == "image" else _VIDEO_CATEGORIES
    raw = await client.list_models(categories)
    seen: set[str] = set()
    models: list[dict] = []
    for item in raw:
        endpoint_id = item.get("endpoint_id")
        if not endpoint_id or endpoint_id in seen or item.get("status") == "deprecated":
            continue
        seen.add(endpoint_id)
        metadata = item.get("metadata") or {}
        models.append(
            {
                "id": endpoint_id,
                "name": metadata.get("display_name") or endpoint_id,
                "description": metadata.get("description") or "",
            }
        )
    return models


async def _gemini_models(
    credentials: dict, kind: str, transport: httpx.AsyncBaseTransport | None
) -> list[dict]:
    api_key = (
        credentials.get("api_key")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )
    if not api_key:
        raise ProviderAuthError("falta la API key de Gemini")
    endpoint = (credentials.get("endpoint") or DEFAULT_BASE_URL).rstrip("/")
    async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
        response = await client.get(
            f"{endpoint}/v1beta/models", headers={"x-goog-api-key": api_key}
        )
        raise_for_gemini_status(response)
        data = response.json()

    models: list[dict] = []
    for item in data.get("models", []):
        name = item.get("name", "").split("/")[-1]
        lowered = name.lower()
        if kind == "image" and not ("image" in lowered or "banana" in lowered):
            continue
        if kind == "video" and not ("omni" in lowered or "veo" in lowered or "video" in lowered):
            continue
        if kind == "llm" and any(marker in lowered for marker in _GEMINI_NON_TEXT):
            continue
        models.append(
            {"id": name, "name": item.get("displayName") or name, "description": ""}
        )
    return models


async def _ollama_models(
    kind: str, transport: httpx.AsyncBaseTransport | None
) -> list[dict]:
    url = get_settings().ollama_url.rstrip("/")
    async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
        response = await client.get(f"{url}/api/tags")
        if response.status_code != 200:
            return []
        data = response.json()
    return [
        {"id": item.get("name", ""), "name": item.get("name", ""), "description": ""}
        for item in data.get("models", [])
    ]


async def _openai_models(
    kind: str, credentials: dict, transport: httpx.AsyncBaseTransport | None
) -> list[dict]:
    api_key = credentials.get("api_key") or os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        raise ProviderAuthError("falta la API key de OpenAI")
    endpoint = (credentials.get("endpoint") or DEFAULT_OPENAI_ENDPOINT).rstrip("/")
    async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
        response = await client.get(
            f"{endpoint}/v1/models", headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code in (401, 403):
            raise ProviderAuthError("clave de OpenAI rechazada")
        raise_for_gemini_status(response)
        data = response.json()

    models: list[dict] = []
    for item in data.get("data", []):
        model_id = item.get("id", "")
        if kind == "llm" and any(marker in model_id.lower() for marker in _OPENAI_NON_TEXT):
            continue
        models.append({"id": model_id, "name": model_id, "description": ""})
    return models


async def list_provider_models(
    kind: str,
    provider: str,
    credentials: dict,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[dict]:
    if provider == "fal":
        return await _fal_models(credentials, kind, transport)
    if provider == "gemini":
        return await _gemini_models(credentials, kind, transport)
    if provider == "ollama":
        return await _ollama_models(kind, transport)
    if provider == "openai":
        return await _openai_models(kind, credentials, transport)
    return _STATIC_MODELS.get((kind, provider), [])