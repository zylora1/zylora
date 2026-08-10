from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar
from uuid import uuid4

import httpx
import pytest
from zylora_api.api import contact
from zylora_api.app import create_app
from zylora_api.core.config import Settings
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import get_challenge_service, get_crypto
from zylora_api.modules.auth.security import AuthCrypto


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class Challenge:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[dict[str, object]] = []

    async def enforce(self, token: str | None, **values: object) -> None:
        self.calls.append({"token": token, **values})
        if self.failure:
            raise self.failure


class FakeEmail:
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, _: object, __: object) -> None: ...

    async def queue(self, **values: object) -> SimpleNamespace:
        self.calls.append(values)
        return SimpleNamespace(id=uuid4())


def app_with_contact_dependencies(settings: Settings, database: FakeSession, challenge: Challenge):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[contact.get_settings] = lambda: settings
    app.dependency_overrides[get_crypto] = lambda: AuthCrypto(
        "phase14-public-contact-secret-that-is-long-enough"
    )
    app.dependency_overrides[get_challenge_service] = lambda: challenge
    return app


@pytest.mark.asyncio
async def test_public_contact_requires_server_challenge_and_queues_a_durable_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = FakeSession()
    challenge = Challenge()
    FakeEmail.calls = []
    app = app_with_contact_dependencies(
        Settings(
            _env_file=None,
            environment="test",
            storage_provider="memory",
            contact_recipient_email="support@zylora.example",
        ),
        database,
        challenge,
    )
    monkeypatch.setattr(contact, "TransactionalEmailService", FakeEmail)

    payload = {
        "name": " Ada Lovelace ",
        "email": "ADA@EXAMPLE.COM",
        "message": " Please help us select an approved Template. ",
        "turnstile_token": "single-use-token",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        first = await client.post("/api/v1/public/contact", json=payload)
        second = await client.post("/api/v1/public/contact", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert database.commits == 2
    assert [call["token"] for call in challenge.calls] == ["single-use-token", "single-use-token"]
    assert all(call["expected_action"] == "contact" for call in challenge.calls)
    assert len(FakeEmail.calls) == 2
    assert FakeEmail.calls[0]["recipient_email"] == "support@zylora.example"
    assert FakeEmail.calls[0]["kind"] == "CONTACT_SUBMISSION"
    assert FakeEmail.calls[0]["resource_type"] == "public_contact"
    assert FakeEmail.calls[0]["body"] == (
        "From: Ada Lovelace <ADA@example.com>\n\nPlease help us select an approved Template."
    )
    assert FakeEmail.calls[0]["idempotency_key"] == FakeEmail.calls[1]["idempotency_key"]


@pytest.mark.asyncio
async def test_public_contact_rejects_unavailable_delivery_invalid_input_and_challenge_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = FakeSession()
    missing_recipient = app_with_contact_dependencies(
        Settings(_env_file=None, environment="test", storage_provider="memory"),
        database,
        Challenge(),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=missing_recipient), base_url="http://testserver"
    ) as client:
        unavailable = await client.post(
            "/api/v1/public/contact",
            json={"name": "Ada", "email": "ada@example.com", "message": "A long enough message."},
        )
        invalid = await client.post(
            "/api/v1/public/contact",
            json={"name": "", "email": "not-an-email", "message": "too short"},
        )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "contact_unavailable"
    assert invalid.status_code == 422
    assert database.commits == 0

    failed_challenge = Challenge(contact.problem(503, "challenge_unavailable", "Try again later."))
    protected = app_with_contact_dependencies(
        Settings(
            _env_file=None,
            environment="test",
            storage_provider="memory",
            contact_recipient_email="support@zylora.example",
        ),
        database,
        failed_challenge,
    )
    FakeEmail.calls = []
    monkeypatch.setattr(contact, "TransactionalEmailService", FakeEmail)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=protected), base_url="http://testserver"
    ) as client:
        rejected = await client.post(
            "/api/v1/public/contact",
            json={
                "name": "Ada",
                "email": "ada@example.com",
                "message": "A long enough message for the form.",
                "turnstile_token": "expired-or-replayed-token",
            },
        )
    assert rejected.status_code == 503
    assert rejected.json()["code"] == "challenge_unavailable"
    assert database.commits == 0
    assert FakeEmail.calls == []
