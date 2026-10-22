"""Typed configuration (docs/architecture.md §5, docs/conventions.md §2)."""

from functools import cached_property
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> repository root
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./polybot.db"


class Settings(BaseSettings):
    """Environment configuration. Every value has a safe local default; secrets never live here."""

    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    app_debug: bool = False
    app_base_url: str = "http://localhost:8000"
    app_version: str = "0.1.0"
    cors_origins: str = "http://localhost:5173"
    database_url: str = DEFAULT_DATABASE_URL

    @field_validator("database_url")
    @classmethod
    def _empty_database_url_means_the_default(cls, value: str) -> str:
        # docs/env.example ships an empty DATABASE_URL: an empty value must not break the app.
        return value.strip() or DEFAULT_DATABASE_URL

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
