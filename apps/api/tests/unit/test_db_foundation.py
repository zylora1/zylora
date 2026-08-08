from collections.abc import AsyncGenerator

from sqlalchemy import CheckConstraint
from zylora_api.db.base import Base
from zylora_api.db.models import JobRun, OutboxEvent, PlatformMetadata
from zylora_api.db.session import get_session, normalize_async_database_url


def test_foundation_metadata_contains_only_operational_tables_and_constraints() -> None:
    assert set(Base.metadata.tables) == {"outbox_events", "job_runs", "platform_metadata"}
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
