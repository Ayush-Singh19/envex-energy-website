"""Application settings, loaded from environment variables / ``.env``.

Company facts (phone numbers, alert email, address) have no defaults on
purpose: they must come from configuration, never from code.
"""

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Allowed in development only. 8080 is the port the frontend README serves the site on.
LOCAL_DEV_ORIGINS = (
    "http://localhost:8080",
    "http://127.0.0.1:8080",
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

    # "Today", "this week" and follow-up dates are the business's local days.
    timezone: str = "Asia/Kolkata"
    rate_limit_login: str = "10/minute"
    # Proxies in front of the app that append to X-Forwarded-For (1 on Render/Railway).
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)

    # Retention (security doc): enquiries 24 months after last activity; logs 12 months.
    retention_enquiry_days: int = Field(default=730, ge=30)
    retention_log_days: int = Field(default=365, ge=30)

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

    @model_validator(mode="after")
    def _production_is_locked_down(self) -> "Settings":
        if not self.is_production:
            return self
        secret = self.secret_key.get_secret_value()
        if len(secret) < 86 or "change-me" in secret:  # 86 chars = 64 random bytes, base64url
            raise ValueError(
                "SECRET_KEY must be 64 random bytes (86+ characters) in production. Generate one "
                'with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        if not self.frontend_url.startswith("https://"):
            raise ValueError("FRONTEND_URL must be an https:// address in production.")
        return self

    @property
    def call_number_display(self) -> str:
        """+917055444005 -> "+91 7055 444 005" (Indian numbers); others unchanged."""
        n = self.call_number
        if n.startswith("+91") and len(n) == 13:
            return f"+91 {n[3:7]} {n[7:10]} {n[10:]}"
        return n

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

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
