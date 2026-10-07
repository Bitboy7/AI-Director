import httpx

from app.config import get_settings
from app.providers.llm.openai import DEFAULT_OPENAI_ENDPOINT

DEFAULT_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com"

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


async def verify_gemini(
    credentials: dict[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bool, str]:
    endpoint = (credentials.get("endpoint") or DEFAULT_GEMINI_ENDPOINT).rstrip("/")
    headers = {"x-goog-api-key": credentials.get("api_key", "")}
    try:
        async with httpx.AsyncClient(timeout=5.0, transport=transport) as client:
            response = await client.get(f"{endpoint}/v1beta/models", headers=headers)
            if response.status_code == 200:
                return True, f"Gemini respondiendo en {endpoint}"
            return False, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


async def verify_fal(
    credentials: dict[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bool, str]:
    api_key = credentials.get("api_key", "")
    if not api_key:
        return False, "falta la API key de fal"
    headers = {"Authorization": f"Key {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=5.0, transport=transport) as client:
            response = await client.get(
                "https://api.fal.ai/v1/models", params={"limit": 1}, headers=headers
            )
            if response.status_code == 200:
                return True, "fal respondiendo en api.fal.ai"
            return False, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


async def verify_openai(
    credentials: dict[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bool, str]:
    api_key = credentials.get("api_key", "")
    if not api_key:
        return False, "falta la API key de OpenAI"
    endpoint = (credentials.get("endpoint") or DEFAULT_OPENAI_ENDPOINT).rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=5.0, transport=transport) as client:
            response = await client.get(f"{endpoint}/v1/models", headers=headers)
            if response.status_code == 200:
                return True, f"OpenAI respondiendo en {endpoint}"
            return False, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


VERIFIERS = {
    "ollama": verify_ollama,
    "gemini": verify_gemini,
    "omni": verify_gemini,
    "fal": verify_fal,
    "openai": verify_openai,
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
