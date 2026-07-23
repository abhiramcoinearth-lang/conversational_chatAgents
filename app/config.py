from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_host: str = "0.0.0.0"
    app_port: int = 5000
    debug: bool = True

    # Gemini LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Phase 2
    chroma_persist_dir: str = "./data/chromadb"
    embedding_model: str = "all-MiniLM-L6-v2"

    # Base URL only
    translation_url: str = "https://translate.chatbucket.chat"

    # Phase 3
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/chatagent"
    api_secret_key: str = "change-this-secret"
    rate_limit: str = "60/minute"
    max_memory_turns: int = 20

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()   