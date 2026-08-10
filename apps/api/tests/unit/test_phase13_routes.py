from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from zylora_api.api import blog, campaigns
from zylora_api.app import create_app
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import RequestIdentity, get_admin_identity, get_crypto
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.blog.service import BlogPostSummary
from zylora_api.modules.campaigns.service import CampaignSummary


class FakeSession:
    def __init__(self, user: User) -> None:
        self.user = user
        self.commits = 0
        self.added: list[object] = []

    async def commit(self) -> None:
        self.commits += 1

    async def scalar(self, _: object) -> User:
        return self.user

    def add(self, value: object) -> None:
        self.added.append(value)


def campaign_summary() -> CampaignSummary:
    return CampaignSummary(
        id=UUID("00000000-0000-0000-0000-000000000013"),
        name="August update",
        subject="A good update",
        state="DRAFT",
        audience_type="ALL_USERS",
        audience_plan_code=None,
        audience_snapshot_count=0,
        scheduled_at=None,
        created_at=datetime(2026, 8, 10, tzinfo=UTC),
    )


def blog_summary(state: str = "DRAFT") -> BlogPostSummary:
    return BlogPostSummary(
        id=UUID("00000000-0000-0000-0000-000000000014"),
        title="A good article",
        slug="a-good-article",
        excerpt="A useful article.",
        state=state,
        scheduled_at=None,
        published_at=datetime(2026, 8, 10, tzinfo=UTC) if state == "PUBLISHED" else None,
        categories=["Product"],
        tags=["Security"],
    )


