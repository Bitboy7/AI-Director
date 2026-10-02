from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data.db"
    redis_url: str = "redis://localhost:6379"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    storage_dir: Path = Path("./storage")
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    script_gen_retries: int = 3
    max_upload_mb: int = 10
    subtitle_burn_default: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
