from app.providers import register_provider
from app.providers.llm.ollama import OllamaLLM

register_provider("llm", "ollama", OllamaLLM)

__all__ = ["OllamaLLM"]
