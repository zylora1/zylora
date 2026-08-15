from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from starlette.requests import Request
from zylora_api.api import admin_leads
from zylora_api.api import analytics as analytics_api
from zylora_api.api import leads as leads_api
from zylora_api.api import public as public_api
from zylora_api.app import create_app
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.http import (
    RequestIdentity,
    get_admin_identity,
    get_challenge_service,
    get_crypto,
    get_user_identity,
)
from zylora_api.modules.auth.security import AuthCrypto


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.added: list[object] = []
        self.rows: list[object] = []

    async def commit(self) -> None:
        self.commits += 1

    def add(self, value: object) -> None:
        self.added.append(value)

    async def scalars(self, _: object) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self.rows)


def user_identity(account_type: str = "USER") -> tuple[RequestIdentity, AuthCrypto]:
    now = datetime.now(UTC)
    crypto = AuthCrypto("phase10-route-secret-that-is-long-enough")
    user = User(
        id=uuid4(),
        account_type=account_type,
        normalized_email=f"{account_type.casefold()}@example.com",
        display_email=f"{account_type.casefold()}@example.com",
        status="ACTIVE",
        verified_at=now,
        billing_country_code="ZZ",
    )
    audience = "ADMIN_WEB" if account_type == "SUPER_ADMIN" else "USER_WEB"
    csrf = "phase10-admin-csrf" if account_type == "SUPER_ADMIN" else "phase10-user-csrf"
    session = Session(
        id=uuid4(),
        user_id=user.id,
        token_hash=b"t" * 32,
        csrf_hash=crypto.digest(csrf, purpose=f"csrf:{audience}"),
        audience=audience,
        auth_epoch=1,
        expires_at=now + timedelta(hours=1),
    )
    return RequestIdentity(session, user, "phase10-token"), crypto


async def test_lead_service_rejects_chatbot_sources_before_any_persistence() -> None:
    from zylora_api.modules.commerce.quotas import LeadService

    database = FakeSession()
    with pytest.raises(AuthProblem, match="Lead source is invalid"):
        await LeadService(database).capture(  # type: ignore[arg-type]
            website_id=uuid4(),
            source="CHATBOT",
            idempotency_key="chatbot-source-must-be-rejected",
            name="Ada",
            email="ada@example.com",
            phone=None,
            enquiry="Please contact me",
            owner_country_code="ZZ",
            correlation_id="chatbot-source-rejection",
        )
    assert database.added == [] and database.commits == 0


