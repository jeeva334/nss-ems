from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str
    test_database_url: str | None = None
    secret_key: str
    cors_origins: str = "http://localhost:5173"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    log_level: str = "INFO"
    session_absolute_hours: int = 12
    session_idle_minutes: int = 60
    cookie_secure: bool | None = None      # default: True in production
    cookie_samesite: str = "lax"           # use "none" (+secure) if frontend/API are on different sites
    login_max_failures: int = 5
    login_window_seconds: int = 900
    email_provider: str = "dev_outbox"     # dev_outbox | resend
    resend_api_key: str | None = None
    email_from: str = "Manpower Portal <no-reply@example.com>"
    frontend_base_url: str = "http://localhost:5173"
    invitation_ttl_hours: int = 24

    @field_validator("app_env")
    @classmethod
    def _env(cls, v: str) -> str:
        if v not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test or production")
        return v

    @model_validator(mode="after")
    def _prod_guard(self):
        if self.app_env == "production" and (
            len(self.secret_key) < 32 or self.secret_key.startswith("change-me")
        ):
            raise ValueError("A strong SECRET_KEY is required in production")
        if self.app_env == "production" and (self.email_provider != "resend" or not self.resend_api_key):
            raise ValueError("Production requires EMAIL_PROVIDER=resend and RESEND_API_KEY")
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
