import httpx
from fastapi import FastAPI
from zylora_api.app import create_app
from zylora_api.core.http_security import ApiSecurityHeadersMiddleware


async def test_api_responses_are_not_cacheable_or_indexable_and_have_browser_safeguards() -> None:
    app = FastAPI()
    app.add_middleware(ApiSecurityHeadersMiddleware, production=False)

    @app.get("/api/v1/security-headers-probe")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/security-headers-probe")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )


async def test_zylora_application_registers_browser_safeguards() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/liveness")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


async def test_production_api_header_middleware_enables_hsts() -> None:
    app = FastAPI()
    app.add_middleware(ApiSecurityHeadersMiddleware, production=True)

    @app.get("/liveness")
    async def liveness() -> dict[str, bool]:
        return {"alive": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.zylora.example"
    ) as client:
        response = await client.get("/liveness")

    assert response.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"
