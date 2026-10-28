"""Typed configuration (docs/architecture.md §5, docs/conventions.md §2)."""

from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> repository root
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./polybot.db"


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

    # Tutor provider: the `LLM` port has one adapter per harness (ADR-013, ADR-019).
    llm_provider: Literal["pi", "opencode"] = "pi"
    pi_bin_path: str = "pi"
    pi_model: str = ""
    pi_timeout_seconds: float = 60.0

    # OpenCode adapter (ADR-019): the CLI talks to the background service, and the model is
    # whatever the installation authorised. `plan` is read-only, so the tutor cannot edit files.
    opencode_bin_path: str = "opencode"
    opencode_model: str = ""
    opencode_agent: str = "plan"
    # Translation uses its own agent: the `plan` identity narrates the task instead of translating
    # (F7 T6). `general` answers directly; an installation without it can override this.
    opencode_translation_agent: str = "general"
    opencode_timeout_seconds: float = 90.0

    # Speech synthesis: the Piper binary and its voices are files on this machine (ADR-016).
    # An empty voices/speech directory means `data/piper-voices` and `data/speech` in the repo.
    piper_bin_path: str = "piper"
    piper_voices_dir: str = ""
    piper_speech_dir: str = ""
    piper_timeout_seconds: float = 30.0

    @field_validator("database_url")
    @classmethod
    def _empty_database_url_means_the_default(cls, value: str) -> str:
        # docs/env.example ships an empty DATABASE_URL: an empty value must not break the app.
        return value.strip() or DEFAULT_DATABASE_URL

    @field_validator("pi_bin_path")
    @classmethod
    def _empty_bin_path_means_the_path_lookup(cls, value: str) -> str:
        return value.strip() or "pi"

    @field_validator("pi_timeout_seconds")
    @classmethod
    def _timeout_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("PI_TIMEOUT_SECONDS must be greater than zero")
        return value

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @cached_property
    def pi_model_or_none(self) -> str | None:
        return self.pi_model.strip() or None

    @field_validator("opencode_bin_path")
    @classmethod
    def _empty_opencode_path_means_the_path_lookup(cls, value: str) -> str:
        return value.strip() or "opencode"

    @field_validator("opencode_timeout_seconds")
    @classmethod
    def _opencode_timeout_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("OPENCODE_TIMEOUT_SECONDS must be greater than zero")
        return value

    @field_validator("opencode_agent")
    @classmethod
    def _empty_agent_means_plan(cls, value: str) -> str:
        return value.strip() or "plan"

    @field_validator("opencode_translation_agent")
    @classmethod
    def _empty_translation_agent_means_general(cls, value: str) -> str:
        return value.strip() or "general"

    @cached_property
    def opencode_model_or_none(self) -> str | None:
        return self.opencode_model.strip() or None

    @field_validator("piper_bin_path")
    @classmethod
    def _empty_piper_path_means_the_path_lookup(cls, value: str) -> str:
        return value.strip() or "piper"

    @field_validator("piper_timeout_seconds")
    @classmethod
    def _piper_timeout_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("PIPER_TIMEOUT_SECONDS must be greater than zero")
        return value

    @cached_property
    def piper_voices_path(self) -> Path:
        configured = self.piper_voices_dir.strip()
        return Path(configured) if configured else REPOSITORY_ROOT / "data" / "piper-voices"

    @cached_property
    def piper_speech_path(self) -> Path:
        configured = self.piper_speech_dir.strip()
        return Path(configured) if configured else REPOSITORY_ROOT / "data" / "speech"
