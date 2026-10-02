from app.providers import register_provider
from app.providers.tts.edge import EdgeTTS

register_provider("tts", "edge", EdgeTTS)

__all__ = ["EdgeTTS"]
