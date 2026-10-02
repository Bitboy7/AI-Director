from collections.abc import Callable
from typing import Any

from app.providers.base import ProviderUnavailableError

_REGISTRY: dict[tuple[str, str], Callable[[], Any]] = {}

_DEFAULT_PROVIDERS = {
    "llm": "ollama",
    "image": "upload",
    "video": "mock",
    "tts": "edge",
}


def register_provider(kind: str, name: str, factory: Callable[[], Any]) -> None:
    _REGISTRY[(kind, name)] = factory


def get_provider(kind: str, name: str | None = None) -> Any:
    resolved = name or _DEFAULT_PROVIDERS.get(kind)
    if resolved is None:
        raise ProviderUnavailableError(f"no default provider for kind '{kind}'")
    factory = _REGISTRY.get((kind, resolved))
    if factory is None:
        raise ProviderUnavailableError(f"provider '{kind}/{resolved}' not registered")
    return factory()


def list_providers(kind: str) -> list[str]:
    return sorted(name for (k, name) in _REGISTRY if k == kind)
