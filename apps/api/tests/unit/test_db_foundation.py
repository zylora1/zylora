from collections.abc import AsyncGenerator

from sqlalchemy import CheckConstraint
from zylora_api.db.base import Base
from zylora_api.db.models import JobRun, OutboxEvent, PlatformMetadata
from zylora_api.db.session import get_session, normalize_async_database_url


def test_metadata_contains_platform_auth_template_and_website_tables() -> None:
    assert set(Base.metadata.tables) == {
        "ai_credit_accounts",
        "analytics_events",
        "analytics_daily_rollups",
        "ai_credit_ledger",
        "ai_operations",
        "audit_logs",
        "auth_attempts",
        "chatbots",
        "chatbot_knowledge_chunks",
        "chatbot_knowledge_indexes",
        "chat_conversations",
        "chat_messages",
        "auth_identities",
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
        "website_pages",
        "websites",
        "website_versions",
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