async def test_public_routes_are_host_scoped_and_never_accept_client_tenant_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    website_id = uuid4()
    database = FakeSession()
    challenge_calls: list[dict[str, object]] = []
    analytics_calls: list[dict[str, object]] = []

    class Challenge:
        async def enforce(self, token: str | None, **values: object) -> None:
            challenge_calls.append({"token": token, **values})

    class Leads:
        def __init__(self, _: object) -> None: ...

        async def capture(self, **values: object) -> SimpleNamespace:
            assert values["source"] == "FORM"
            return SimpleNamespace(
                lead=SimpleNamespace(id=uuid4(), source="FORM", whatsapp_notification_queued=True),
                duplicate=False,
            )

    class Analytics:
        def __init__(self, _: object) -> None: ...

        async def record(self, **values: object) -> SimpleNamespace:
            analytics_calls.append(values)
            return SimpleNamespace(duplicate=False)

    class Chats:
        @classmethod
        def from_settings(cls, *_: object) -> Chats:
            return cls()

        async def start_conversation(self, *_: object) -> SimpleNamespace:
            return SimpleNamespace(
                conversation=SimpleNamespace(id=uuid4()), access_token="opaque-capability"
            )

        async def reply(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(
                conversation=SimpleNamespace(id=uuid4()),
                answer="Grounded answer",
                source_paths=["/"],
            )

    async def context(*_: object) -> public_api.PublicWebsite:
        return public_api.PublicWebsite(
            website=SimpleNamespace(id=website_id), hostname="site.example", owner_country_code="ZZ"
        )

    app = create_app()
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_challenge_service] = lambda: Challenge()
    app.dependency_overrides[public_api.get_settings] = lambda: Settings(
        _env_file=None, environment="test", storage_provider="memory"
    )
    monkeypatch.setattr(public_api, "resolve_public_website", context)
    monkeypatch.setattr(public_api, "LeadService", Leads)
    monkeypatch.setattr(public_api, "AnalyticsService", Analytics)
    monkeypatch.setattr(public_api, "ChatbotService", Chats)
    app.dependency_overrides[get_crypto] = lambda: AuthCrypto("phase11-public-analytics-secret")
    assert "/api/v1/public/chatbot/conversations/{conversation_id}/leads" not in {
        route.path for route in app.routes if hasattr(route, "path")
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        page_view = await client.post(
            "/api/v1/public/analytics/page-views",
            json={
                "event_id": "phase11-public-page-view-0001",
                "session_id": "phase11-public-session-0001",
                "page_path": "/about",
            },
        )
        rejected_analytics_tenant = await client.post(
            "/api/v1/public/analytics/page-views",
            json={
                "event_id": "phase11-public-page-view-0002",
                "session_id": "phase11-public-session-0002",
                "page_path": "/about",
                "website_id": str(uuid4()),
            },
        )
        form = await client.post(
            "/api/v1/public/leads",
            json={"name": "Ada", "enquiry": "Please call", "page_path": "/contact"},
            headers={"Idempotency-Key": "phase10-public-form-0001"},
        )
        start = await client.post("/api/v1/public/chatbot/conversations", json={})
        message = await client.post(
            f"/api/v1/public/chatbot/conversations/{uuid4()}/messages",
            json={"access_token": "a" * 32, "message": "Hello"},
        )
        rejected_tenant = await client.post(
            "/api/v1/public/leads",
            json={"name": "Ada", "enquiry": "Please call", "website_id": str(uuid4())},
            headers={"Idempotency-Key": "phase10-public-invalid-0001"},
        )

    assert page_view.status_code == 202 and page_view.json() == {
        "accepted": True,
        "duplicate": False,
    }
    assert rejected_analytics_tenant.status_code == 422
    assert analytics_calls[0]["website_id"] == website_id
    assert analytics_calls[0]["page_path"] == "/about"
    assert form.status_code == 201 and form.json()["source"] == "FORM"
    assert start.status_code == 201 and start.json()["access_token"] == "opaque-capability"
    assert message.json()["answer"] == "Grounded answer"
    assert rejected_tenant.status_code == 422
    assert len(challenge_calls) == 1
    assert all(call["expected_hostname"] == "site.example" for call in challenge_calls)
    assert database.commits == 4


async def test_owner_lead_and_credit_routes_filter_through_the_user_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity, crypto = user_identity()
    website_id = uuid4()
    database = FakeSession()
    database.rows = [
        SimpleNamespace(
            id=uuid4(),
            source="FORM",
            name="Ada",
            email="ada@example.com",
            phone=None,
            enquiry="Please call",
            page_path="/contact",
            status="NEW",
            captured_at=datetime(2026, 8, 10, tzinfo=UTC),
        )
    ]

    class Credits:
        def __init__(self, _: object) -> None: ...

        async def balance_for(self, _: object) -> int:
            return -1

    class Policy:
        def __init__(self, _: object) -> None: ...

        async def current(self) -> SimpleNamespace:
            return SimpleNamespace(policy="ALLOW_DEBT")

    app = create_app()
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_user_identity] = lambda: identity
    app.dependency_overrides[get_crypto] = lambda: crypto
    monkeypatch.setattr(leads_api, "CreditLedgerService", Credits)
    monkeypatch.setattr(leads_api, "LeadCreditPolicyService", Policy)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        listed = await client.get(f"/api/v1/websites/{website_id}/leads?limit=50")
        balance = await client.get("/api/v1/lead-credits")

    assert listed.json()[0]["name"] == "Ada"
    assert balance.json() == {"balance": -1, "policy": "ALLOW_DEBT"}
    assert database.commits == 2


