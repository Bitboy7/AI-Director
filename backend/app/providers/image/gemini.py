import base64
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx

from app.providers.base import ImageProvider, ProviderAuthError, ProviderUnavailableError
from app.providers.gemini_client import GeminiClient

DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"


def _resolve_api_key(credentials: dict) -> str:
    return (
        credentials.get("api_key")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )


def _extract_image(interaction: dict, client: GeminiClient) -> bytes:
    if interaction.get("status") == "failed":
        raise ProviderUnavailableError("Gemini no pudo generar la imagen")
    for step in interaction.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for item in step.get("content", []):
            if item.get("type") != "image":
                continue
            if item.get("data"):
                return base64.b64decode(item["data"])
            if item.get("uri"):
                return client.download_bytes(item["uri"])
    raise ProviderUnavailableError("la respuesta de Gemini no contiene imagen")


class GeminiImageProvider(ImageProvider):
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
        self.default_model = model or DEFAULT_IMAGE_MODEL
        self._tmp = Path(tempfile.mkdtemp(prefix="gemini-image-"))

    async def generate(
        self,
        prompt: str,
        model: str | None,
        style: str | None,
        aspect: str,
        count: int,
    ) -> list[Path]:
        paths: list[Path] = []
        for _ in range(count):
            paths.append(await self._generate_one(prompt, model, style, aspect))
        return paths

    async def _generate_one(
        self, prompt: str, model: str | None, style: str | None, aspect: str
    ) -> Path:
        text = f"{style}. {prompt}" if style else prompt
        payload = {
            "model": model or self.default_model,
            "input": [{"type": "text", "text": text}],
            "response_format": {
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": aspect,
                "image_size": "2K",
            },
        }
        interaction = await self.client.post_interaction(payload)
        data = _extract_image(interaction, self.client)
        out = self._tmp / f"{uuid4().hex}.jpg"
        out.write_bytes(data)
        return out
