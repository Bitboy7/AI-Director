import asyncio
import tempfile
from pathlib import Path

import edge_tts

from app.config import get_settings
from app.providers.base import ProviderError, TTSProvider, TTSResult


class EdgeTTS(TTSProvider):
    async def synthesize(self, text: str, voice: str) -> TTSResult:
        settings = get_settings()
        out_dir = Path(tempfile.mkdtemp(prefix="tts-"))
        out_path = out_dir / "voice.mp3"
        try:
            await edge_tts.Communicate(text, voice).save(str(out_path))
        except Exception as exc:
            raise ProviderError(f"edge-tts falló: {exc}") from exc
        duration = await self._probe_duration(settings.ffprobe_path, out_path)
        return TTSResult(path=out_path, duration_seconds=duration)

    async def _probe_duration(self, ffprobe_path: str, path: Path) -> float:
        proc = await asyncio.create_subprocess_exec(
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise ProviderError(f"ffprobe falló: {stderr.decode()}")
        try:
            return float(stdout.decode().strip())
        except ValueError as exc:
            raise ProviderError(f"duración ilegible de ffprobe: {stdout!r}") from exc
