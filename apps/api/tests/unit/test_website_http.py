from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import ClassVar
from uuid import UUID, uuid4

import zylora_api.api.websites as api
from starlette.requests import Request
from zylora_api.core.config import Settings
from zylora_api.db.website_models import Website, WebsitePage
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.websites.schemas import (
    InstantiateRequest,
    PageCreateRequest,
    PageDeleteRequest,
    PageUpdateRequest,
)
from zylora_api.modules.websites.service import PageMutationResult, PathChange


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeService:
    website: Website
    page_values: list[WebsitePage]

    def __init__(self, session: object) -> None:
        self.session = session

    async def list_for_owner(self, owner_id: UUID) -> list[Website]:
        return [self.website]

    async def get_draft_status(self, owner_id: UUID) -> tuple[int, str | None, object]:
        return (1, None, None)

    async def get_for_owner(self, website_id: UUID, owner_id: UUID) -> Website:
        return self.website

    async def instantiate(self, slug: str, owner_id: UUID) -> Website:
        return self.website

    async def pages(self, website_id: UUID) -> list[WebsitePage]:
        return self.page_values

    async def add_page(
        self, website_id: UUID, owner_id: UUID, payload: PageCreateRequest
    ) -> PageMutationResult:
        return PageMutationResult(self.website, [])

    async def update_page(
        self,
        website_id: UUID,
        page_id: UUID,
        owner_id: UUID,
        payload: PageUpdateRequest,
    ) -> PageMutationResult:
        return PageMutationResult(
            self.website,
            [PathChange(page_id=page_id, old_path="/about", new_path="/company")],
        )

    async def delete_page(
        self, website_id: UUID, page_id: UUID, owner_id: UUID
    ) -> PageMutationResult:
        return PageMutationResult(self.website, [])


class FakeAudit:
    events: ClassVar[list[str]] = []

    def __init__(self, session: object, crypto: object) -> None:
        pass

    def record(self, event_type: str, **kwargs: object) -> None:
        self.events.append(event_type)


def state() -> tuple[Website, list[WebsitePage], object]:
    now = datetime.now(UTC)
    owner = uuid4()
    website = Website(
        id=uuid4(),
        owner_user_id=owner,
        source_template_version_id=uuid4(),
        display_name="Haven Draft",
        status="DRAFT",
        created_at=now,
        updated_at=now,
    )
    root = WebsitePage(
        id=uuid4(),
        website_id=website.id,
        source_template_page_id="home",
        parent_page_id=None,
        name="Home",
        slug="",
        sort_order=0,
        is_home=True,
        show_in_navigation=True,
        status="DRAFT",
        content={"components": []},
        seo={},
        created_at=now,
        updated_at=now,
    )
    about = WebsitePage(
        id=uuid4(),
        website_id=website.id,
        source_template_page_id="about",
        parent_page_id=None,
        name="About",
        slug="about",
        sort_order=1,
        is_home=False,
        show_in_navigation=True,
        status="DRAFT",
        content={"components": []},
        seo={},
        created_at=now,
        updated_at=now,
    )
    return website, [root, about], SimpleNamespace(user=SimpleNamespace(id=owner))


async def test_user_website_list_and_detail_serialize_paths(monkeypatch: object) -> None:
    website, pages, identity = state()
    FakeService.website = website
    FakeService.page_values = pages
    monkeypatch.setattr(api, "WebsiteService", FakeService)  # type: ignore[attr-defined]
    session = FakeSession()
    listed = await api.list_websites(identity, session)
    detail = await api.website_detail(website.id, identity, session)  # type: ignore[arg-type]
    assert [page.path for page in listed.items[0].pages] == ["/", "/about"]
    assert detail.owner_user_id == identity.user.id and session.commits == 2


async def test_instantiation_command_is_audited_and_committed(monkeypatch: object) -> None:
    website, pages, identity = state()
    FakeService.website = website
    FakeService.page_values = pages
    FakeAudit.events = []
    monkeypatch.setattr(api, "WebsiteService", FakeService)
    monkeypatch.setattr(api, "AuditService", FakeAudit)
    monkeypatch.setattr(api, "require_json_origin", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "require_csrf", lambda *args, **kwargs: None)  # type: ignore[attr-defined]
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/templates/haven/instantiate",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "state": {"correlation_id": "phase4"},
        }
    )
    session = FakeSession()
    result = await api.instantiate(
        "haven",
        InstantiateRequest(),
        request,
        identity,
        session,
        Settings(environment="test", storage_provider="memory", _env_file=None),
        AuthCrypto("website-http-secret-long-enough-123"),
    )  # type: ignore[arg-type]
    assert (
        result.status == "DRAFT"
        and FakeAudit.events == ["website.instantiated_from_template"]
        and session.commits == 1
    )


async def test_page_mutations_are_protected_audited_and_return_path_changes(
    monkeypatch: object,
) -> None:
    website, pages, identity = state()
    FakeService.website = website
    FakeService.page_values = pages
    FakeAudit.events = []
    monkeypatch.setattr(api, "WebsiteService", FakeService)
    monkeypatch.setattr(api, "AuditService", FakeAudit)
    monkeypatch.setattr(api, "require_json_origin", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "require_csrf", lambda *args, **kwargs: None)
    request = Request(
        {
            "type": "http",
            "method": "PATCH",
            "path": f"/api/v1/websites/{website.id}/pages/{pages[1].id}",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "state": {"correlation_id": "phase5"},
        }
    )
    session = FakeSession()
    settings = Settings(environment="test", storage_provider="memory", _env_file=None)
    crypto = AuthCrypto("website-http-secret-long-enough-123")
    await api.add_page(
        website.id,
        PageCreateRequest(name="Contact", slug="contact"),
        request,
        identity,
        session,
        settings,
        crypto,
    )
    updated = await api.update_page(
        website.id,
        pages[1].id,
        PageUpdateRequest(name="Company"),
        request,
        identity,
        session,
        settings,
        crypto,
    )
    await api.delete_page(
        website.id,
        pages[1].id,
        PageDeleteRequest(confirm=True, child_strategy="PROMOTE"),
        request,
        identity,
        session,
        settings,
        crypto,
    )
    assert [item.old_path for item in updated.path_changes] == ["/about"]
    assert FakeAudit.events == [
        "website.page_added",
        "website.page_updated",
        "website.page_deleted",
    ]
    assert session.commits == 3
