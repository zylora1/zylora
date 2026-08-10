from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.blog_models import BlogTag
from zylora_api.db.campaign_models import CampaignRecipient, EmailSuppression
from zylora_api.db.models import OutboxEvent
from zylora_api.db.session import get_engine
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.blog.service import BlogService
from zylora_api.modules.campaigns.service import CampaignService


class Provider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[tuple[str, str, str]] = []

    async def send_transactional(self, *, recipient: str, subject: str, body: str) -> None:
        if self.fail:
            raise RuntimeError("provider unavailable")
        self.messages.append((recipient, subject, body))


async def user(session: AsyncSession, email: str) -> User:
    model = User(
        account_type="USER",
        normalized_email=email,
        display_email=email,
        status="ACTIVE",
        verified_at=datetime.now(UTC),
        billing_country_code="ZZ",
    )
    session.add(model)
    await session.flush()
    return model


@pytest.mark.integration
async def test_campaign_audience_snapshot_suppression_delivery_retry_and_unsubscribe() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    crypto = AuthCrypto("phase13-campaign-secret-long-enough")
    async with factory() as session:
        admin = await user(session, f"phase13-admin-{uuid4().hex}@example.com")
        first = await user(session, f"phase13-first-{uuid4().hex}@example.com")
        second = await user(session, f"phase13-second-{uuid4().hex}@example.com")
        service = CampaignService(session, crypto)
        campaign = await service.create(
            actor_user_id=admin.id,
            name="August update",
            subject="New capabilities",
            body="A considered update for your Website.",
            audience_type="ALL_USERS",
        )
        with pytest.raises(AuthProblem, match="audience is invalid"):
            await service.update(
                campaign.id,
                name="August update",
                subject="New capabilities",
                body="A considered update for your Website.",
                audience_type="PLAN_USERS",
                audience_plan_code=None,
            )
        await service.update(
            campaign.id,
            name="August update revised",
            subject="New capabilities",
            body="A considered update for your Website.",
            audience_type="ALL_USERS",
            audience_plan_code=None,
        )
        await service.ready(campaign.id)
        with pytest.raises(AuthProblem, match="future"):
            await service.schedule(campaign.id, datetime.now(UTC))
        session.add(
            EmailSuppression(
                recipient_user_id=second.id,
                scope="MARKETING",
                reason="recipient_opt_out",
                source="test",
            )
        )
        await service.start(campaign.id, correlation_id="phase13-campaign-send")
        recipients = list(
            (
                await session.scalars(
                    select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id)
                )
            ).all()
        )
        assert campaign.state == "SENDING" and campaign.audience_snapshot_count >= 2
        suppressed = next(row for row in recipients if row.recipient_user_id == second.id)
        pending = next(row for row in recipients if row.recipient_user_id == first.id)
        assert suppressed.state == "SUPPRESSED" and pending.state == "PENDING"
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == pending.id).with_for_update()
        )
        assert event is not None
        provider = Provider()
        assert (await service.process_outbox_event(event.id, provider)).state == "PUBLISHED"
        assert pending.state == "SENT" and provider.messages[0][0] == first.display_email
        assert "Unsubscribe: /unsubscribe?token=" in provider.messages[0][2]
        assert (await service.process_outbox_event(event.id, provider)).state == "PUBLISHED"
        assert len(provider.messages) == 1
        purpose = f"campaign-unsubscribe:{campaign.id}:{first.id}"
        token = crypto.decrypt(pending.unsubscribe_token_ciphertext, purpose=f"{purpose}:token")
        unsubscribed = await service.unsubscribe(token)
        assert unsubscribed.id == pending.id and unsubscribed.state == "UNSUBSCRIBED"
        assert await session.scalar(
            select(EmailSuppression).where(EmailSuppression.recipient_user_id == first.id)
        )
        with pytest.raises(AuthProblem, match="invalid or expired"):
            await service.unsubscribe(crypto.token())
        await session.commit()


@pytest.mark.integration
async def test_campaign_delivery_failures_and_lifecycle_protection() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    crypto = AuthCrypto("phase13-campaign-failure-secret-long-enough")
    async with factory() as session:
        admin = await user(session, f"phase13-failure-admin-{uuid4().hex}@example.com")
        recipient_user = await user(session, f"phase13-failure-user-{uuid4().hex}@example.com")
        service = CampaignService(session, crypto)
        campaign = await service.create(
            actor_user_id=admin.id,
            name="Failure test",
            subject="Still queued",
            body="Provider failure must not claim success.",
            audience_type="RECENT_USERS",
        )
        with pytest.raises(AuthProblem, match="Prepare"):
            await service.start(campaign.id, correlation_id="phase13-failure")
        await service.ready(campaign.id)
        await service.start(campaign.id, correlation_id="phase13-failure")
        recipient = await session.scalar(
            select(CampaignRecipient).where(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.recipient_user_id == recipient_user.id,
            )
        )
        assert recipient is not None
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == recipient.id)
        )
        assert event is not None
        for _ in range(4):
            await service.process_outbox_event(event.id, Provider(fail=True))
        assert recipient.state == "FAILED" and event.state == "FAILED"
        with pytest.raises(AuthProblem, match="can no longer be cancelled"):
            await service.cancel(campaign.id)
        await session.commit()


