from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
import zylora_api.api.editor as api
from starlette.requests import Request
from zylora_api.core.config import Settings
from zylora_api.db.website_models import AiOperation, Website, WebsiteVersion
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.editor.provider import DisabledPlanner
from zylora_api.modules.editor.schemas import AiEditRequest, ManualEditRequest, RestoreRequest
from zylora_api.modules.editor.service import AppliedEdit


def website(owner_id: UUID) -> Website:
    now = datetime.now(UTC)
    return Website(
        id=uuid4(),
        owner_user_id=owner_id,
        source_template_version_id=uuid4(),
        display_name="Editor Draft",
        status="DRAFT",
        theme={},
        revision=2,
        current_version_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


def version(site: Website, owner_id: UUID) -> WebsiteVersion:
    return WebsiteVersion(
        id=site.current_version_id,
        website_id=site.id,
        revision=site.revision,
        parent_version_id=None,
        schema_version="1.0.0",
        document={"schema_version": "1.0.0", "pages": []},
        page_state=[],
        checksum="a" * 64,
        source="MANUAL",
        actor_user_id=owner_id,
        operation_id=uuid4(),
        edit_summary="Saved heading",
        validation_status="VALID",
        validation_results={"valid": True},
        created_at=datetime.now(UTC),
    )


class FakeSession:
    operations: list[AiOperation]

    def __init__(self) -> None:
        self.commits = 0
        self.operations = []

    async def commit(self) -> None:
        self.commits += 1

    async def scalars(self, statement: object) -> object:
        del statement
        return SimpleNamespace(all=lambda: self.operations)


class FakeRevisionService:
    site_version: ClassVar[WebsiteVersion]

    def __init__(self, session: object) -> None:
        del session

    async def current(self, site: Website) -> WebsiteVersion:
        assert site.id == self.site_version.website_id
        return self.site_version

    async def history(self, website_id: UUID) -> list[WebsiteVersion]:
        assert website_id == self.site_version.website_id
        return [self.site_version]


class FakeCreditService:
    def __init__(self, session: object) -> None:
        del session

    async def account(self, user_id: UUID) -> object:
        assert user_id
        now = datetime.now(UTC)
        return SimpleNamespace(
            balance=12,
            allowance=15,
            period_start=now,
            period_end=now + timedelta(days=30),
        )


class FakeWebsiteService:
    site: ClassVar[Website]

    def __init__(self, session: object) -> None:
        del session

    async def get_for_owner(self, website_id: UUID, owner_id: UUID) -> Website:
        assert website_id == self.site.id and owner_id == self.site.owner_user_id
        return self.site


class FakeEditorService:
    applied: ClassVar[AppliedEdit]

    def __init__(self, session: object) -> None:
        del session

    async def manual_edit(
        self, website_id: UUID, owner_id: UUID, payload: ManualEditRequest
    ) -> AppliedEdit:
        assert website_id == self.applied.website.id and owner_id and payload.operations
        return self.applied

    async def ai_edit(
        self,
        website_id: UUID,
        owner_id: UUID,
        payload: AiEditRequest,
        planner: object,
        safety_identifier: str,
    ) -> AppliedEdit:
        assert (
            website_id and owner_id and payload.prompt and planner and len(safety_identifier) == 64
        )
        return self.applied

    async def restore(
        self,
        website_id: UUID,
        owner_id: UUID,
        version_id: UUID,
        operation_id: UUID,
        base_revision: int,
    ) -> AppliedEdit:
        assert website_id and owner_id and version_id and operation_id and base_revision == 2
        return self.applied


class FakeAudit:
    events: ClassVar[list[str]] = []

    def __init__(self, session: object, crypto: object) -> None:
        del session, crypto

    def record(self, event_type: str, **kwargs: object) -> None:
        assert kwargs["metadata"]
        self.events.append(event_type)


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/websites/site/editor/edits",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "state": {"correlation_id": "phase6-http"},
        }
    )


def setup(monkeypatch: pytest.MonkeyPatch) -> tuple[Website, WebsiteVersion, object, FakeSession]:
    owner_id = uuid4()
    site = website(owner_id)
    site_version = version(site, owner_id)
    FakeWebsiteService.site = site
    FakeRevisionService.site_version = site_version
    FakeEditorService.applied = AppliedEdit(site, site_version, 1)
    monkeypatch.setattr(api, "WebsiteService", FakeWebsiteService)
    monkeypatch.setattr(api, "RevisionService", FakeRevisionService)
    monkeypatch.setattr(api, "AiCreditService", FakeCreditService)
    monkeypatch.setattr(api, "EditorService", FakeEditorService)

    async def record_product_event(*args: object, **kwargs: object) -> tuple[object, bool]:
        del args, kwargs
        return SimpleNamespace(), True

    monkeypatch.setattr(api.ProductAnalyticsService, "record_event", record_product_event)
    return site, site_version, SimpleNamespace(user=SimpleNamespace(id=owner_id)), FakeSession()


