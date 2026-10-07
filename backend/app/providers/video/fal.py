import base64
import os
from pathlib import Path

import httpx

from app.providers.base import (
    ProviderAuthError,
    ProviderUnavailableError,
    VideoProvider,
    VideoSubmitPayload,
    VideoTaskStatus,
)
from app.providers.fal_client import FalClient, is_arg_error

DEFAULT_VIDEO_MODEL = "fal-ai/kling-video/v2.1/pro/text-to-video"

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _resolve_api_key(credentials: dict) -> str:
    return (
        credentials.get("api_key")
        or os.environ.get("FAL_API_KEY")
        or os.environ.get("FAL_KEY")
        or ""
    )


def _image_to_video_model(model: str) -> str:
    """Cambia el endpoint text-to-video por su variante image-to-video."""
    if "text-to-video" in model:
        return model.replace("text-to-video", "image-to-video")
    return model


def _to_data_uri(path: Path) -> str:
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _extract_video_url(data: dict) -> str | None:
    video = data.get("video")
    if isinstance(video, dict) and video.get("url"):
        return video["url"]
    for key in ("videos", "data"):
        items = data.get(key)
        if items and isinstance(items, list) and isinstance(items[0], dict) and items[0].get("url"):
            return items[0]["url"]
    url = data.get("url")
    return url if isinstance(url, str) else None


class FalVideoProvider(VideoProvider):
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
        self.default_model = model or DEFAULT_VIDEO_MODEL
        self._tasks: dict[str, dict] = {}

    async def submit(self, payload: VideoSubmitPayload) -> str:
        text = f"{payload.style}. {payload.prompt}" if payload.style else payload.prompt
        args: dict = {"prompt": text}
        if payload.aspect_ratio:
            args["aspect_ratio"] = payload.aspect_ratio
        if payload.duration_seconds:
            args["duration"] = str(payload.duration_seconds)
        if payload.resolution:
            args["resolution"] = payload.resolution

        model = self.default_model
        image = next((p for p in payload.reference_images if p.exists()), None)
        if image is not None:
            # Con imagen de referencia usamos image-to-video y enviamos la imagen.
            model = _image_to_video_model(model)
            args["image_url"] = _to_data_uri(image)

        try:
            data = await self.client.submit_queue(model, args)
        except ProviderUnavailableError as exc:
            if is_arg_error(str(exc)):
                fallback = {"prompt": text}
                if "image_url" in args:
                    fallback["image_url"] = args["image_url"]
                data = await self.client.submit_queue(model, fallback)
            else:
                raise

        request_id = data.get("request_id")
        if not request_id:
            raise ProviderUnavailableError("fal no devolvió un request_id")
        self._tasks[request_id] = {
            "status_url": data.get("status_url"),
            "response_url": data.get("response_url"),
        }
        return request_id

    async def poll(self, task_id: str) -> VideoTaskStatus:
        task = self._tasks.get(task_id)
        if task is None:
            return VideoTaskStatus(state="failed", error="tarea de fal desconocida")
        status = await self.client.poll_status(task["status_url"])
        state = status.get("status")
        if state == "COMPLETED":
            result = await self.client.fetch_result(task["response_url"])
            url = _extract_video_url(result)
            if not url:
                return VideoTaskStatus(
                    state="failed", error="la respuesta de fal no contiene video"
                )
            return VideoTaskStatus(state="succeeded", video_url=url)
        if state in ("IN_QUEUE", "IN_PROGRESS"):
            return VideoTaskStatus(state="processing")
        return VideoTaskStatus(state="failed", error=f"fal reportó estado '{state}'")

    async def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(await self.client.download_bytes(url))
        return dest