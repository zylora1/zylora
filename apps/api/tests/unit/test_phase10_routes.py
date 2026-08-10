from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from starlette.requests import Request
from zylora_api.api import admin_leads
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


async def test_public_routes_are_host_scoped_and_never_accept_client_tenant_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    website_id = uuid4()
    database = FakeSession()
    challenge_calls: list[dict[str, object]] = []

    class Challenge:
        async def enforce(self, token: str | None, **values: object) -> None:
            challenge_calls.append({"token": token, **values})

    class Leads:
        def __init__(self, _: object) -> None: ...

        async def capture(self, **values: object) -> SimpleNamespace:
            source = str(values["source"])
            return SimpleNamespace(
                lead=SimpleNamespace(
                    id=uuid4(), source=source, whatsapp_notification_queued=source == "FORM"
                ),
                duplicate=source == "CHATBOT",
            )

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

        async def capture_conversation_lead(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(
                lead=SimpleNamespace(
                    id=uuid4(), source="CHATBOT", whatsapp_notification_queued=False
                ),
                duplicate=True,
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
    monkeypatch.setattr(public_api, "ChatbotService", Chats)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
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
        chatbot_lead = await client.post(
            f"/api/v1/public/chatbot/conversations/{uuid4()}/leads",
            json={"name": "Ada", "enquiry": "Please call"},
            headers={
                "Idempotency-Key": "phase10-public-chat-lead-0001",
                "X-Zylora-Conversation-Token": "a" * 32,
            },
        )
        rejected_tenant = await client.post(
            "/api/v1/public/leads",
            json={"name": "Ada", "enquiry": "Please call", "website_id": str(uuid4())},
            headers={"Idempotency-Key": "phase10-public-invalid-0001"},
        )

    assert form.status_code == 201 and form.json()["source"] == "FORM"
    assert start.status_code == 201 and start.json()["access_token"] == "opaque-capability"
    assert message.json()["answer"] == "Grounded answer"
    assert chatbot_lead.status_code == 200 and chatbot_lead.json()["duplicate"] is True
    assert rejected_tenant.status_code == 422
    assert len(challenge_calls) == 2
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
