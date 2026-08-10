from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request
from zylora_api.api import publishing


class Values:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def all(self) -> list[object]:
        return self.items


class StatusSession:
    def __init__(self, website: object, domains: list[object], deployments: list[object]) -> None:
        self.website = website
        self.results = [Values(domains), Values(deployments)]

    async def scalar(self, _: object) -> object:
        return self.website

    async def scalars(self, _: object) -> Values:
        return self.results.pop(0)


def domain() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        website_id=uuid4(),
        type="CUSTOM",
        display_hostname="www.example.com",
        state="VERIFIED",
        tls_status="ACTIVE",
        is_primary=False,
        is_active=False,
        verification_record_name="_cf.example.com",
        verification_record_type="TXT",
        verification_record_value="proof",
        safe_error=None,
        updated_at=datetime.now(UTC),
    )


def deployment(website_id: object, domain_id: object) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        website_id=website_id,
        domain_id=domain_id,
        operation="PUBLISH",
        state="ACTIVE",
        artifact_checksum="checksum",
        failure_code=None,
        safe_error=None,
        queued_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )


def test_domain_and_deployment_responses_expose_only_safe_operational_fields() -> None:
    item = domain()
    response = publishing._domain_response(item)  # type: ignore[arg-type]
    assert response.hostname == "www.example.com" and response.verification_record_value == "proof"
    deployment_response = publishing._deployment_response(
        deployment(item.website_id, item.id)  # type: ignore[arg-type]
    )
    assert (
        deployment_response.state == "ACTIVE"
        and deployment_response.artifact_checksum == "checksum"
    )


@pytest.mark.asyncio
async def test_publication_status_is_scoped_to_the_authenticated_owner_website() -> None:
    website_id = uuid4()
    item = domain()
    item.website_id = website_id
    deploy = deployment(website_id, item.id)
    website = SimpleNamespace(
        id=website_id,
        owner_user_id=uuid4(),
        status="PUBLISHED",
        active_deployment_id=deploy.id,
    )
    result = await publishing.publication_status(
        website_id,
        SimpleNamespace(user=SimpleNamespace(id=website.owner_user_id)),
        StatusSession(website, [item], [deploy]),  # type: ignore[arg-type]
    )
    assert result.website_status == "PUBLISHED"
    assert [entry.id for entry in result.domains] == [item.id]
    assert [entry.id for entry in result.deployments] == [deploy.id]


@pytest.mark.asyncio
async def test_owner_lookup_rejects_an_absent_or_other_website() -> None:
    class EmptySession:
        async def scalar(self, _: object) -> None:
            return None

    with pytest.raises(Exception, match="Website not found"):
        await publishing._website_for_owner(EmptySession(), uuid4(), uuid4())  # type: ignore[arg-type]


class MutationSession:
    def __init__(self, *values: object) -> None:
        self.values = list(values)
        self.commits = 0
        self.refreshed: list[object] = []

    async def scalar(self, _: object) -> object:
        return self.values.pop(0)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, value: object) -> None:
        self.refreshed.append(value)


def mutation_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/v1/websites/test/domains/custom",
            "raw_path": b"/api/v1/websites/test/domains/custom",
            "query_string": b"",
            "headers": [(b"host", b"app.zylora.test")],
            "client": ("127.0.0.1", 1234),
            "server": ("app.zylora.test", 443),
        }
    )


def patch_command_guards(monkeypatch: pytest.MonkeyPatch, audits: list[dict[str, object]]) -> None:
    class Audit:
        def __init__(self, *_: object) -> None:
            return None

        def record(self, _action: str, **kwargs: object) -> None:
            audits.append(kwargs)

    monkeypatch.setattr(publishing, "require_json_origin", lambda *_: None)
    monkeypatch.setattr(publishing, "require_csrf", lambda *_: None)
    monkeypatch.setattr(publishing, "correlation_id", lambda _: "correlation-id")
    monkeypatch.setattr(publishing, "request_ip", lambda *_: "127.0.0.1")
    monkeypatch.setattr(publishing, "AuditService", Audit)