class FakeCampaigns:
    def __init__(self, _: object, __: object) -> None: ...

    async def list(self, _: int = 50) -> list[CampaignSummary]:
        return [campaign_summary()]

    async def create(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(**campaign_summary().__dict__)

    async def update(self, _: UUID, **__: object) -> SimpleNamespace:
        return SimpleNamespace(**campaign_summary().__dict__)

    async def ready(self, _: UUID) -> SimpleNamespace:
        return SimpleNamespace(**campaign_summary().__dict__)

    async def cancel(self, _: UUID) -> SimpleNamespace:
        return SimpleNamespace(**campaign_summary().__dict__)

    async def start(self, _: UUID, **__: object) -> SimpleNamespace:
        item = campaign_summary()
        return SimpleNamespace(**{**item.__dict__, "state": "SENDING"})

    async def schedule(self, _: UUID, when: datetime) -> SimpleNamespace:
        return SimpleNamespace(
            **{**campaign_summary().__dict__, "state": "SCHEDULED", "scheduled_at": when}
        )

    async def unsubscribe(self, _: str) -> SimpleNamespace:
        return SimpleNamespace(id=uuid4(), state="UNSUBSCRIBED")


class FakeEmail:
    def __init__(self, *_: object) -> None: ...

    async def queue(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(id=uuid4(), kind="ADMIN_TRANSACTIONAL")


class FakeBlog:
    def __init__(self, _: object) -> None: ...

    async def list_admin(self) -> list[BlogPostSummary]:
        return [blog_summary()]

    async def public_list(self, limit: int = 50) -> list[BlogPostSummary]:
        assert limit in {50, 10_000}
        return [blog_summary("PUBLISHED")]

    async def create(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(author_user_id=uuid4(), **blog_summary().__dict__)

    async def update(self, _: UUID, **__: object) -> SimpleNamespace:
        return SimpleNamespace(author_user_id=uuid4(), **blog_summary().__dict__)

    async def ready(self, _: UUID) -> SimpleNamespace:
        return SimpleNamespace(author_user_id=uuid4(), **blog_summary().__dict__)

    async def publish(self, _: UUID, **__: object) -> SimpleNamespace:
        summary = blog_summary("PUBLISHED")
        return SimpleNamespace(author_user_id=uuid4(), **summary.__dict__)

    async def unpublish(self, _: UUID) -> SimpleNamespace:
        return SimpleNamespace(author_user_id=uuid4(), **blog_summary().__dict__)

    async def schedule(self, _: UUID, when: datetime) -> SimpleNamespace:
        summary = blog_summary("SCHEDULED")
        return SimpleNamespace(author_user_id=uuid4(), **{**summary.__dict__, "scheduled_at": when})

    async def summary(self, _: object) -> BlogPostSummary:
        return blog_summary()

    async def public_get(self, _: str) -> SimpleNamespace:
        summary = blog_summary("PUBLISHED")
        return SimpleNamespace(
            **summary.__dict__,
            content="A safe public body.",
            featured_image_url=None,
            seo_title="SEO",
            meta_description="Description",
            og_title="OG",
            og_description="OG description",
        )

    @staticmethod
    def render_html(_: str) -> str:
        return "<p>A safe public body.</p>"


@pytest.mark.asyncio
async def test_phase13_campaign_and_blog_routes_are_admin_only_and_public_reads_are_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    crypto = AuthCrypto("phase13-route-secret-long-enough")
    admin = User(
        id=uuid4(),
        account_type="SUPER_ADMIN",
        normalized_email="admin@example.com",
        display_email="admin@example.com",
        status="ACTIVE",
        verified_at=now,
        billing_country_code="ZZ",
    )
    recipient = User(
        id=uuid4(),
        account_type="USER",
        normalized_email="recipient@example.com",
        display_email="recipient@example.com",
        status="ACTIVE",
        verified_at=now,
        billing_country_code="ZZ",
    )
    identity = RequestIdentity(
        Session(
            id=uuid4(),
            user_id=admin.id,
            token_hash=b"a" * 32,
            csrf_hash=crypto.digest("phase13-csrf", purpose="csrf:ADMIN_WEB"),
            audience="ADMIN_WEB",
            auth_epoch=1,
            expires_at=now + timedelta(hours=1),
        ),
        admin,
        "admin-token",
    )
    database = FakeSession(recipient)
    app = create_app()
    app.dependency_overrides[get_admin_identity] = lambda: identity
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_crypto] = lambda: crypto
    app.dependency_overrides[campaigns.get_settings] = lambda: Settings(
        environment="test", storage_provider="memory", _env_file=None
    )
    app.dependency_overrides[blog.get_settings] = lambda: Settings(
        environment="test", storage_provider="memory", _env_file=None
    )
    monkeypatch.setattr(campaigns, "CampaignService", FakeCampaigns)
    monkeypatch.setattr(campaigns, "TransactionalEmailService", FakeEmail)
    monkeypatch.setattr(blog, "BlogService", FakeBlog)
    headers = {"Origin": "http://admin.localhost:3000", "X-CSRF-Token": "phase13-csrf"}
    campaign_body = {
        "name": "August update",
        "subject": "A good update",
        "body": "The precise body.",
        "audience_type": "ALL_USERS",
        "audience_plan_code": None,
    }
    blog_body = {
        "title": "A good article",
        "slug": "a-good-article",
        "excerpt": "A useful article.",
        "content": "Safe body.",
        "categories": ["Product"],
        "tags": ["Security"],
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_admin_csrf", "phase13-csrf")
        assert (await client.get("/api/v1/admin/campaigns")).status_code == 200
        assert (
            await client.post("/api/v1/admin/campaigns", json=campaign_body, headers=headers)
        ).status_code == 201
        assert (
            await client.patch(
                "/api/v1/admin/campaigns/00000000-0000-0000-0000-000000000013",
                json=campaign_body,
                headers=headers,
            )
        ).status_code == 200
        for action in ("ready", "cancel", "send"):
            assert (
                await client.post(
                    f"/api/v1/admin/campaigns/00000000-0000-0000-0000-000000000013/{action}",
                    json={"reason": "Approved administrative action."},
                    headers=headers,
                )
            ).status_code == 200
        assert (
            await client.post(
                "/api/v1/admin/campaigns/00000000-0000-0000-0000-000000000013/schedule",
                json={"reason": "Approved schedule.", "scheduled_at": "2026-08-11T00:00:00Z"},
                headers=headers,
            )
        ).status_code == 200
        assert (
            await client.post(
                f"/api/v1/admin/users/{recipient.id}/administrative-email",
                json={
                    "subject": "Administrative note",
                    "body": "A secure transaction.",
                    "reason": "Customer request.",
                },
                headers=headers,
            )
        ).status_code == 202
        assert (
            await client.post("/api/v1/public/marketing/unsubscribe", json={"token": "x" * 32})
        ).status_code == 204
        assert (await client.get("/api/v1/admin/blog/posts")).status_code == 200
        assert (
            await client.post("/api/v1/admin/blog/posts", json=blog_body, headers=headers)
        ).status_code == 201
        assert (
            await client.patch(
                "/api/v1/admin/blog/posts/00000000-0000-0000-0000-000000000014",
                json=blog_body,
                headers=headers,
            )
        ).status_code == 200
        for action in ("ready", "publish", "unpublish"):
            assert (
                await client.post(
                    f"/api/v1/admin/blog/posts/00000000-0000-0000-0000-000000000014/{action}",
                    json={"reason": "Approved publication action."},
                    headers=headers,
                )
            ).status_code == 200
        assert (
            await client.post(
                "/api/v1/admin/blog/posts/00000000-0000-0000-0000-000000000014/schedule",
                json={"reason": "Approved schedule.", "scheduled_at": "2026-08-11T00:00:00Z"},
                headers=headers,
            )
        ).status_code == 200
        assert (await client.get("/api/v1/blog/posts")).json()[0]["state"] == "PUBLISHED"
        post = await client.get("/api/v1/blog/posts/a-good-article")
        assert post.status_code == 200 and post.json()["canonical_path"] == "/blog/a-good-article"
        assert (await client.get("/api/v1/blog/sitemap")).json()[0]["slug"] == "a-good-article"
    assert database.commits >= 12 and database.added
