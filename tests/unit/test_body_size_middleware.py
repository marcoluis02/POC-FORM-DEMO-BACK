from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.core.exception_handlers import register_exception_handlers
from app.security.body_size_middleware import BodySizeLimitMiddleware

MAX_BYTES = 100


def build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BYTES, max_upload_mb=1)

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        return {"size": len(await request.body())}

    return app


async def send(content) -> "object":
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://test") as client:
        return await client.post("/echo", content=content)


async def test_deja_pasar_cuerpos_dentro_del_limite():
    response = await send(b"a" * MAX_BYTES)

    assert response.status_code == 200
    assert response.json() == {"size": MAX_BYTES}


async def test_corta_por_content_length_sin_leer_el_cuerpo():
    response = await send(b"a" * (MAX_BYTES + 1))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


async def test_corta_cuando_mandan_el_cuerpo_por_partes_sin_content_length():
    async def chunks():
        for _ in range(5):
            yield b"a" * 40

    response = await send(chunks())

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