@pytest.mark.integration
async def test_blog_draft_publish_schedule_taxonomy_and_safe_public_projection() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        author = await user(session, f"phase13-blog-{uuid4().hex}@example.com")
        service = BlogService(session)
        payload: dict[str, object] = {
            "title": "A safer Website workflow",
            "slug": f"safer-website-workflow-{uuid4().hex[:10]}",
            "excerpt": "A clear account of the production workflow.",
            "content": "First paragraph with <script>alert(1)</script>.\n\nSecond paragraph.",
            "featured_image_url": "https://cdn.example.com/hero.jpg",
            "categories": ["Product notes"],
            "tags": ["Security", "Publishing"],
            "seo_title": "Safer Website workflow",
            "meta_description": "A secure template-first Website workflow.",
            "canonical_url": "https://www.zylora.example/blog/safer-website-workflow",
            "og_title": "Safer Website workflow",
            "og_description": "A secure template-first Website workflow.",
        }
        with pytest.raises(AuthProblem, match="URL"):
            await service.create(
                actor_user_id=author.id, payload={**payload, "slug": "unsafe slug"}
            )
        post = await service.create(actor_user_id=author.id, payload=payload)
        summary = await service.summary(post)
        assert summary.categories == ["Product notes"] and summary.tags == [
            "Publishing",
            "Security",
        ]
        with pytest.raises(AuthProblem, match="not found"):
            await service.public_get(post.slug)
        await service.update(
            post.id, payload={**payload, "title": "A safer Website workflow, revised"}
        )
        await service.ready(post.id)
        with pytest.raises(AuthProblem, match="future"):
            await service.schedule(post.id, datetime.now(UTC))
        scheduled = await service.schedule(post.id, datetime.now(UTC) + timedelta(minutes=10))
        assert scheduled.state == "SCHEDULED"
        scheduled.scheduled_at = datetime.now(UTC) - timedelta(seconds=1)
        assert scheduled.id in await service.due_post_ids(10)
        published = await service.publish(post.id, correlation_id="phase13-blog-publish")
        assert published.state == "PUBLISHED" and published.published_at is not None
        with pytest.raises(AuthProblem, match="cannot be edited"):
            await service.update(post.id, payload=payload)
        with pytest.raises(AuthProblem, match="Only draft Blog posts"):
            await service.ready(post.id)
        with pytest.raises(AuthProblem, match="Prepare"):
            await service.schedule(post.id, datetime.now(UTC) + timedelta(hours=1))
        projection = await service.public_get(post.slug)
        html = service.render_html(projection.content)
        assert "<script>" not in html and "&lt;script&gt;" in html
        assert (await service.public_list())[0].slug == post.slug
        with pytest.raises(AuthProblem, match="already in use"):
            await service.create(actor_user_id=author.id, payload=payload)
        taxonomy = await service._taxonomy(BlogTag, f"Extra {uuid4().hex[:8]}")
        assert taxonomy.slug.startswith("extra-")
        taxonomy = await service._taxonomy(BlogTag, f"Extra {uuid4().hex[:8]}")
        assert taxonomy.slug.startswith("extra-")
        await service.unpublish(post.id)
        with pytest.raises(AuthProblem, match="Prepare"):
            await service.publish(post.id, correlation_id="phase13-not-ready")
        with pytest.raises(AuthProblem, match="Prepare"):
            await service.schedule(post.id, datetime.now(UTC) + timedelta(hours=1))
        with pytest.raises(AuthProblem, match="not found"):
            await service._locked_post(uuid4())
        assert service._optional_url(None) is None
        assert service._optional_string(None, 180) is None
        assert service._names(None) == []
        with pytest.raises(AuthProblem, match="Only published"):
            await service.unpublish(post.id)
        with pytest.raises(AuthProblem, match="categories or tags"):
            service._names(["valid", 5])
        with pytest.raises(AuthProblem, match="HTTPS"):
            service._optional_url("http://insecure.example")
        with pytest.raises(AuthProblem, match="SEO metadata"):
            service._optional_string("", 180)
        with pytest.raises(AuthProblem, match="Blog title"):
            service._string({}, "title", 180)
        with pytest.raises(AuthProblem, match="category and tag"):
            service.slugify("###")
        assert (await service.list_admin())[0].state == "DRAFT"
        await session.commit()


