from app.providers import register_provider
from app.providers.image.fal import FalImageProvider
from app.providers.image.gemini import GeminiImageProvider

register_provider("image", "gemini", GeminiImageProvider)
register_provider("image", "fal", FalImageProvider)

__all__ = ["FalImageProvider", "GeminiImageProvider"]
