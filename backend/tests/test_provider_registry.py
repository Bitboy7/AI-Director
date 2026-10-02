import pytest

from app.providers import get_provider, register_provider
from app.providers.base import ProviderError, ProviderRateLimitError, ProviderUnavailableError


def test_register_and_get_provider():
    class Fake:
        pass

    register_provider("llm", "fake", lambda: Fake())
    assert isinstance(get_provider("llm", "fake"), Fake)


def test_unknown_provider_raises():
    with pytest.raises(ProviderUnavailableError):
        get_provider("video", "noexiste")


def test_error_hierarchy():
    assert issubclass(ProviderRateLimitError, ProviderError)