@pytest.mark.integration
async def test_campaign_scheduling_terminal_and_safe_failure_paths() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    crypto = AuthCrypto("phase13-campaign-branches-secret-long-enough")
    async with factory() as session:
        actor = await user(session, f"phase13-branches-{uuid4().hex}@example.com")
        service = CampaignService(session, crypto)
        assert await service.list(0) == []
        draft = await service.create(
            actor_user_id=actor.id,
            name="Branch coverage",
            subject="Safe paths",
            body="Every outcome remains auditable.",
            audience_type="FREE_USERS",
        )
        with pytest.raises(AuthProblem, match="Prepare"):
            await service.schedule(draft.id, datetime.now(UTC) + timedelta(hours=1))
        assert (await service.cancel(draft.id)).state == "CANCELLED"
        ready = await service.create(
            actor_user_id=actor.id,
            name="Scheduled update",
            subject="Scheduled",
            body="Provider work starts later.",
            audience_type="ALL_USERS",
        )
        await service.ready(ready.id)
        await service.schedule(ready.id, datetime.now(UTC) + timedelta(hours=1))
        with pytest.raises(AuthProblem, match="not due"):
            await service.start(ready.id, correlation_id="phase13-not-due")
        ready.scheduled_at = datetime.now(UTC) - timedelta(seconds=1)
        assert ready.id in await service.due_campaign_ids(100)
        await service.start(ready.id, correlation_id="phase13-due")
        recipient = await session.scalar(
            select(CampaignRecipient).where(CampaignRecipient.campaign_id == ready.id)
        )
        assert recipient is not None
        unknown = uuid4()
        with pytest.raises(AuthProblem, match="job not found"):
            await service.process_outbox_event(unknown, Provider())
        unsupported = OutboxEvent(
            aggregate_type="CAMPAIGN_RECIPIENT",
            aggregate_id=uuid4(),
            event_type="campaign.unsupported",
            payload={},
            correlation_id="phase13-unsupported",
        )
        missing = OutboxEvent(
            aggregate_type="CAMPAIGN_RECIPIENT",
            aggregate_id=uuid4(),
            event_type="campaign.delivery_requested",
            payload={"campaign_recipient_id": str(uuid4())},
            correlation_id="phase13-missing",
        )
        session.add_all([unsupported, missing])
        await session.flush()
        assert (await service.process_outbox_event(unsupported.id, Provider())).state == "FAILED"
        assert (await service.process_outbox_event(missing.id, Provider())).state == "FAILED"
        terminal_event = OutboxEvent(
            aggregate_type="CAMPAIGN_RECIPIENT",
            aggregate_id=recipient.id,
            event_type="campaign.delivery_requested",
            payload={"campaign_recipient_id": str(recipient.id)},
            correlation_id="phase13-terminal",
        )
        recipient.state = "SENT"
        session.add(terminal_event)
        await session.flush()
        assert (
            await service.process_outbox_event(terminal_event.id, Provider())
        ).state == "PUBLISHED"
        recipient.state = "PENDING"
        ready.state = "PAUSED"
        paused_event = OutboxEvent(
            aggregate_type="CAMPAIGN_RECIPIENT",
            aggregate_id=recipient.id,
            event_type="campaign.delivery_requested",
            payload={"campaign_recipient_id": str(recipient.id)},
            correlation_id="phase13-paused",
        )
        session.add(paused_event)
        await session.flush()
        assert (
            await service.process_outbox_event(paused_event.id, Provider())
        ).last_error_code == "campaign_not_sending"
        for audience_type, plan in [
            ("PAID_USERS", None),
            ("PLAN_USERS", "BASIC"),
            ("HAS_DRAFT", None),
            ("NO_PUBLISHED_WEBSITE", None),
        ]:
            ready.audience_type, ready.audience_plan_code = audience_type, plan
            assert "SELECT" in str(service._audience_query(ready))
        summaries = await service.list(100)
        assert any(item.id == ready.id for item in summaries)
        with pytest.raises(AuthProblem, match="name, subject, or body"):
            await service.create(
                actor_user_id=actor.id, name="", subject="x", body="x", audience_type="ALL_USERS"
            )
        await session.commit()


@pytest.mark.integration
async def test_campaign_terminal_guards_and_remaining_server_validation() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    crypto = AuthCrypto("phase13-guards-secret-long-enough")
    async with factory() as session:
        actor = await user(session, f"phase13-guards-{uuid4().hex}@example.com")
        service = CampaignService(session, crypto)
        campaign = await service.create(
            actor_user_id=actor.id,
            name="Guards",
            subject="Subject",
            body="Body",
            audience_type="ALL_USERS",
        )
        with pytest.raises(AuthProblem, match="Campaign not found"):
            await service.ready(uuid4())
        await service.ready(campaign.id)
        with pytest.raises(AuthProblem, match="Only a draft"):
            await service.ready(campaign.id)
        with pytest.raises(AuthProblem, match="Only draft campaigns"):
            await service.update(
                campaign.id,
                name="Changed",
                subject="Subject",
                body="Body",
                audience_type="ALL_USERS",
                audience_plan_code=None,
            )
        with pytest.raises(AuthProblem, match="invalid"):
            await service.unsubscribe("short")
        for audience_type, plan in [("FREE_USERS", None), ("RECENT_USERS", None)]:
            campaign.audience_type, campaign.audience_plan_code = audience_type, plan
            assert "SELECT" in str(service._audience_query(campaign))
        await session.commit()
