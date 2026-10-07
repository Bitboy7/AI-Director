import asyncio
import base64
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx

from app.providers.base import (
    ProviderAuthError,
    ProviderUnavailableError,
    VideoProvider,
    VideoSubmitPayload,
    VideoTaskStatus,
)
from app.providers.gemini_client import GeminiClient

DEFAULT_VIDEO_MODEL = "gemini-omni-1.1-flash"

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _mime_for(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")


def _resolve_api_key(credentials: dict) -> str:
    return (
        credentials.get("api_key")
        or os.environ.get("OMNI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )


def _file_id_from_uri(uri: str) -> str:
    marker = "/files/"
    rest = uri.split(marker, 1)[1]
    return rest.split(":", 1)[0].split("?", 1)[0]


def _extract_video_content(interaction: dict) -> dict | None:
    for step in interaction.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for item in step.get("content", []):
            if item.get("type") == "video":
                return item
    return None


class OmniVideoProvider(VideoProvider):
    def __init__(
        self,
        credentials: dict | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        creds = credentials or {}
        api_key = _resolve_api_key(creds)
        if not api_key:
            raise ProviderAuthError("falta la API key de Gemini (provider 'omni')")
        self.client = GeminiClient(api_key, base_url=creds.get("endpoint"), transport=transport)
        self.model = model or DEFAULT_VIDEO_MODEL
        self._tmp = Path(tempfile.mkdtemp(prefix="omni-video-"))

    async def submit(self, payload: VideoSubmitPayload) -> str:
        text = f"{payload.style}. {payload.prompt}" if payload.style else payload.prompt
        refs = payload.reference_images[:2]
        if refs:
            task = "image_to_video"
            input_parts: list[dict] = [
                {
                    "type": "image",
                    "data": base64.b64encode(ref.read_bytes()).decode(),
                    "mime_type": _mime_for(ref),
                }
                for ref in refs
            ]
            input_parts.append({"type": "text", "text": text})
            input_value: str | list[dict] = input_parts
        else:
            task = "text_to_video"
            input_value = text

        duration = min(max(payload.duration_seconds, 3), 10)
        body = {
            "model": self.model,
            "input": input_value,
            "background": True,
            "generation_config": {"video_config": {"task": task}},
            "response_format": {
                "type": "video",
                "aspect_ratio": payload.aspect_ratio or "16:9",
                "resolution": payload.resolution or "720p",
                "duration": f"{duration}s",
            },
        }
        interaction = await self.client.post_interaction(body)
        interaction_id = interaction.get("id")
        if not interaction_id:
            raise ProviderUnavailableError("Gemini no devolvió un id de interacción")
        return interaction_id

    async def poll(self, task_id: str) -> VideoTaskStatus:
        interaction = await self.client.get_interaction(task_id)
        status = interaction.get("status")
        if status == "failed":
            return VideoTaskStatus(state="failed", error="Gemini Omni no pudo generar el video")
        if status != "completed":
            return VideoTaskStatus(state="processing")

        video = _extract_video_content(interaction)
        if video is None:
            return VideoTaskStatus(state="failed", error="la respuesta no contiene video")
        if video.get("data"):
            out = self._tmp / f"{uuid4().hex}.mp4"
            out.write_bytes(base64.b64decode(video["data"]))
            return VideoTaskStatus(state="succeeded", video_url=str(out))
        uri = video.get("uri")
        if uri:
            if not await self._wait_file_active(uri):
                return VideoTaskStatus(
                    state="failed", error="el video no quedó disponible en Gemini"
                )
            return VideoTaskStatus(state="succeeded", video_url=uri)
        return VideoTaskStatus(state="failed", error="el video no contiene datos")

    async def _wait_file_active(self, uri: str) -> bool:
        file_id = _file_id_from_uri(uri)
        for _ in range(60):
            info = await self.client.get_file(file_id)
            state = info.get("state", "")
            if state == "ACTIVE":
                return True
            if state == "FAILED":
                return False
            await asyncio.sleep(5)
        return False

    async def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if url.startswith(("http://", "https://")):
            dest.write_bytes(await self.client.download_bytes(url))
        else:
            shutil.copyfile(url, dest)
        return dest
