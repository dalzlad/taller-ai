from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and the local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TallerAI API"
    environment: str = "development"
    debug: bool = False
    database_url: str = Field(
        default="postgresql+psycopg://tallerai:tallerai@localhost:5432/tallerai"
    )
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    ai_provider: str = "stub"
    openai_api_key: str | None = None
    openai_model: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    vision_api_key: str | None = None
    transcription_api_key: str | None = None
    knowledge_api_key: str | None = None
    storage_path: str = "storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
