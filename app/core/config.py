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

    idempotency_ttl_hours: int = Field(gt=0)
    idempotency_purge_interval_minutes: int = Field(gt=0)
    idempotency_purge_batch_size: int = Field(gt=0)

    worker_enabled: bool
    worker_poll_interval_seconds: float = Field(gt=0)
    worker_batch_size: int = Field(gt=0)
    worker_max_attempts: int = Field(gt=0)
    worker_retry_delay_seconds: int = Field(gt=0)
    worker_task_timeout_seconds: int = Field(gt=0)
    worker_db_pool_size: int = Field(gt=0)

    pagination_default_limit: int = Field(gt=0)
    pagination_max_limit: int = Field(gt=0)

    # Deben existir en el .env; si están vacías la app arranca, pero subir archivos responde 503
    s3_bucket: str
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key: str
    s3_presigned_url_expires_seconds: int = Field(gt=0)
    s3_max_pool_connections: int = Field(gt=0)
    s3_timeout_seconds: int = Field(gt=0)
    max_upload_mb: int = Field(gt=0)
    max_pdf_pages: int = Field(gt=0)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def storage_configured(self) -> bool:
        values = (self.s3_bucket, self.aws_region, self.aws_access_key_id, self.aws_secret_access_key)
        return all(value.strip() for value in values)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

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
