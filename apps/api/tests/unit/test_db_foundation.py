from collections.abc import AsyncGenerator

from sqlalchemy import CheckConstraint
from zylora_api.db.base import Base
from zylora_api.db.models import JobRun, OutboxEvent, PlatformMetadata
from zylora_api.db.session import get_session, normalize_async_database_url


def test_metadata_contains_platform_auth_template_and_website_tables() -> None:
    assert set(Base.metadata.tables) == {
        "acquisition_attributions",
        "ai_credit_accounts",
        "analytics_events",
        "analytics_daily_rollups",
        "ai_credit_ledger",
        "ai_operations",
        "ai_generation_artifacts",
        "ai_generation_events",
        "ai_generation_jobs",
        "ai_site_generations",
        "ai_site_projects",
        "audit_logs",
        "auth_attempts",
        "blog_categories",
        "blog_post_categories",
        "blog_post_tags",
        "blog_post_versions",
        "blog_posts",
        "blog_tags",
        "campaign_delivery_events",
        "campaign_recipients",
        "campaigns",
        "chatbots",
        "chatbot_knowledge_chunks",
        "chatbot_knowledge_indexes",
        "chat_conversations",
        "knowledge_sources",
        "chat_messages",
        "auth_identities",
        "email_suppressions",
        "email_verifications",
        "export_prices",
        "export_purchases",
        "website_export_artifacts",
        "deployment_events",
        "deployments",
        "domains",
        "job_runs",
        "oauth_transactions",
        "outbox_events",
        "password_resets",
        "platform_metadata",
        "sessions",
        "super_admin_profiles",
        "template_assets",
        "transactional_emails",
        "template_categories",
        "template_tag_assignments",
        "template_tags",
        "template_validations",
        "website_page_path_changes",
        "template_versions",
        "templates",
        "product_events",
        "website_digest_deliveries",
        "website_pages",
        "websites",
        "website_value_states",
        "website_versions",
        "zero_lead_checkpoints",
        "whatsapp_callback_events",
        "whatsapp_notification_settings",
        "whatsapp_notifications",
        "invoices",
        "leads",
        "lead_credit_accounts",
        "lead_credit_ledger",
        "notifications",
        "notification_quota_accounts",
        "notification_quota_ledger",
        "ownership_transfers",
        "payment_events",
        "payments",
        "plan_catalogs",
        "plan_entitlements",
        "plan_prices",
        "plans",
        "subscriptions",
        "website_ownerships",
        "pro_leads",
        "users",
    }
    assert OutboxEvent.__table__.c.id.server_default is not None
    assert JobRun.__table__.c.idempotency_key.unique is True
    assert OutboxEvent.__table__.c.leased_until.nullable is True
    assert JobRun.__table__.c.dead_lettered_at.nullable is True
    assert {foreign_key.target_fullname for foreign_key in JobRun.__table__.foreign_keys} == {
        "outbox_events.id"
    }
    assert PlatformMetadata.__table__.c.key.primary_key is True
    assert any(isinstance(item, CheckConstraint) for item in OutboxEvent.__table__.constraints)


def test_async_database_url_normalization_is_idempotent() -> None:
    plain = "postgresql://user:password@db.example/zylora"
    async_url = "postgresql+psycopg://user:password@db.example/zylora"
    assert normalize_async_database_url(plain) == async_url
    assert normalize_async_database_url(async_url) == async_url


async def test_session_dependency_yields_an_unconnected_session() -> None:
    dependency: AsyncGenerator[object] = get_session()
    session = await anext(dependency)
    assert session is not None
    await dependency.aclose()


def test_engine_applies_bounded_pool_and_postgresql_session_timeouts(monkeypatch) -> None:
    from zylora_api.core.config import Settings
    from zylora_api.db import session as db_session

    captured: dict[str, object] = {}

    def create(url: str, **kwargs: object) -> object:
        captured.update({"url": url, **kwargs})
        return object()

    settings = Settings(
        _env_file=None,
        database_pool_size=7,
        database_max_overflow=9,
        database_pool_timeout_seconds=11,
        database_pool_recycle_seconds=700,
        database_statement_timeout_ms=24000,
        database_lock_timeout_ms=4000,
    )
    db_session.get_engine.cache_clear()
    monkeypatch.setattr(db_session, "get_settings", lambda: settings)
    monkeypatch.setattr(db_session, "create_async_engine", create)
    try:
        db_session.get_engine()
    finally:
        db_session.get_engine.cache_clear()

    assert captured["pool_size"] == 7
    assert captured["max_overflow"] == 9
    assert captured["pool_timeout"] == 11
    assert captured["pool_recycle"] == 700
    assert captured["connect_args"] == {
        "options": "-c statement_timeout=24000 -c lock_timeout=4000"
    }