@pytest.mark.asyncio
async def test_state_and_mutation_response_include_revision_history_and_credit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site, site_version, identity, session = setup(monkeypatch)
    state = await api.state_response(session, site, identity.user.id)  # type: ignore[arg-type]
    assert state.revision == 2 and state.credits.balance == 12
    assert state.revisions[0].checksum == site_version.checksum
    mutation = await api.mutation_response(
        session,
        AppliedEdit(site, site_version, 1),
        identity.user.id,
        uuid4(),
        "AI",
    )  # type: ignore[arg-type]
    assert mutation.source == "AI" and mutation.credits_used == 1


def test_security_audit_and_planner_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    site, _version, identity, session = setup(monkeypatch)
    checks: list[str] = []
    monkeypatch.setattr(api, "require_json_origin", lambda *args: checks.append("origin"))
    monkeypatch.setattr(api, "require_csrf", lambda *args: checks.append("csrf"))
    monkeypatch.setattr(api, "AuditService", FakeAudit)
    FakeAudit.events = []
    settings = Settings(environment="test", storage_provider="memory", _env_file=None)
    crypto = AuthCrypto("phase6-http-secret-long-enough")
    api.secure_mutation(request(), identity, settings, crypto)  # type: ignore[arg-type]
    api.record_edit_audit(
        session,
        crypto,
        request(),
        settings,
        identity,
        site.id,
        "AI",
        "Changed",
        1,  # type: ignore[arg-type]
    )
    assert checks == ["origin", "csrf"]
    assert FakeAudit.events == ["website.editor_change_applied"]
    assert isinstance(api.planner_dependency(settings), DisabledPlanner)


@pytest.mark.asyncio
async def test_editor_endpoints_apply_commit_restore_and_list_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site, site_version, identity, session = setup(monkeypatch)
    monkeypatch.setattr(api, "secure_mutation", lambda *args: None)
    monkeypatch.setattr(api, "record_edit_audit", lambda *args: None)
    settings = Settings(environment="test", storage_provider="memory", _env_file=None)
    crypto = AuthCrypto("phase6-http-secret-long-enough")
    operation_id = uuid4()
    manual = ManualEditRequest(
        operation_id=operation_id,
        base_revision=2,
        scope="PAGE",
        selected_page_id=uuid4(),
        summary="Save heading",
        operations=[
            {
                "kind": "SET_COMPONENT_PROP",
                "page_id": uuid4(),
                "component_id": "hero-home",
                "property": "heading",
                "value": "New heading",
            }
        ],
    )
    result = await api.manual_edit(
        site.id,
        manual,
        request(),
        identity,
        session,
        settings,
        crypto,  # type: ignore[arg-type]
    )
    assert result.source == "MANUAL"

    ai_payload = AiEditRequest(
        operation_id=uuid4(),
        base_revision=2,
        prompt="Rewrite this heading",
        scope="WEBSITE",
    )
    ai_result = await api.ai_edit(
        site.id,
        ai_payload,
        request(),
        identity,
        session,  # type: ignore[arg-type]
        settings,
        crypto,
        DisabledPlanner(),
    )
    assert ai_result.source == "AI"

    restored = await api.restore_revision(
        site.id,
        site_version.id,
        RestoreRequest(operation_id=uuid4(), base_revision=2),
        request(),
        identity,
        session,  # type: ignore[arg-type]
        settings,
        crypto,
    )
    assert restored.source == "RESTORE" and session.commits == 3

    state = await api.editor_state(site.id, identity, session)  # type: ignore[arg-type]
    assert state.website_id == site.id and session.commits == 4

    session.operations = [
        AiOperation(
            id=uuid4(),
            user_id=identity.user.id,
            website_id=site.id,
            status="SUCCEEDED",
            scope="WEBSITE",
            prompt_digest="a" * 64,
            provider="TEST",
            model="test-model",
            prompt_template_version="1",
            base_revision=1,
            cost_credits=1,
            usage={"input_tokens": 10},
            latency_ms=3,
            created_at=datetime.now(UTC),
        )
    ]
    usage = await api.ai_usage(site.id, identity, session)  # type: ignore[arg-type]
    assert usage.items[0].cost_credits == 1
