import json
import math
import time

from limits import parse
from limits.aio.strategies import SlidingWindowCounterRateLimiter
from limits.storage import storage_from_string
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.exception_handlers import error_body

UNKNOWN_CLIENT = "unknown"


class RateLimitMiddleware:
    """Limita las peticiones por IP en toda la API. Si se pasa del límite responde 429."""

    def __init__(self, app: ASGIApp, limit: str, storage_uri: str):
        self._app = app
        self._limit = parse(limit)
        self._limiter = SlidingWindowCounterRateLimiter(storage_from_string(storage_uri))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            await self._app(scope, receive, send)
            return

        client_ip = scope["client"][0] if scope.get("client") else UNKNOWN_CLIENT
        if await self._limiter.hit(self._limit, client_ip):
            await self._app(scope, receive, send)
            return

        stats = await self._limiter.get_window_stats(self._limit, client_ip)
        retry_after = max(1, math.ceil(stats.reset_time - time.time()))
        await self._send_too_many_requests(send, retry_after)

    async def _send_too_many_requests(self, send: Send, retry_after: int) -> None:
        message = f"Demasiadas solicitudes. Espera {retry_after} segundos e intenta de nuevo."
        body = json.dumps(error_body("rate_limited", message), ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(retry_after).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
