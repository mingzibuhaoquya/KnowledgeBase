from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    app_name: str = "KnowledgeBase"
    api_v1_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'knowledgebase.db').as_posix()}"
    upload_root: Path = PROJECT_ROOT / "uploads" / "knowledge"
    secret_key: str = "change-me-before-production"
    access_token_expire_minutes: int = 1440
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_provider: str = "mock"
    ocr_provider: str = "stub"
    qdrant_url: str = ""
    qdrant_collection: str = "knowledge_chunks"
    embedding_dimension: int = 64
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5188",
            "http://127.0.0.1:5188",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.database_url.startswith("sqlite:///./"):
        relative_path = settings.database_url.removeprefix("sqlite:///./")
        settings.database_url = f"sqlite:///{(PROJECT_ROOT / relative_path).as_posix()}"
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
