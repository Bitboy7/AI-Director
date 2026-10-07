import os
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx

from app.providers.base import (
    ImageProvider,
    ProviderAuthError,
    ProviderUnavailableError,
)
from app.providers.fal_client import FalClient, is_arg_error

DEFAULT_IMAGE_MODEL = "fal-ai/flux/dev"

_IMAGE_SIZES = {
    "1:1": "square_hd",
    "16:9": "landscape_16_9",
    "9:16": "portrait_16_9",
    "4:3": "landscape_4_3",
    "3:4": "portrait_4_3",
}

_SUFFIX_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _resolve_api_key(credentials: dict) -> str:
    return (
        credentials.get("api_key")
        or os.environ.get("FAL_API_KEY")
        or os.environ.get("FAL_KEY")
        or ""
    )


def _extract_image_url(data: dict) -> str:
    images = data.get("images") or data.get("data") or []
    if images and isinstance(images[0], dict) and images[0].get("url"):
        return images[0]["url"]
    image = data.get("image")
    if isinstance(image, dict) and image.get("url"):
        return image["url"]
    raise ProviderUnavailableError("la respuesta de fal no contiene imágenes")


def _suffix_for(data: dict, fallback: str = ".png") -> str:
    images = data.get("images") or data.get("data") or []
    if images and isinstance(images[0], dict):
        content_type = images[0].get("content_type") or ""
        return _SUFFIX_BY_CONTENT_TYPE.get(content_type, fallback)
    return fallback


class FalImageProvider(ImageProvider):
    def __init__(
        self,
        credentials: dict | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        creds = credentials or {}
        api_key = _resolve_api_key(creds)
        if not api_key:
            raise ProviderAuthError("falta la API key de fal (provider 'fal')")
        self.client = FalClient(api_key, transport=transport)
        self.default_model = model or DEFAULT_IMAGE_MODEL
        self._tmp = Path(tempfile.mkdtemp(prefix="fal-image-"))

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
        m = model or self.default_model
        args: dict = {"prompt": text}
        size = _IMAGE_SIZES.get(aspect)
        if size:
            args["image_size"] = size
        data = await self._submit_with_fallback(m, args, text)
        url = _extract_image_url(data)
        content = await self.client.download_bytes(url)
        suffix = _suffix_for(data)
        out = self._tmp / f"{uuid4().hex}{suffix}"
        out.write_bytes(content)
        return out

    async def _submit_with_fallback(self, model: str, args: dict, prompt: str) -> dict:
        try:
            return await self.client.run(model, args)
        except ProviderUnavailableError as exc:
            if is_arg_error(str(exc)):
                return await self.client.run(model, {"prompt": prompt})
            raise