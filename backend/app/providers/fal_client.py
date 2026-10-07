import httpx

from app.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

DEFAULT_RUN_URL = "https://fal.run"
DEFAULT_QUEUE_URL = "https://queue.fal.run"
DEFAULT_API_URL = "https://api.fal.ai/v1"

_ARG_ERROR_MARKERS = (
    "unexpected",
    "unknown argument",
    "additional properties",
    "not allowed",
)


def is_arg_error(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _ARG_ERROR_MARKERS)


def raise_for_fal_status(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise ProviderAuthError(
            f"clave de fal rechazada: HTTP {response.status_code} {response.text[:300]}"
        )
    if response.status_code == 429:
        raise ProviderRateLimitError("límite de peticiones de fal alcanzado")
    if response.status_code >= 400:
        raise ProviderUnavailableError(
            f"fal respondió con HTTP {response.status_code}: {response.text[:300]}"
        )


class FalClient:
    def __init__(
        self,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            transport=transport,
            headers={"Authorization": f"Key {api_key}"},
            timeout=httpx.Timeout(300.0),
        )

    async def run(self, model: str, args: dict) -> dict:
        response = await self._client.post(f"{DEFAULT_RUN_URL}/{model}", json=args)
        raise_for_fal_status(response)
        return response.json()

    async def submit_queue(self, model: str, args: dict) -> dict:
        response = await self._client.post(f"{DEFAULT_QUEUE_URL}/{model}", json=args)
        raise_for_fal_status(response)
        return response.json()

    async def poll_status(self, url: str) -> dict:
        response = await self._client.get(url)
        raise_for_fal_status(response)
        return response.json()

    async def fetch_result(self, url: str) -> dict:
        response = await self._client.get(url)
        raise_for_fal_status(response)
        return response.json()

    async def list_models(self, categories: list[str]) -> list[dict]:
        models: list[dict] = []
        for category in categories:
            response = await self._client.get(
                f"{DEFAULT_API_URL}/models",
                params={"category": category, "limit": 50, "status": "active"},
            )
            raise_for_fal_status(response)
            models.extend(response.json().get("models", []))
        return models

    async def download_bytes(self, url: str) -> bytes:
        response = await self._client.get(url)
        raise_for_fal_status(response)
        return response.content