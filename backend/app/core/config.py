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
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
