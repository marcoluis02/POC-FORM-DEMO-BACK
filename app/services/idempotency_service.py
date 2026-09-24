from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.exceptions import ConflictError, IdempotencyKeyTakenError
from app.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkInterface
from app.models.idempotency_key import IdempotencyKey
from app.utils.hashing import stable_hash
from app.utils.time import utc_now

ResultT = TypeVar("ResultT", bound=BaseModel)
Operation = Callable[[UnitOfWorkInterface], Awaitable[ResultT]]


class IdempotencyService:
    """Ejecuta una operación una sola vez por Idempotency-Key.
    Si el cliente reintenta con la misma clave y los mismos datos, regresa la respuesta guardada."""

    def __init__(self, uow_factory: UnitOfWorkFactory, ttl_hours: int):
        self._uow_factory = uow_factory
        self._ttl = timedelta(hours=ttl_hours)

    async def execute(
        self,
        *,
        key: str | None,
        scope: str,
        request_payload: Any,
        operation: Operation,
        response_model: type[ResultT],
    ) -> ResultT:
        if key is None:
            async with self._uow_factory() as uow:
                result = await operation(uow)
                await uow.commit()
                return result

        request_hash = stable_hash(request_payload)
        try:
            return await self._execute_once(key, scope, request_hash, operation, response_model)
        except IdempotencyKeyTakenError:
            # Otra petición con la misma clave terminó primero: se regresa lo que ella guardó
            async with self._uow_factory() as uow:
                stored = await uow.idempotency.get_active(key, scope, utc_now())
            if stored is None:
                raise ConflictError("Otra solicitud igual se está procesando. Intenta de nuevo.") from None
            return self._replay(stored, request_hash, response_model)

    async def _execute_once(
        self,
        key: str,
        scope: str,
        request_hash: str,
        operation: Operation,
        response_model: type[ResultT],
    ) -> ResultT:
        now = utc_now()
        async with self._uow_factory() as uow:
            stored = await uow.idempotency.get_active(key, scope, now)
            if stored is not None:
                return self._replay(stored, request_hash, response_model)

            await uow.idempotency.delete_expired_key(key, scope, now)
            result = await operation(uow)
            await uow.idempotency.add(
                IdempotencyKey(
                    idempotency_key=key,
                    scope=scope,
                    request_hash=request_hash,
                    response_body=result.model_dump(mode="json"),
                    expires_at=now + self._ttl,
                )
            )
            await uow.commit()
            return result

    @staticmethod
    def _replay(stored: IdempotencyKey, request_hash: str, response_model: type[ResultT]) -> ResultT:
        if stored.request_hash != request_hash:
            raise ConflictError(
                "Esta clave de idempotencia ya se usó con datos diferentes.", code="idempotency_key_reused"
            )
        return response_model.model_validate(stored.response_body)
