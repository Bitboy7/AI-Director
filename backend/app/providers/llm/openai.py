import os

import httpx

from app.providers.base import (
    LLMProvider,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

DEFAULT_OPENAI_ENDPOINT = "https://api.openai.com"
DEFAULT_LLM_MODEL = "gpt-4o-mini"


def _resolve_api_key(credentials: dict) -> str:
    return credentials.get("api_key") or os.environ.get("OPENAI_API_KEY") or ""


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise ProviderAuthError(f"clave de OpenAI rechazada: HTTP {response.status_code}")
    if response.status_code == 429:
        raise ProviderRateLimitError("límite de peticiones de OpenAI alcanzado")
    if response.status_code >= 400:
        raise ProviderUnavailableError(
            f"OpenAI respondió con HTTP {response.status_code}: {response.text[:300]}"
        )


class OpenAILLM(LLMProvider):
    def __init__(
        self,
        credentials: dict | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        creds = credentials or {}
        api_key = _resolve_api_key(creds)
        if not api_key:
            raise ProviderAuthError("falta la API key de OpenAI (provider 'openai')")
        endpoint = (creds.get("endpoint") or DEFAULT_OPENAI_ENDPOINT).rstrip("/")
        self._client = httpx.AsyncClient(
            transport=transport,
            base_url=endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(300.0),
        )
        self.default_model = model or DEFAULT_LLM_MODEL
        self.last_usage: dict[str, int] = {}

    async def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        body: dict = {
            "model": self.default_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        response = await self._client.post("/v1/chat/completions", json=body)
        _raise_for_status(response)
        data = response.json()
        usage = data.get("usage") or {}
        self.last_usage = {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        }
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailableError(
                "OpenAI no devolvió un mensaje válido"
            ) from exc