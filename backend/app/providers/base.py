from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ProviderError(Exception):
    """Base error for all provider failures."""


class ProviderAuthError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class VideoSubmitPayload(BaseModel):
    prompt: str
    duration_seconds: int
    aspect_ratio: str = "16:9"
    style: str = ""
    resolution: str | None = None
    reference_images: list[Path] = Field(default_factory=list)


class VideoTaskStatus(BaseModel):
    state: Literal["queued", "processing", "succeeded", "failed"]
    video_url: str | None = None
    error: str | None = None


class TTSResult(BaseModel):
    path: Path
    duration_seconds: float


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        ...


class ImageProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str | None,
        style: str | None,
        aspect: str,
        count: int,
    ) -> list[Path]:
        ...


class VideoProvider(ABC):
    @abstractmethod
    async def submit(self, payload: VideoSubmitPayload) -> str:
        ...

    @abstractmethod
    async def poll(self, task_id: str) -> VideoTaskStatus:
        ...

    @abstractmethod
    async def download(self, url: str, dest: Path) -> Path:
        ...


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str) -> TTSResult:
        ...
