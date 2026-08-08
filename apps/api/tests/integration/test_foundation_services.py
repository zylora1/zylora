from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from zylora_api.core.config import get_settings
from zylora_api.db.session import get_engine


@pytest.mark.integration
async def test_postgresql_migration_and_uuidv7_foundation() -> None:
    engine = get_engine()
    key = f"integration-{uuid4()}"
    async with engine.begin() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision == "20260808_0001"
        column_rows = await connection.execute(
            text(
                "SELECT table_name || '.' || column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name IN ('outbox_events', 'job_runs')"
            )
        )
        assert {
            "outbox_events.lease_owner",
            "outbox_events.leased_until",
            "job_runs.dead_lettered_at",
        }.issubset(set(column_rows.scalars()))
        foreign_key_count = await connection.scalar(
            text(
                "SELECT count(*) FROM pg_constraint "
                "WHERE conrelid = 'job_runs'::regclass AND contype = 'f'"
            )
        )
        assert foreign_key_count == 1
        outbox_id = await connection.scalar(
            text(
                "INSERT INTO outbox_events "
                "(aggregate_type, aggregate_id, event_type, payload, correlation_id) "
                "VALUES ('Foundation', uuidv7(), 'foundation.checked', '{}'::jsonb, :key) "
                "RETURNING id"
            ),
            {"key": key},
        )
        assert outbox_id.version == 7
        await connection.execute(
            text("DELETE FROM outbox_events WHERE correlation_id = :key"), {"key": key}
        )


@pytest.mark.integration
async def test_redis_transport_is_reachable() -> None:
    client = Redis.from_url(get_settings().redis_url)
    try:
        assert await client.ping() is True
    finally:
        await client.aclose()
