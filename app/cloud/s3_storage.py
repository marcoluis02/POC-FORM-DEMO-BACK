import asyncio
import logging

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.exceptions import StorageUnavailableError

logger = logging.getLogger(__name__)

STORAGE_NOT_CONFIGURED = "El guardado de archivos todavía no está configurado en el servidor."
STORAGE_FAILED = "No pudimos guardar el archivo en este momento. Intenta de nuevo en unos segundos."


class S3Storage:
    """Bucket privado. boto3 es bloqueante, por eso las llamadas de red corren en otro hilo."""

    def __init__(self, settings: Settings):
        self._configured = settings.storage_configured
        self._bucket = settings.s3_bucket
        self._url_expires = settings.s3_presigned_url_expires_seconds
        self._client = None
        if self._configured:
            self._client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=settings.s3_timeout_seconds,
                    read_timeout=settings.s3_timeout_seconds,
                    max_pool_connections=settings.s3_max_pool_connections,
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )

    def _require_client(self):
        if self._client is None:
            raise StorageUnavailableError(STORAGE_NOT_CONFIGURED)
        return self._client

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        client = self._require_client()
        try:
            await asyncio.to_thread(
                client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
        except (BotoCoreError, ClientError) as exc:
            logger.warning("S3 put falló para %s: %s", key, type(exc).__name__)
            raise StorageUnavailableError(STORAGE_FAILED) from exc

    async def delete(self, key: str) -> None:
        """Si el archivo ya no existe S3 responde bien igual, así que reintentar no hace daño."""
        client = self._require_client()
        try:
            await asyncio.to_thread(client.delete_object, Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            logger.warning("S3 delete falló para %s: %s", key, type(exc).__name__)
            raise StorageUnavailableError(STORAGE_FAILED) from exc

    async def get_url(self, key: str) -> str:
        """URL temporal para ver el archivo. Firmar no hace llamadas de red."""
        client = self._require_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=self._url_expires,
        )
