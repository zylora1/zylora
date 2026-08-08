"""Create platform foundation tables.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08 22:00:00+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("event_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("state IN ('PENDING','PUBLISHED','FAILED')", name="ck_outbox_events_state"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_events_dispatch",
        "outbox_events",
        ["state", "available_at", "created_at"],
        unique=False,
    )
    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("outbox_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_name", sa.String(length=160), nullable=False),
        sa.Column("queue", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=24), server_default="PENDING", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(length=100), nullable=True),
        sa.Column("safe_error_detail", sa.Text(), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','DEAD_LETTER','CANCELLED')",
            name="ck_job_runs_state",
        ),
        sa.ForeignKeyConstraint(["outbox_event_id"], ["outbox_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("outbox_event_id"),
    )
    op.create_index(
        "ix_job_runs_operations", "job_runs", ["state", "queue", "created_at"], unique=False
    )
    op.create_table(
        "platform_metadata",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        sa.text(
            "INSERT INTO platform_metadata (key, value) "
            "VALUES ('foundation', '{\"phase\": 1, \"status\": \"initialized\"}'::jsonb)"
        )
    )


def downgrade() -> None:
    op.drop_table("platform_metadata")
    op.drop_index("ix_job_runs_operations", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_index("ix_outbox_events_dispatch", table_name="outbox_events")
    op.drop_table("outbox_events")
