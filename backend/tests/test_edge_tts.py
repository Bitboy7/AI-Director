import shutil
import subprocess

import edge_tts

from app.config import get_settings
from app.providers.tts.edge import EdgeTTS


class FakeCommunicate:
    def __init__(self, source: str):
        self.source = source

    async def save(self, path):
        shutil.copyfile(self.source, path)


async def test_edge_tts_returns_path_and_duration(monkeypatch, tmp_path):
    wav = tmp_path / "two.wav"
    subprocess.run(
        [
            get_settings().ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-ar",
            "16000",
            str(wav),
        ],
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(edge_tts, "Communicate", lambda text, voice: FakeCommunicate(str(wav)))

    result = await EdgeTTS().synthesize("Hola mundo", "es-ES-AlvaroNeural")
    assert result.path.exists()
    assert 1.5 < result.duration_seconds < 2.5
