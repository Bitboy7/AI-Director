import httpx

from app.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


def raise_for_gemini_status(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise ProviderAuthError(f"clave de Gemini rechazada: HTTP {response.status_code}")
    if response.status_code == 429:
        raise ProviderRateLimitError("límite de peticiones de Gemini alcanzado")
    if response.status_code >= 400:
        raise ProviderUnavailableError(
            f"Gemini respondió con HTTP {response.status_code}: {response.text[:300]}"
        )


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            transport=transport,
            base_url=self.base_url,
            headers={"x-goog-api-key": api_key},
            timeout=httpx.Timeout(300.0),
        )

    async def post_interaction(self, payload: dict) -> dict:
        response = await self._client.post("/v1beta/interactions", json=payload)
        raise_for_gemini_status(response)
        return response.json()

    async def get_interaction(self, interaction_id: str) -> dict:
        response = await self._client.get(f"/v1beta/interactions/{interaction_id}")
        raise_for_gemini_status(response)
        return response.json()

    async def get_file(self, file_id: str) -> dict:
        response = await self._client.get(f"/v1beta/files/{file_id}")
        raise_for_gemini_status(response)
        return response.json()

    async def download_bytes(self, url: str) -> bytes:
        response = await self._client.get(url)
        raise_for_gemini_status(response)
        return response.content
