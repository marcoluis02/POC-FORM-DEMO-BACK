from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Precio publicado para GPT-5.6 Luna al cerrar esta POC.
# Si se usa otro modelo, las tarifas deben declararse explícitamente en el entorno.
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_LUNA_INPUT_COST_PER_MILLION = Decimal("0.20")
DEFAULT_LUNA_OUTPUT_COST_PER_MILLION = Decimal("1.20")


class Settings(BaseSettings):
    """Configuración central del backend.

    Las credenciales estáticas de AWS son opcionales: si no se informan, boto3 usa su
    credential provider chain (IAM Role, variables estándar, perfil, workload identity, etc.).
    """

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

    s3_bucket: str
    aws_region: str
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    s3_presigned_url_expires_seconds: int = Field(gt=0)
    s3_max_pool_connections: int = Field(gt=0)
    s3_timeout_seconds: int = Field(gt=0)
    max_upload_mb: int = Field(gt=0)
    max_pdf_pages: int = Field(gt=0)
    max_photos_per_field: int = Field(gt=0)

    # Extracción IA. Para la POC el único provider implementado es OpenAI.
    ai_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = DEFAULT_OPENAI_MODEL
    openai_timeout_seconds: float = Field(default=120, gt=0)
    # El worker es quien controla los retries durables. El SDK queda sin retry por default
    # para evitar multiplicar intentos/costo; puede habilitarse explícitamente si se desea.
    openai_max_retries: int = Field(default=0, ge=0)
    openai_input_cost_per_million: Decimal | None = Field(default=None, ge=0)
    openai_output_cost_per_million: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_cross_field_configuration(self):
        static_parts = [self.aws_access_key_id.strip(), self.aws_secret_access_key.strip()]
        if any(static_parts) and not all(static_parts):
            raise ValueError(
                "AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY deben configurarse juntos, "
                "o dejarse ambos vacíos para usar la credential chain de boto3."
            )
        if self.aws_session_token.strip() and not all(static_parts):
            raise ValueError("AWS_SESSION_TOKEN requiere AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY.")

        input_price = self.openai_input_cost_per_million
        output_price = self.openai_output_cost_per_million

        if input_price is None and output_price is None:
            if self.openai_model == DEFAULT_OPENAI_MODEL:
                self.openai_input_cost_per_million = DEFAULT_LUNA_INPUT_COST_PER_MILLION
                self.openai_output_cost_per_million = DEFAULT_LUNA_OUTPUT_COST_PER_MILLION
            else:
                raise ValueError(
                    "Al cambiar OPENAI_MODEL debes configurar también "
                    "OPENAI_INPUT_COST_PER_MILLION y OPENAI_OUTPUT_COST_PER_MILLION."
                )
        elif input_price is None or output_price is None:
            raise ValueError(
                "OPENAI_INPUT_COST_PER_MILLION y OPENAI_OUTPUT_COST_PER_MILLION "
                "deben configurarse juntos."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def storage_configured(self) -> bool:
        # S3 puede autenticarse sin credenciales estáticas mediante IAM/default chain.
        return bool(self.s3_bucket.strip() and self.aws_region.strip())

    @property
    def aws_static_credentials_configured(self) -> bool:
        return bool(self.aws_access_key_id.strip() and self.aws_secret_access_key.strip())

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
