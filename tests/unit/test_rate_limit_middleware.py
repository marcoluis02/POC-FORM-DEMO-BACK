from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.security.rate_limit_middleware import RateLimitMiddleware


def build_app(limit: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=limit, storage_uri="async+memory://")

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    return app


async def test_corta_con_429_al_pasar_el_limite():
    app = build_app("2/minute")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        codes = [(await client.get("/ping")).status_code for _ in range(3)]
        blocked = await client.get("/ping")

    assert codes == [200, 200, 429]
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1


async def test_no_cuenta_las_peticiones_options_de_cors():
    app = build_app("1/minute")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.options("/ping")
        response = await client.get("/ping")

    assert response.status_code == 200