async def test_super_admin_policy_and_adjustment_routes_are_csrf_protected_and_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity, crypto = user_identity("SUPER_ADMIN")
    database = FakeSession()
    target_user_id = uuid4()

    class Policy:
        def __init__(self, _: object) -> None: ...

        async def current(self) -> SimpleNamespace:
            return SimpleNamespace(policy="ALLOW_DEBT")

        async def configure(self, policy: str) -> SimpleNamespace:
            assert policy == "REJECT_NEW"
            return SimpleNamespace(policy=policy)

    class Credits:
        def __init__(self, _: object) -> None: ...

        async def adjust(self, **values: object) -> SimpleNamespace:
            assert values["user_id"] == target_user_id
            assert values["actor_user_id"] == identity.user.id
            return SimpleNamespace(
                id=uuid4(),
                delta=25,
                resulting_balance=25,
                entry_type="ADMIN_GRANT",
                reason="Launch grant",
            )

    app = create_app()
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_admin_identity] = lambda: identity
    app.dependency_overrides[get_crypto] = lambda: crypto
    app.dependency_overrides[admin_leads.get_settings] = lambda: Settings(_env_file=None)
    monkeypatch.setattr(admin_leads, "LeadCreditPolicyService", Policy)
    monkeypatch.setattr(admin_leads, "CreditLedgerService", Credits)
    headers = {"Origin": "http://admin.localhost:3000", "X-CSRF-Token": "phase10-admin-csrf"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_admin_csrf", "phase10-admin-csrf")
        current = await client.get("/api/v1/admin/lead-credit-policy")
        configured = await client.post(
            "/api/v1/admin/lead-credit-policy", json={"policy": "REJECT_NEW"}, headers=headers
        )
        adjusted = await client.post(
            f"/api/v1/admin/users/{target_user_id}/lead-credits",
            json={"delta": 25, "reason": "Launch grant"},
            headers={**headers, "Idempotency-Key": "phase10-admin-credit-0001"},
        )

    assert current.json()["policy"] == "ALLOW_DEBT"
    assert configured.json()["policy"] == "REJECT_NEW"
    assert adjusted.json()["resulting_balance"] == 25
    assert database.commits == 3 and len(database.added) == 2


async def test_public_website_resolution_uses_only_the_active_request_hostname() -> None:
    owner = SimpleNamespace(account_type="USER", status="ACTIVE", billing_country_code="IN")
    domain = SimpleNamespace(website_id=uuid4())
    website = SimpleNamespace(id=domain.website_id, live_owner_user_id=uuid4())

    class ResolutionSession:
        def __init__(self) -> None:
            self.rows = [domain, website]

        async def scalar(self, _: object) -> object:
            return self.rows.pop(0) if self.rows else None

        async def get(self, _: object, __: object) -> object:
            return owner

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [(b"host", b"dental.example")],
            "client": ("127.0.0.1", 1234),
            "server": ("dental.example", 443),
        }
    )
    context = await public_api.resolve_public_website(request, ResolutionSession())
    assert context.website is website
    assert context.hostname == "dental.example" and context.owner_country_code == "IN"

    class MissingDomainSession:
        async def scalar(self, _: object) -> None:
            return None

    with pytest.raises(AuthProblem, match="Published Website not found"):
        await public_api.resolve_public_website(request, MissingDomainSession())


async def test_phase11_analytics_and_notification_routes_are_identity_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity, crypto = user_identity()
    database = FakeSession()
    notification_id = uuid4()
    captured: dict[str, object] = {}

    class Analytics:
        def __init__(self, _: object) -> None: ...

        async def dashboard(self, **values: object) -> SimpleNamespace:
            captured["analytics"] = values
            return SimpleNamespace(
                website_id=None,
                timezone="UTC",
                period_days=30,
                has_published_website=True,
                has_meaningful_data=True,
                page_views=4,
                sessions=3,
                visitors=2,
                leads=1,
                lead_form_opens=2,
                lead_form_submissions=1,
                form_leads=1,
                chatbot_leads=0,
                chatbot_conversations=1,
                chatbot_messages=2,
                conversions=1,
                points=[],
            )

    class Notifications:
        def __init__(self, _: object) -> None: ...

        async def page_for_user(self, **values: object) -> tuple[list[SimpleNamespace], int, None]:
            captured["notification_page"] = values
            return (
                [
                    SimpleNamespace(
                        id=notification_id,
                        type="LEAD_CAPTURED",
                        title="New lead captured",
                        body="A form enquiry is ready to review.",
                        deep_link="/app/leads",
                        state="UNREAD",
                        read_at=None,
                        created_at=datetime(2026, 8, 10, tzinfo=UTC),
                    )
                ],
                1,
                None,
            )

        async def mark_read(self, received_id: object, recipient_id: object) -> SimpleNamespace:
            captured["notification_read"] = (received_id, recipient_id)
            return SimpleNamespace(
                id=notification_id,
                type="LEAD_CAPTURED",
                title="New lead captured",
                body="A form enquiry is ready to review.",
                deep_link="/app/leads",
                state="READ",
                read_at=datetime(2026, 8, 10, 1, tzinfo=UTC),
                created_at=datetime(2026, 8, 10, tzinfo=UTC),
            )

    app = create_app()
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_user_identity] = lambda: identity
    app.dependency_overrides[get_crypto] = lambda: crypto
    monkeypatch.setattr(analytics_api, "AnalyticsService", Analytics)
    monkeypatch.setattr(analytics_api, "NotificationService", Notifications)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_user_csrf", "phase10-user-csrf")
        dashboard = await client.get("/api/v1/analytics?period_days=30")
        notifications = await client.get("/api/v1/notifications?limit=10")
        marked = await client.post(
            f"/api/v1/notifications/{notification_id}/read",
            json={},
            headers={"X-CSRF-Token": "phase10-user-csrf"},
        )

    assert dashboard.status_code == 200 and dashboard.json()["page_views"] == 4
    assert notifications.status_code == 200 and notifications.json()["unread_count"] == 1
    assert marked.status_code == 200 and marked.json()["state"] == "READ"
    assert captured["analytics"] == {
        "owner_user_id": identity.user.id,
        "timezone": identity.user.timezone,
        "period_days": 30,
        "website_id": None,
    }
    assert captured["notification_page"] == {
        "recipient_user_id": identity.user.id,
        "limit": 10,
        "before": None,
    }
    assert captured["notification_read"] == (notification_id, identity.user.id)
    assert database.commits == 3
