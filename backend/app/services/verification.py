import httpx

from app.config import get_settings

NOT_NEEDED_PROVIDERS = {
    "edge": "Edge-TTS no requiere clave; usa la voz gratuita de Microsoft",
}

MOCK_PROVIDERS = {
    "mock": "Proveedor simulado para pruebas; siempre disponible",
}


async def verify_ollama(credentials: dict[str, str]) -> tuple[bool, str]:
    url = (credentials.get("endpoint") or get_settings().ollama_url).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/api/tags")
            if response.status_code == 200:
                return True, f"Ollama respondiendo en {url}/api/tags"
            return False, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


VERIFIERS = {
    "ollama": verify_ollama,
}


async def verify_provider(provider: str, credentials: dict[str, str]) -> dict:
    if provider in NOT_NEEDED_PROVIDERS:
        return {"status": "not_needed", "detail": NOT_NEEDED_PROVIDERS[provider]}
    if provider in MOCK_PROVIDERS:
        return {"status": "mock", "detail": MOCK_PROVIDERS[provider]}
    verifier = VERIFIERS.get(provider)
    if verifier is None:
        return {
            "status": "unavailable",
            "detail": "verificación no disponible para este proveedor",
        }
    ok, detail = await verifier(credentials)
    return {"status": "ok" if ok else "error", "detail": detail}
