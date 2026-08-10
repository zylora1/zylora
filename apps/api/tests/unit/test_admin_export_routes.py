from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from zylora_api.api import admin_exports
from zylora_api.app import create_app
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import RequestIdentity, get_admin_identity, get_crypto
from zylora_api.modules.auth.security import AuthCrypto


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.added: list[object] = []

    async def commit(self) -> None:
        self.commits += 1

    def add(self, model: object) -> None:
        self.added.append(model)


async def test_super_admin_configures_versioned_export_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    crypto = AuthCrypto("admin-export-route-test-secret-long-enough")
    admin = User(
        id=uuid4(),
        account_type="SUPER_ADMIN",
        normalized_email="admin@example.com",
        display_email="admin@example.com",
        status="ACTIVE",
        verified_at=now,
        billing_country_code="ZZ",
    )
    identity = RequestIdentity(
        Session(
            id=uuid4(),
            user_id=admin.id,
            token_hash=b"a" * 32,
            csrf_hash=crypto.digest("admin-export-csrf", purpose="csrf:ADMIN_WEB"),
            audience="ADMIN_WEB",
            auth_epoch=1,
            expires_at=now + timedelta(hours=1),
        ),
        admin,
        "opaque-admin-token",
    )
    price = SimpleNamespace(
        id=uuid4(),
        currency="USD",
        amount_minor=1900,
        active=True,
        version=1,
        effective_at=now,
        created_at=now,
    )

    class Prices:
        def __init__(self, _: object) -> None: ...

        async def list_prices(self) -> list[object]:
            return [price]

        async def configure(self, **values: object) -> object:
            assert values["currency"] == "USD"
            assert values["amount_minor"] == 1900
            assert values["configured_by_user_id"] == admin.id
            return price

    database = FakeSession()
    app = create_app()
    app.dependency_overrides[get_admin_identity] = lambda: identity
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_crypto] = lambda: crypto
    app.dependency_overrides[admin_exports.get_settings] = lambda: admin_exports.Settings(
        _env_file=None
    )
    monkeypatch.setattr(admin_exports, "ExportPriceService", Prices)
    headers = {"Origin": "http://admin.localhost:3000", "X-CSRF-Token": "admin-export-csrf"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_admin_csrf", "admin-export-csrf")
        listed = await client.get("/api/v1/admin/export-prices")
        configured = await client.post(
            "/api/v1/admin/export-prices",
            json={"currency": "USD", "amount_minor": 1900, "active": True},
            headers=headers,
        )

    assert listed.json()[0]["amount_minor"] == 1900
    assert configured.status_code == 201 and configured.json()["version"] == 1
    assert database.commits == 2 and len(database.added) == 1
