from app.providers import register_provider
from app.providers.video.mock import MockVideoProvider

register_provider("video", "mock", MockVideoProvider)

__all__ = ["MockVideoProvider"]
