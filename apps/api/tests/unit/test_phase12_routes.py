from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from zylora_api.api import admin_operations
from zylora_api.api.health import ReadinessService
from zylora_api.app import create_app
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.admin.schemas import (
    AdminMetric,
    AdminOperationListResponse,
    AdminOverviewResponse,
    AdminRecord,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserSummary,
)
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


class FakeOperations:
    def __init__(self, _: object) -> None: ...

    async def overview(self) -> AdminOverviewResponse:
        return AdminOverviewResponse(
            generated_at=datetime(2026, 8, 10, tzinfo=UTC),
            metrics=[AdminMetric(key="users", label="Users", value=2)],
            analytics_window_start=date(2026, 7, 12),
            page_views_last_30_days=9,
            leads_last_30_days=1,
        )

    async def users(self, query: str | None, _: int) -> AdminUserListResponse:
        assert query == "owner"
        return AdminUserListResponse(items=[summary()])

    async def user_detail(self, user_id: UUID) -> AdminUserDetail | None:
        result = summary()
        if user_id != result.id:
            return None
        return AdminUserDetail(
            **result.model_dump(),
            websites=[],
            subscriptions=[],
            payments=[],
            credit_ledger=[],
            leads=[],
            domains=[],
            audit_activity=[],
        )

    async def section(self, section: str, _: int) -> AdminOperationListResponse:
        return AdminOperationListResponse(
            section=section,  # type: ignore[arg-type]
            items=[AdminRecord(id="record", label="Measured record")],
        )


def summary() -> AdminUserSummary:
    return AdminUserSummary(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="owner@example.com",
        status="ACTIVE",
        signup_methods=["PASSWORD"],
        verified_at=datetime(2026, 8, 1, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        website_count=1,
        draft_count=1,
        live_website_id=None,
        live_website_name=None,
        plan_code="FREE",
        subscription_state=None,
    )


class Probe:
    async def check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_super_admin_operational_reads_are_isolated_and_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    crypto = AuthCrypto("phase12-admin-route-test-secret-long-enough")
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
            csrf_hash=crypto.digest("admin-csrf", purpose="csrf:ADMIN_WEB"),
            audience="ADMIN_WEB",
            auth_epoch=1,
            expires_at=now + timedelta(hours=1),
        ),
        admin,
        "opaque-admin-token",
    )
    database = FakeSession()
    app = create_app()
    app.dependency_overrides[get_admin_identity] = lambda: identity
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_crypto] = lambda: crypto
    app.dependency_overrides[admin_operations.get_settings] = lambda: SimpleNamespace(
        trusted_proxy_cidrs=(),
        trusted_proxy_hops=0,
    )
    app.dependency_overrides[admin_operations.get_readiness_service] = lambda: ReadinessService(
        Probe(), Probe()
    )
    monkeypatch.setattr(admin_operations, "AdminOperationsService", FakeOperations)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        overview = await client.get("/api/v1/admin/overview")
        users = await client.get("/api/v1/admin/users?query=owner")
        detail = await client.get(f"/api/v1/admin/users/{summary().id}")
        operations = await client.get("/api/v1/admin/operations/audit")
        health = await client.get("/api/v1/admin/health")

    assert overview.json()["metrics"] == [{"key": "users", "label": "Users", "value": 2}]
    assert users.json()["items"][0]["email"] == "owner@example.com"
    assert detail.status_code == 200
    assert operations.json()["section"] == "audit"
    assert health.json()["status"] == "ready"
    assert database.commits == 4
    assert database.added and database.added[0].event_type == "admin.user_viewed"
