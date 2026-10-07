from collections.abc import Callable
from typing import Any

from app.providers.base import ProviderUnavailableError

_REGISTRY: dict[tuple[str, str], Callable[[], Any]] = {}

_DEFAULT_PROVIDERS = {
    "llm": "ollama",
    "image": "gemini",
    "video": "mock",
    "tts": "edge",
}


def register_provider(kind: str, name: str, factory: Callable[[], Any]) -> None:
    _REGISTRY[(kind, name)] = factory


def default_provider(kind: str) -> str | None:
    return _DEFAULT_PROVIDERS.get(kind)


def _ensure_loaded(kind: str) -> None:
    import importlib

    try:
        importlib.import_module(f"app.providers.{kind}")
    except ModuleNotFoundError:
        pass


def get_provider(kind: str, name: str | None = None, **factory_kwargs: Any) -> Any:
    resolved = name or _DEFAULT_PROVIDERS.get(kind)
    if resolved is None:
        raise ProviderUnavailableError(f"no default provider for kind '{kind}'")
    factory = _REGISTRY.get((kind, resolved))
    if factory is None:
        _ensure_loaded(kind)
        factory = _REGISTRY.get((kind, resolved))
    if factory is None:
        raise ProviderUnavailableError(f"provider '{kind}/{resolved}' not registered")
    return factory(**factory_kwargs) if factory_kwargs else factory()


def list_providers(kind: str) -> list[str]:
    return sorted(name for (k, name) in _REGISTRY if k == kind)


_PROVIDER_KINDS = ("llm", "image", "video", "tts")


def list_all_providers() -> dict[str, list[str]]:
    for kind in _PROVIDER_KINDS:
        _ensure_loaded(kind)
    return {kind: list_providers(kind) for kind in _PROVIDER_KINDS}
