"""Application configuration loaded from environment variables.

All secrets come from the environment (or a secret manager that injects env vars).
Nothing sensitive is hard-coded; development defaults are explicitly unsafe and
rejected when ENVIRONMENT=production.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-secret-change-me-0000000000000000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "Recova Anticipatory Health Platform"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://recova:recova@localhost:5432/recova"

    # Security
    secret_key: str = _DEV_SECRET
    # Fernet key (urlsafe base64, 32 bytes) for field-level encryption at rest.
    # When empty in development, a key is derived from SECRET_KEY.
    field_encryption_key: str = ""
    session_cookie_name: str = "recova_session"
    csrf_cookie_name: str = "recova_csrf"
    session_ttl_minutes: int = 60 * 8
    session_idle_timeout_minutes: int = 60
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    password_reset_ttl_minutes: int = 30
    bootstrap_setup_token: str = ""
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    )
    rate_limit_login_per_minute: int = 10
    rate_limit_default_per_minute: int = 300

    # Public base URL of the frontend (used in password-reset / notification links)
    frontend_base_url: str = "http://localhost:3000"

    # Background worker
    run_embedded_worker: bool = True
    worker_poll_interval_seconds: float = 1.0
    scheduler_interval_seconds: int = 60

    # LLM provider abstraction (Agent 5)
    llm_provider: Literal["none", "openai", "azure_openai", "gemini", "anthropic"] = (
        "none"
    )
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""  # optional override (e.g. Azure endpoint)
    llm_azure_deployment: str = ""
    llm_azure_api_version: str = "2024-06-01"
    llm_timeout_seconds: float = 45.0

    # Notification providers
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_whatsapp_from: str = ""

    # External HIE integrations (adapters only; disabled until configured)
    malaffi_base_url: str = ""
    malaffi_client_id: str = ""
    malaffi_client_secret: str = ""
    malaffi_token_url: str = ""
    sahatna_base_url: str = ""
    sahatna_api_key: str = ""

    # Allows the Gate 2 emergency screen to run even if routine-processing consent is
    # missing (vital-interest exception). Routine analysis remains blocked.
    emergency_screen_without_consent: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v):  # type: ignore[no-untyped-def]
        if isinstance(v, str):
            val = v.strip()
            if val.startswith("postgres://"):
                return "postgresql+psycopg://" + val[len("postgres://") :]
            if val.startswith("postgresql://"):
                return "postgresql+psycopg://" + val[len("postgresql://") :]
            return val
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):  # type: ignore[no-untyped-def]
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.environment == "production":
            if self.bootstrap_setup_token and (
                len(self.bootstrap_setup_token) < 32
                or self.bootstrap_setup_token.startswith("__GENERATE_")
            ):
                raise ValueError(
                    "BOOTSTRAP_SETUP_TOKEN must be a private random secret of at least 32 characters, or empty to disable initialization"
                )
            from urllib.parse import urlsplit

            origin = urlsplit(self.frontend_base_url)
            if (
                origin.scheme != "https"
                or not origin.hostname
                or origin.username
                or origin.password
                or origin.query
                or origin.fragment
            ):
                raise ValueError(
                    "FRONTEND_BASE_URL must be the trusted public HTTPS URL in production"
                )
            if self.secret_key == _DEV_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a strong value in production"
                )
            if not self.field_encryption_key:
                raise ValueError("FIELD_ENCRYPTION_KEY must be set in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "none" or not self.llm_api_key:
            return False
        if self.llm_provider == "azure_openai":
            return bool(self.llm_base_url and self.llm_azure_deployment)
        return True

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def twilio_configured(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and (self.twilio_from_number or self.twilio_whatsapp_from)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
