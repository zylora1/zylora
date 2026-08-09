from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from zylora_api.api import commerce as commerce_api
from zylora_api.app import create_app
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import RequestIdentity, get_crypto, get_user_identity
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.commerce.schemas import (
    CancelSubscriptionResponse,
    MoneyResponse,
    PlanListResponse,
    PlanResponse,
    PublishCommandResponse,
    PublishEvaluationResponse,
    SubscriptionResponse,
    UnpublishCommandResponse,
)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.added: list[object] = []

    async def commit(self) -> None:
        self.commits += 1

    def add(self, model: object) -> None:
        self.added.append(model)


def plan(code: str = "FREE") -> PlanResponse:
    return PlanResponse(
        id=uuid4(),
        code=code,  # type: ignore[arg-type]
        name=code.title(),
        description=f"{code} plan",
        slot={"FREE": 1, "BASIC": 2, "GROWTH": 3, "BUSINESS": 4}[code],
        most_popular=code == "GROWTH",
        price=MoneyResponse(amount_minor=0 if code == "FREE" else 99900, currency="USD"),
        interval="MONTHLY",
        entitlements={
            "max_pages": 1,
            "custom_domain": False,
            "ai_monthly_credits": 15,
            "whatsapp_monthly_notifications": 0,
        },
    )


def setup(monkeypatch: pytest.MonkeyPatch) -> tuple[object, FakeSession, User]:
    now = datetime.now(UTC)
    crypto = AuthCrypto("commerce-route-test-secret-that-is-long-enough")
    user = User(
        id=uuid4(),
        account_type="USER",
        normalized_email="owner@example.com",
        display_email="owner@example.com",
        status="ACTIVE",
        verified_at=now,
        billing_country_code="ZZ",
    )
    session_model = Session(
        id=uuid4(),
        user_id=user.id,
        token_hash=b"s" * 32,
        csrf_hash=crypto.digest("commerce-csrf", purpose="csrf:USER_WEB"),
        audience="USER_WEB",
        auth_epoch=1,
        expires_at=now + timedelta(hours=1),
    )
    identity = RequestIdentity(session_model, user, "opaque-token")
    database = FakeSession()
    app = create_app()
    app.dependency_overrides[get_user_identity] = lambda: identity
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_crypto] = lambda: crypto
    return app, database, user


