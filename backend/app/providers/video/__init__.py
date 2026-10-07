from app.providers import register_provider
from app.providers.video.fal import FalVideoProvider
from app.providers.video.mock import MockVideoProvider
from app.providers.video.omni import OmniVideoProvider

register_provider("video", "mock", MockVideoProvider)
register_provider("video", "omni", OmniVideoProvider)
register_provider("video", "fal", FalVideoProvider)

__all__ = ["FalVideoProvider", "MockVideoProvider", "OmniVideoProvider"]
