"""durable isolated AI generation jobs and immutable artifacts

Revision ID: 20260821_0016
Revises: 20260820_0015
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260821_0016"
down_revision = "20260820_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_site_generations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_generation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(length=160), nullable=False),
        sa.Column("prompt_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("prompt_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="CREATED", nullable=False),
        sa.Column("retryable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column("provider_name", sa.String(length=80), nullable=True),
        sa.Column("provider_model", sa.String(length=160), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "state IN ('CREATED','QUEUED','CLAIMED','GENERATING','VALIDATING','SCANNING',"
            "'SANDBOXING','BUILDING','STORING','COMPLETED','FAILED','CANCELLED')",
            name="ck_ai_site_generations_state",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["ai_site_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["previous_generation_id"], ["ai_site_generations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "request_key", name="uq_ai_generations_project_request"),
        sa.UniqueConstraint(
            "project_id", "version_number", name="uq_ai_generations_project_version"
        ),
    )
    op.create_index(
        "ix_ai_generations_owner_created", "ai_site_generations", ["owner_user_id", "created_at"]
    )
    op.create_index(
        "ix_ai_generations_project_created", "ai_site_generations", ["project_id", "created_at"]
    )

    op.create_table(
        "ai_generation_jobs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="4", nullable=False),
        sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(length=100), nullable=True),
        sa.Column("internal_error_detail", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("attempt >= 0 AND max_attempts >= 1", name="ck_ai_jobs_attempts"),
        sa.CheckConstraint(
            "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_ai_generation_jobs_state",
        ),
        sa.ForeignKeyConstraint(["generation_id"], ["ai_site_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["ai_site_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_id", name="uq_ai_jobs_generation"),
        sa.UniqueConstraint("idempotency_key", name="uq_ai_jobs_idempotency"),
    )
    op.create_index("ix_ai_jobs_owner_state", "ai_generation_jobs", ["owner_user_id", "state"])
    op.create_index(
        "ix_ai_jobs_recovery", "ai_generation_jobs", ["state", "retry_at", "lease_expires_at"]
    )

    op.create_table(
        "ai_generation_artifacts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["generation_id"], ["ai_site_generations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["ai_site_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_id", name="uq_ai_artifacts_generation"),
        sa.UniqueConstraint("object_key", name="uq_ai_artifacts_object_key"),
    )
    op.create_index(
        "ix_ai_artifacts_owner_created", "ai_generation_artifacts", ["owner_user_id", "created_at"]
    )

    op.create_table(
        "ai_generation_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False
        ),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_state", sa.String(length=20), nullable=True),
        sa.Column("to_state", sa.String(length=20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["generation_id"], ["ai_site_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["ai_generation_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_generation_events_timeline", "ai_generation_events", ["generation_id", "created_at"]
    )
    # Preserve existing Phase-boundary projects as immutable generation 1 records.
    op.execute(
        """
        INSERT INTO ai_site_generations (
            id, project_id, owner_user_id, version_number, request_key,
            prompt_ciphertext, prompt_digest, state, retryable, error_category,
            queued_at, started_at, completed_at, failed_at, cancelled_at, created_at, updated_at
        )
        SELECT uuidv7(), p.id, p.owner_user_id, 1, p.idempotency_key,
               p.prompt_ciphertext, p.prompt_digest,
               CASE p.status
                 WHEN 'READY' THEN 'COMPLETED'
                 WHEN 'FAILED' THEN 'FAILED'
                 WHEN 'CANCELLED' THEN 'CANCELLED'
                 WHEN 'QUEUED' THEN 'QUEUED'
                 WHEN 'SUBMITTED' THEN 'QUEUED'
                 ELSE p.status
               END,
               false, p.safe_error_code,
               p.created_at,
               CASE WHEN p.status NOT IN ('QUEUED','CANCELLED') THEN p.updated_at END,
               CASE WHEN p.status = 'READY' THEN p.updated_at END,
               CASE WHEN p.status = 'FAILED' THEN p.updated_at END,
               CASE WHEN p.status = 'CANCELLED' THEN p.updated_at END,
               p.created_at, p.updated_at
        FROM ai_site_projects p
        """
    )
    op.execute(
        """
        INSERT INTO ai_generation_jobs (
            id, project_id, generation_id, owner_user_id, state, idempotency_key,
            attempt, max_attempts, safe_error_code, correlation_id, queued_at,
            started_at, finished_at, created_at, updated_at
        )
        SELECT uuidv7(), g.project_id, g.id, g.owner_user_id,
               CASE g.state
                 WHEN 'COMPLETED' THEN 'SUCCEEDED'
                 WHEN 'FAILED' THEN 'FAILED'
                 WHEN 'CANCELLED' THEN 'CANCELLED'
                 ELSE 'PENDING'
               END,
               'ai-generation:' || g.id::text, 0, 4, g.error_category,
               'ai-builder-migration-backfill', g.queued_at,
               g.started_at, COALESCE(g.completed_at, g.failed_at, g.cancelled_at),
               g.created_at, g.updated_at
        FROM ai_site_generations g
        """
    )
    op.execute(
        """
        UPDATE outbox_events e
           SET aggregate_type = 'AI_GENERATION_JOB',
               aggregate_id = j.id,
               event_type = 'ai_generation.execute_requested',
               payload = jsonb_build_object('job_id', j.id::text)
          FROM ai_generation_jobs j
         WHERE e.aggregate_type = 'AI_SITE_PROJECT'
           AND e.aggregate_id = j.project_id
           AND e.state = 'PENDING'
        """
    )
    op.execute(
        """
        INSERT INTO outbox_events (
            id, aggregate_type, aggregate_id, event_type, event_version, payload,
            state, attempts, available_at, correlation_id, created_at
        )
        SELECT uuidv7(), 'AI_GENERATION_JOB', j.id, 'ai_generation.execute_requested', 1,
               jsonb_build_object('job_id', j.id::text), 'PENDING', 0, now(),
               j.correlation_id, now()
          FROM ai_generation_jobs j
         WHERE j.state = 'PENDING'
           AND NOT EXISTS (
               SELECT 1 FROM outbox_events e
                WHERE e.aggregate_type = 'AI_GENERATION_JOB' AND e.aggregate_id = j.id
           )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE outbox_events e
           SET aggregate_type = 'AI_SITE_PROJECT',
               aggregate_id = j.project_id,
               event_type = 'ai_site.build_requested',
               payload = jsonb_build_object('ai_site_project_id', j.project_id::text)
          FROM ai_generation_jobs j
         WHERE e.aggregate_type = 'AI_GENERATION_JOB'
           AND e.aggregate_id = j.id
           AND EXISTS (
               SELECT 1 FROM ai_site_generations g
                WHERE g.id = j.generation_id AND g.version_number = 1
           )
        """
    )
    op.execute(
        "DELETE FROM outbox_events e USING ai_generation_jobs j, ai_site_generations g "
        "WHERE e.aggregate_type = 'AI_GENERATION_JOB' AND e.aggregate_id = j.id "
        "AND j.generation_id = g.id AND g.version_number > 1"
    )
    op.drop_index("ix_ai_generation_events_timeline", table_name="ai_generation_events")
    op.drop_table("ai_generation_events")
    op.drop_index("ix_ai_artifacts_owner_created", table_name="ai_generation_artifacts")
    op.drop_table("ai_generation_artifacts")
    op.drop_index("ix_ai_jobs_recovery", table_name="ai_generation_jobs")
    op.drop_index("ix_ai_jobs_owner_state", table_name="ai_generation_jobs")
    op.drop_table("ai_generation_jobs")
    op.drop_index("ix_ai_generations_project_created", table_name="ai_site_generations")
    op.drop_index("ix_ai_generations_owner_created", table_name="ai_site_generations")
    op.drop_table("ai_site_generations")
