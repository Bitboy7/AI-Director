from app.providers import register_provider
from app.providers.llm.gemini import GeminiLLM
from app.providers.llm.ollama import OllamaLLM
from app.providers.llm.openai import OpenAILLM

register_provider("llm", "ollama", OllamaLLM)
register_provider("llm", "gemini", GeminiLLM)
register_provider("llm", "openai", OpenAILLM)

__all__ = ["GeminiLLM", "OllamaLLM", "OpenAILLM"]