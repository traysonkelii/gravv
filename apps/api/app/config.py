from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"

    database_url: str = "postgresql+asyncpg://gravv_api:gravv_api_local@127.0.0.1:54322/postgres"
    database_url_worker: str = "postgresql+asyncpg://gravv_worker:gravv_worker_local@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_secret: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    app_encryption_key: str = ""

    llm_provider: Literal["anthropic", "openai", "fake"] = "fake"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    transcription_provider: Literal["openai", "deepgram", "fake"] = "fake"
    deepgram_api_key: str = ""

    storage_bucket_voice: str = "voice-notes"
    storage_bucket_exports: str = "exports"
    storage_bucket_avatars: str = "avatars"

    worker_concurrency: int = 4
    worker_poll_interval_seconds: float = 2.0
    rate_limit_per_minute: int = 120
    log_level: str = "INFO"
    sentry_dsn: str = ""

    def model_post_init(self, __context: object) -> None:
        if self.app_env == "test":
            self.llm_provider = "fake"
            self.transcription_provider = "fake"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def auth_issuer(self) -> str:
        return f"{self.supabase_url}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
