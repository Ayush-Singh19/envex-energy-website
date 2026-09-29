"""Application settings, loaded from environment variables / ``.env``.

Company facts (phone numbers, alert email, address) have no defaults on
purpose: they must come from configuration, never from code.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DEV_ORIGINS = (
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    secret_key: SecretStr = Field(min_length=32)
    frontend_url: str
    access_token_expire_minutes: int = Field(default=480, gt=0)
    database_url: str

    company_name: str
    whatsapp_number: str = Field(pattern=r"^\d{8,15}$")
    call_number: str = Field(pattern=r"^\+\d{8,15}$")
    alt_call_number: str = Field(pattern=r"^\+\d{8,15}$")
    alert_email: str
    company_address: str

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""

    rate_limit_enquiry: str = "5/10minutes"
    rate_limit_events: str = "60/minute"
    rate_limit_storage: str = "memory://"
    duplicate_window_hours: int = Field(default=24, ge=0)

    sentry_dsn: str = ""

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        # Render/Railway hand out postgres:// URLs; SQLAlchemy async needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix) :]
        return v

    @field_validator("frontend_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.frontend_url]
        if not self.is_production:
            origins += [o for o in LOCAL_DEV_ORIGINS if o != self.frontend_url]
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
