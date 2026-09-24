from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Todas las variables salen del .env. No hay valores por defecto."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str
    app_env: str
    api_prefix: str
    log_level: str
    cors_origins: str

    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    db_ssl_mode: str
    db_pool_size: int = Field(gt=0)
    db_max_overflow: int = Field(ge=0)
    db_pool_timeout_seconds: int = Field(gt=0)
    db_pool_recycle_seconds: int = Field(gt=0)
    db_statement_timeout_ms: int = Field(gt=0)

    rate_limit_default: str
    rate_limit_storage_uri: str

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