@pytest.mark.asyncio
async def test_domain_command_endpoints_scope_mutations_and_audit_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    website_id = uuid4()
    owner_id = uuid4()
    item = domain()
    item.website_id = website_id
    identity = SimpleNamespace(user=SimpleNamespace(id=owner_id))
    audits: list[dict[str, object]] = []
    patch_command_guards(monkeypatch, audits)
    provider = object()
    monkeypatch.setattr(publishing, "domain_provider_for", lambda _: provider)

    calls: list[tuple[object, ...]] = []

    class DomainCommands:
        def __init__(self, _: object) -> None:
            return None

        async def list_for_owner(
            self, received_website_id: object, received_owner_id: object
        ) -> list[object]:
            calls.append((received_website_id, received_owner_id))
            return [item]

        async def create_custom(
            self,
            received_website_id: object,
            received_owner_id: object,
            hostname: str,
            idempotency_key: str,
            received_provider: object,
        ) -> object:
            calls.append(
                (
                    received_website_id,
                    received_owner_id,
                    hostname,
                    idempotency_key,
                    received_provider,
                )
            )
            return item

        async def verify_custom(
            self, domain_id: object, received_owner_id: object, received_provider: object
        ) -> object:
            calls.append((domain_id, received_owner_id, received_provider))
            return item

    monkeypatch.setattr(publishing, "DomainService", DomainCommands)
    website = SimpleNamespace(
        id=website_id, owner_user_id=owner_id, status="DRAFT", active_deployment_id=None
    )

    listed = await publishing.domains(
        website_id,
        identity,
        MutationSession(website),  # type: ignore[arg-type]
    )
    assert [entry.id for entry in listed] == [item.id]
    assert calls == [(website_id, owner_id)]

    create_session = MutationSession()
    created = await publishing.create_custom_domain(
        website_id,
        publishing.DomainCreateRequest(hostname="www.example.com"),
        mutation_request(),
        identity,
        create_session,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        "domain-command-key-0001",
    )
    assert created.id == item.id
    assert calls[-1] == (
        website_id,
        owner_id,
        "www.example.com",
        "domain-command-key-0001",
        provider,
    )
    assert create_session.commits == 1 and create_session.refreshed == [item]
    assert audits[-1]["target_id"] == str(item.id)

    verify_session = MutationSession(website, item)
    verified = await publishing.verify_custom_domain(
        website_id,
        item.id,
        mutation_request(),
        identity,
        verify_session,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )
    assert verified.state == "VERIFIED"
    assert calls[-1] == (item.id, owner_id, provider)
    assert verify_session.commits == 1
    assert audits[-1]["metadata"] == {"website_id": str(website_id), "state": "VERIFIED"}


@pytest.mark.asyncio
async def test_domain_verification_rejects_cross_website_identifier_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    website_id = uuid4()
    owner_id = uuid4()
    identity = SimpleNamespace(user=SimpleNamespace(id=owner_id))
    audits: list[dict[str, object]] = []
    patch_command_guards(monkeypatch, audits)
    website = SimpleNamespace(id=website_id, owner_user_id=owner_id)

    with pytest.raises(Exception, match="Custom domain not found"):
        await publishing.verify_custom_domain(
            website_id,
            uuid4(),
            mutation_request(),
            identity,
            MutationSession(website, None),  # type: ignore[arg-type]
            SimpleNamespace(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
        )
    assert audits == []


@pytest.mark.asyncio
async def test_rollback_command_uses_authenticated_owner_and_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    website_id = uuid4()
    owner_id = uuid4()
    target_id = uuid4()
    queued = deployment(website_id, uuid4())
    identity = SimpleNamespace(user=SimpleNamespace(id=owner_id))
    audits: list[dict[str, object]] = []
    patch_command_guards(monkeypatch, audits)
    calls: list[tuple[object, ...]] = []

    class RollbackCommands:
        def __init__(self, _: object) -> None:
            return None

        async def queue_rollback(self, *args: object) -> object:
            calls.append(args)
            return queued

    monkeypatch.setattr(publishing, "DeploymentService", RollbackCommands)
    session = MutationSession()
    response = await publishing.rollback(
        website_id,
        publishing.RollbackRequest(deployment_id=target_id),
        mutation_request(),
        identity,
        session,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        "rollback-command-key-0001",
    )
    assert response.id == queued.id
    assert calls == [
        (website_id, owner_id, target_id, "rollback-command-key-0001", "correlation-id")
    ]
    assert session.commits == 1 and session.refreshed == [queued]
    assert audits[-1]["metadata"] == {
        "website_id": str(website_id),
        "target_deployment_id": str(target_id),
    }


def test_idempotency_key_rejects_missing_or_short_values() -> None:
    for value in (None, "too-short"):
        with pytest.raises(Exception, match="Idempotency-Key"):
            publishing._idempotency_key(value)