async def test_commerce_http_routes_use_server_evaluated_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, database, user = setup(monkeypatch)
    website_id = uuid4()
    payment_id = uuid4()
    transfer_id = uuid4()
    recipient_id = uuid4()
    catalog = PlanListResponse(
        region="INTERNATIONAL",
        country_code="ZZ",
        currency="USD",
        interval="MONTHLY",
        items=[plan()],
    )
    subscription = SubscriptionResponse(
        plan_code="FREE",
        state="ACTIVE",
        is_paid=False,
        price=MoneyResponse(amount_minor=0, currency="USD"),
        interval="MONTHLY",
        current_period_start=datetime(2026, 8, 1, tzinfo=UTC),
        current_period_end=datetime(2026, 9, 1, tzinfo=UTC),
        cancel_at_period_end=False,
        entitlements={"ai_monthly_credits": 15},
    )
    evaluation = PublishEvaluationResponse(
        website_id=website_id,
        page_count=1,
        domain_type="ZYLORA_SUBDOMAIN",
        current_plan_code="FREE",
        reuse_existing_subscription=True,
        can_request_publish=True,
        status="ELIGIBLE",
        recommended_plan_code="FREE",
        plans=[],
    )

    class Catalog:
        def __init__(self, _: object) -> None: ...

        async def response(self, _: str) -> PlanListResponse:
            return catalog

    class Subscriptions:
        def __init__(self, _: object) -> None: ...

        async def response(self, *_: object) -> SubscriptionResponse:
            return subscription

        async def create_payment(self, *_: object) -> object:
            return SimpleNamespace(
                id=payment_id,
                plan_id=plan().id,
                expected_amount_minor=99900,
                expected_currency="USD",
                state="CREATED",
            )

        async def cancel(self, *_: object) -> CancelSubscriptionResponse:
            return CancelSubscriptionResponse(
                plan_code="BASIC",
                state="CANCELLED",
                cancel_at_period_end=True,
                current_period_end=datetime(2026, 9, 1, tzinfo=UTC),
                message="Preserved.",
            )

    class Eligibility:
        def __init__(self, _: object) -> None: ...

        async def evaluate(self, *_: object) -> PublishEvaluationResponse:
            return evaluation

    class Publishing:
        def __init__(self, _: object) -> None: ...

        async def request_publish(self, *_: object) -> PublishCommandResponse:
            return PublishCommandResponse(
                website_id=website_id,
                status="PUBLISHING",
                plan_code="FREE",
                reused_existing_subscription=True,
                message="Reserved.",
            )

        async def request_unpublish(self, *_: object) -> UnpublishCommandResponse:
            return UnpublishCommandResponse(
                website_id=website_id, status="DRAFT", message="Cancelled."
            )

    class Ownership:
        def __init__(self, _: object) -> None: ...

        async def transfer(self, *_: object) -> object:
            return SimpleNamespace(
                id=transfer_id,
                website_id=website_id,
                sender_user_id=user.id,
                recipient_user_id=recipient_id,
                status="COMPLETED",
                completed_at=datetime(2026, 8, 1, tzinfo=UTC),
            )

    monkeypatch.setattr(commerce_api, "CatalogService", Catalog)
    monkeypatch.setattr(commerce_api, "SubscriptionService", Subscriptions)
    monkeypatch.setattr(commerce_api, "PublishEligibilityService", Eligibility)
    monkeypatch.setattr(commerce_api, "PublishService", Publishing)
    monkeypatch.setattr(commerce_api, "OwnershipService", Ownership)
    app.dependency_overrides[commerce_api.get_settings] = lambda: commerce_api.Settings(
        _env_file=None
    )

    headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": "commerce-csrf"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_user_csrf", "commerce-csrf")
        plans = await client.get("/api/v1/plans")
        current = await client.get("/api/v1/billing/subscription")
        checkout = await client.post(
            "/api/v1/billing/subscription/checkouts",
            json={"plan_id": str(uuid4())},
            headers={**headers, "Idempotency-Key": "commerce-checkout-0001"},
        )
        cancel = await client.post("/api/v1/billing/subscription/cancel", json={}, headers=headers)
        publish_evaluation = await client.get(f"/api/v1/websites/{website_id}/publish-evaluation")
        publish = await client.post(
            f"/api/v1/websites/{website_id}/publish",
            json={"domain_type": "ZYLORA_SUBDOMAIN"},
            headers={**headers, "Idempotency-Key": "commerce-publish-0001"},
        )
        unpublish = await client.post(
            f"/api/v1/websites/{website_id}/unpublish", json={}, headers=headers
        )
        transfer = await client.post(
            f"/api/v1/websites/{website_id}/transfers",
            json={"recipient_email": "recipient@example.com"},
            headers={**headers, "Idempotency-Key": "commerce-transfer-0001"},
        )

    assert plans.json()["currency"] == "USD"
    assert current.json()["plan_code"] == "FREE"
    assert checkout.json() == {
        "payment_id": str(payment_id),
        "status": "CREATED",
        "price": {"amount_minor": 99900, "currency": "USD"},
        "provider_available": False,
        "detail": (
            "Your server-authoritative price snapshot is saved. Paid checkout remains unavailable "
            "until an approved production payment provider is configured."
        ),
    }
    assert cancel.json()["cancel_at_period_end"] is True
    assert publish_evaluation.json()["can_request_publish"] is True
    assert publish.status_code == 202 and publish.json()["status"] == "PUBLISHING"
    assert unpublish.status_code == 202 and unpublish.json()["status"] == "DRAFT"
    assert transfer.json()["recipient_user_id"] == str(recipient_id)
    assert database.commits == 8
    assert len(database.added) == 4
