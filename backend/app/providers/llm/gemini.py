import os

import httpx

from app.providers.base import LLMProvider, ProviderAuthError
from app.providers.gemini_client import GeminiClient

DEFAULT_LLM_MODEL = "gemini-3.8-flash"


def _resolve_api_key(credentials: dict) -> str:
    return (
        credentials.get("api_key")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )


def _extract_text(interaction: dict) -> str:
    parts: list[str] = []
    for step in interaction.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for item in step.get("content", []):
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
    return "".join(parts)


class GeminiLLM(LLMProvider):
    def __init__(
        self,
        credentials: dict | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        creds = credentials or {}
        api_key = _resolve_api_key(creds)
        if not api_key:
            raise ProviderAuthError("falta la API key de Gemini (provider 'gemini')")
        self.client = GeminiClient(api_key, base_url=creds.get("endpoint"), transport=transport)
        self.default_model = model or DEFAULT_LLM_MODEL
        self.last_usage: dict[str, int] = {}

    async def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        payload: dict = {
            "model": self.default_model,
            "input": user,
        }
        if system:
            payload["system_instruction"] = system
        if json_mode:
            payload["response_format"] = {"type": "object"}
        interaction = await self.client.post_interaction(payload)
        usage = interaction.get("usage") or interaction.get("usage_metadata") or {}
        self.last_usage = {
            "input_tokens": int(
                usage.get("input_tokens") or usage.get("prompt_token_count") or 0
            ),
            "output_tokens": int(
                usage.get("output_tokens") or usage.get("candidates_token_count") or 0
            ),
        }
        return _extract_text(interaction)