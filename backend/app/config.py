"""Application settings, read from environment variables (and a local .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Bump this whenever a financial formula or rule changes. Every report stores it,
# so an old report can always be explained by the code that produced it.
CALC_VERSION = "1.2.0"
CONSENT_TEXT_VERSION = "2026-10-v1"


class Settings(BaseSettings):
    # Strip stray spaces from .env values: " openai" must still mean "openai".
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", str_strip_whitespace=True)

    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/foliolens"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(default="dev-only-change-me-not-for-production", min_length=32)
    jwt_expire_minutes: int = 60

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    storage_backend: str = "local"  # "local" or "s3"
    local_storage_dir: Path = Path("./data/uploads")
    s3_bucket: str | None = None
    s3_prefix: str = "uploads/"

    max_upload_mb: int = 10
    benchmark_symbol: str = "NIFTY50TRI"
    # Run background jobs inside the API process (tests and simple local runs).
    run_jobs_inline: bool = False

    llm_provider: str = "none"  # "none", "openai", "azure_openai" or "anthropic"
    llm_api_key: str | None = None
    llm_model: str | None = None  # model ID; for azure_openai, the deployment name
    llm_endpoint: str | None = None  # azure_openai: https://<resource>.openai.azure.com/
    llm_api_version: str = "2024-10-21"  # azure_openai API version
    llm_timeout_seconds: float = 60.0  # reasoning models can take a while

    login_max_attempts: int = 5
    login_window_seconds: int = 300

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.jwt_secret == "dev-only-change-me-not-for-production":  # noqa: S105
        raise RuntimeError("JWT_SECRET must be set in production")
    return settings
