import httpx

from app.config import get_settings
from app.providers.base import LLMProvider


class OllamaLLM(LLMProvider):
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.ollama_model
        self._client = httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(300.0))

    async def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        body: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        if json_mode:
            body["format"] = "json"
        response = await self._client.post(f"{self.base_url}/api/chat", json=body)
        if response.status_code == 400 and json_mode and "format" in response.text.lower():
            body.pop("format", None)
            response = await self._client.post(f"{self.base_url}/api/chat", json=body)
        response.raise_for_status()
        return response.json()["message"]["content"]
