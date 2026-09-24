import json

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exception_handlers import error_body


class BodyTooLargeError(HTTPException):
    """Es HTTPException para que FastAPI no la convierta en un 400 genérico al leer el body."""

    def __init__(self, message: str):
        super().__init__(status_code=413, detail=message)


class BodySizeLimitMiddleware:
    """Corta cualquier petición cuyo cuerpo pase de max_bytes antes de que se lea completo.
    Revisa el Content-Length y además cuenta los bytes reales (por si el cliente no lo manda)."""

    def __init__(self, app: ASGIApp, max_bytes: int, max_upload_mb: int):
        self._app = app
        self._max_bytes = max_bytes
        self._message = f"El archivo pesa más de {max_upload_mb} MB. Elige uno más ligero."

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self._max_bytes:
            await self._send_too_large(send)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise BodyTooLargeError(self._message)
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._app(scope, limited_receive, tracked_send)
        except BodyTooLargeError:
            if not response_started:
                await self._send_too_large(send)

    async def _send_too_large(self, send: Send) -> None:
        body = json.dumps(error_body("file_too_large", self._message), ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
