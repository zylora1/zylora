from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.core.config import Settings
from zylora_api.db.ai_builder_models import (
    AiGenerationArtifact,
    AiGenerationEvent,
    AiGenerationJob,
    AiSiteGeneration,
    AiSiteProject,
)
from zylora_api.db.auth_models import User
from zylora_api.db.models import OutboxEvent
from zylora_api.db.session import get_engine
from zylora_api.modules.ai_builder.artifacts import GenerationArtifactVerifier
from zylora_api.modules.ai_builder.client import BuilderArtifact, BuilderExecutionResult
from zylora_api.modules.ai_builder.service import AiSiteProjectService
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.storage.memory import MemoryObjectStorage

CRYPTO = AuthCrypto("ai-site-integration-secret-long-enough")
SETTINGS = Settings(
    _env_file=None,
    environment="test",
    storage_provider="memory",
    ai_builder_enabled=True,
    ai_builder_url="https://builder.test",
    ai_builder_service_token="test-service-token-long-enough-for-tests",
    max_active_ai_jobs_per_user=4,
    max_ai_generations_per_window=20,
)


async def create_user(session: AsyncSession, marker: str) -> User:
    email = f"ai-builder-{marker}-{uuid4().hex}@example.com"
    user = User(
        account_type="USER",
        normalized_email=email,
        display_email=email,
        status="ACTIVE",
        verified_at=datetime.now(UTC),
        billing_country_code="ZZ",
    )
    session.add(user)
    await session.flush()
    return user


def service(session: AsyncSession) -> AiSiteProjectService:
    return AiSiteProjectService(session, CRYPTO, SETTINGS)


@pytest.mark.integration
async def test_durable_happy_path_is_idempotent_encrypted_and_immutable() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    storage = MemoryObjectStorage()
    async with factory() as session:
        owner = await create_user(session, "happy-owner")
        stranger = await create_user(session, "happy-stranger")
        prompt = "Build a premium architecture studio website with projects and enquiries."
        created = await service(session).queue(
            owner_user_id=owner.id,
            prompt=prompt,
            idempotency_key="ai-site-integration-idempotency",
            correlation_id="ai-site-integration",
        )
        duplicate = await service(session).queue(
            owner_user_id=owner.id,
            prompt=prompt,
            idempotency_key="ai-site-integration-idempotency",
            correlation_id="ai-site-integration-duplicate",
        )
        assert duplicate.project.id == created.project.id
        assert duplicate.generation.id == created.generation.id
        assert prompt.encode() not in created.project.prompt_ciphertext
        assert prompt.encode() not in created.generation.prompt_ciphertext
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == created.job.id)
        )
        assert event is not None
        assert event.payload == {"job_id": str(created.job.id)}
        assert prompt not in str(event.payload)
        with pytest.raises(AuthProblem, match="not found"):
            await service(session).get_for_owner(created.project.id, stranger.id)
        await session.commit()

    # A new session represents API/worker process restart; DB state remains authoritative.
    async with factory() as session:
        claimed = await service(session).claim(created.job.id, "integration-worker")
        assert claimed is not None
        assert await service(session).claim(created.job.id, "duplicate-worker") is None
        await session.commit()

    payload = b"content-addressed immutable generated site"
    digest = sha256(payload).hexdigest()
    key = f"ai-sites/{owner.id}/{created.project.id}/{created.generation.id}/{digest}.tar.gz"
    storage.put_bytes(key, payload, "application/gzip")
    artifact = BuilderArtifact(key, digest, len(payload), "application/gzip")
    GenerationArtifactVerifier(storage, SETTINGS).verify(
        artifact,
        owner_user_id=owner.id,
        project_id=created.project.id,
        generation_id=created.generation.id,
    )
    result = BuilderExecutionResult(
        created.generation.id,
        artifact,
        "deterministic-test-provider",
        "test-model",
        {"validating": 2, "scanning": 1, "sandboxing": 4, "building": 3, "storing": 2},
    )
    async with factory() as session:
        completed = await service(session).complete(created.job.id, claimed.lease_token, result)
        assert completed is not None
        assert completed.generation.state == "COMPLETED"
        assert completed.job.state == "SUCCEEDED"
        assert completed.artifact is not None
        assert completed.artifact.checksum_sha256 == digest
        assert await service(session).complete(created.job.id, claimed.lease_token, result) is None
        with pytest.raises(AuthProblem, match="not found"):
            await service(session).artifact_for_owner(
                created.project.id, created.generation.id, stranger.id
            )
        assert (
            await session.scalar(
                select(func.count(AiGenerationArtifact.id)).where(
                    AiGenerationArtifact.generation_id == created.generation.id
                )
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(AiGenerationEvent.id)).where(
                    AiGenerationEvent.generation_id == created.generation.id
                )
            )
            >= 8
        )
        await session.commit()


@pytest.mark.integration
async def test_stale_lease_recovery_and_bounded_retry_are_deterministic() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "recovery")
        snapshot = await service(session).queue(
            owner_user_id=owner.id,
            prompt="Build a clear production website for a coaching academy and its courses.",
            idempotency_key="ai-site-recovery-idempotency",
            correlation_id="ai-site-recovery",
        )
        claim = await service(session).claim(snapshot.job.id, "worker-before-crash")
        assert claim is not None
        snapshot.job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    async with factory() as session:
        recovered = await service(session).recover_stale()
        assert snapshot.job.id in recovered
        await session.commit()

    async with factory() as session:
        next_claim = await service(session).claim(snapshot.job.id, "worker-after-restart")
        assert next_claim is not None and next_claim.attempt == 2
        failed = await service(session).fail(
            snapshot.job.id,
            next_claim.lease_token,
            error_code="PROVIDER_RATE_LIMITED",
            retryable=True,
        )
        assert failed is not None and failed.job.state == "RETRY_WAIT"
        failed.job.retry_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    async with factory() as session:
        assert snapshot.job.id in await service(session).recover_stale()
        claim3 = await service(session).claim(snapshot.job.id, "worker-attempt-3")
        assert claim3 is not None and claim3.attempt == 3
        terminal = await service(session).fail(
            snapshot.job.id,
            claim3.lease_token,
            error_code="GENERATION_POLICY_REJECTED",
            retryable=False,
        )
        assert terminal is not None
        assert terminal.job.state == "FAILED"
        assert terminal.generation.state == "FAILED"
        assert terminal.generation.retryable is False
        await session.commit()


@pytest.mark.integration
async def test_retry_creates_new_version_and_cancel_is_owner_authorized() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "retry-owner")
        stranger = await create_user(session, "retry-stranger")
        first = await service(session).queue(
            owner_user_id=owner.id,
            prompt="Build a production website for a regional consulting business.",
            idempotency_key="ai-site-version-one-key",
            correlation_id="ai-site-version-one",
        )
        claim = await service(session).claim(first.job.id, "version-one-worker")
        assert claim is not None
        failed = await service(session).fail(
            first.job.id,
            claim.lease_token,
            error_code="PROVIDER_UNAVAILABLE",
            retryable=True,
        )
        assert failed is not None
        failed.job.attempt = failed.job.max_attempts
        failed.job.state = "RUNNING"
        failed.job.lease_token = uuid4()
        failed.generation.state = "GENERATING"
        terminal_token = failed.job.lease_token
        await service(session).fail(
            first.job.id,
            terminal_token,
            error_code="PROVIDER_UNAVAILABLE",
            retryable=True,
        )
        with pytest.raises(AuthProblem, match="not found"):
            await service(session).retry(
                first.project.id,
                stranger.id,
                request_key="ai-site-forged-retry-key",
                correlation_id="forged-retry",
            )
        second = await service(session).retry(
            first.project.id,
            owner.id,
            request_key="ai-site-version-two-key",
            correlation_id="ai-site-version-two",
        )
        assert second.generation.version_number == 2
        assert second.generation.previous_generation_id == first.generation.id
        cancelled = await service(session).cancel(
            first.project.id, owner.id, correlation_id="owner-cancel"
        )
        assert cancelled.generation.state == "CANCELLED"
        assert cancelled.job.state == "CANCELLED"
        await session.commit()


@pytest.mark.integration
async def test_concurrent_duplicate_submission_produces_one_project_generation_and_job() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "concurrent")
        owner_id = owner.id
        await session.commit()

    async def submit(marker: str) -> tuple[object, object, object]:
        async with factory() as session:
            snapshot = await service(session).queue(
                owner_user_id=owner_id,
                prompt="Build a durable website for a neighbourhood healthcare practice.",
                idempotency_key="ai-site-concurrent-idempotency",
                correlation_id=marker,
            )
            await session.commit()
            return snapshot.project.id, snapshot.generation.id, snapshot.job.id

    first, second = await asyncio.gather(submit("concurrent-a"), submit("concurrent-b"))
    assert first == second
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count(AiSiteProject.id)).where(AiSiteProject.owner_user_id == owner_id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(AiSiteGeneration.id)).where(
                    AiSiteGeneration.owner_user_id == owner_id
                )
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(AiGenerationJob.id)).where(
                    AiGenerationJob.owner_user_id == owner_id
                )
            )
            == 1
        )


@pytest.mark.integration
async def test_generation_validation_quota_and_owner_guards_fail_closed() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "guards")
        guarded = AiSiteProjectService(
            session,
            CRYPTO,
            SETTINGS.model_copy(
                update={
                    "max_active_ai_jobs_per_user": 1,
                    "max_ai_generations_per_window": 10,
                }
            ),
        )
        with pytest.raises(AuthProblem, match="supported prompt limit"):
            await guarded.queue(
                owner_user_id=owner.id,
                prompt="too short",
                idempotency_key="ai-site-validation-key",
                correlation_id="invalid-prompt",
            )
        with pytest.raises(AuthProblem, match="request key is invalid"):
            await guarded.queue(
                owner_user_id=owner.id,
                prompt="Build a valid professional website for a local business.",
                idempotency_key="short",
                correlation_id="invalid-key",
            )
        with pytest.raises(AuthProblem, match="User account is unavailable"):
            await guarded.queue(
                owner_user_id=uuid4(),
                prompt="Build a valid professional website for a local business.",
                idempotency_key="ai-site-missing-owner-key",
                correlation_id="missing-owner",
            )
        first = await guarded.queue(
            owner_user_id=owner.id,
            prompt="Build a valid professional website for a local business.",
            idempotency_key="ai-site-guard-first-key",
            correlation_id="guard-first",
        )
        with pytest.raises(AuthProblem, match="active AI website generation"):
            await guarded.queue(
                owner_user_id=owner.id,
                prompt="Build another valid website for the same local business.",
                idempotency_key="ai-site-guard-second-key",
                correlation_id="guard-second",
            )
        with pytest.raises(AuthProblem, match="cannot be retried"):
            await guarded.retry(
                first.project.id,
                owner.id,
                request_key="ai-site-guard-retry-key",
                correlation_id="guard-retry",
            )
        with pytest.raises(AuthProblem, match="Preview artifact not found"):
            await guarded.artifact_for_owner(first.project.id, first.generation.id, owner.id)
        await session.commit()

    async with factory() as session:
        rate_owner = await create_user(session, "rate")
        limited = AiSiteProjectService(
            session,
            CRYPTO,
            SETTINGS.model_copy(
                update={
                    "max_active_ai_jobs_per_user": 10,
                    "max_ai_generations_per_window": 1,
                }
            ),
        )
        first = await limited.queue(
            owner_user_id=rate_owner.id,
            prompt="Build a valid professional website for the rate-limit test.",
            idempotency_key="ai-site-rate-first-key",
            correlation_id="rate-first",
        )
        first.job.state = "FAILED"
        first.generation.state = "FAILED"
        with pytest.raises(AuthProblem, match="generation limit has been reached"):
            await limited.queue(
                owner_user_id=rate_owner.id,
                prompt="Build another valid professional website for the rate-limit test.",
                idempotency_key="ai-site-rate-second-key",
                correlation_id="rate-second",
            )
        await session.rollback()


@pytest.mark.integration
async def test_generation_state_guards_reject_stale_late_and_conflicting_results() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "state-guards")
        current = await service(session).queue(
            owner_user_id=owner.id,
            prompt="Build a production website for state transition testing.",
            idempotency_key="ai-site-state-guards-key",
            correlation_id="state-guards",
        )
        claim = await service(session).claim(current.job.id, "state-worker")
        assert claim is not None
        assert (
            await service(session).fail(
                current.job.id,
                uuid4(),
                error_code="PROVIDER_TIMEOUT",
                retryable=True,
            )
            is None
        )
        failed = await service(session).fail(
            current.job.id,
            claim.lease_token,
            error_code="PROVIDER_TIMEOUT",
            retryable=True,
        )
        assert failed is not None
        assert await service(session).claim(current.job.id, "early-retry-worker") is None
        failed.job.retry_at = datetime.now(UTC) - timedelta(seconds=1)
        recovered = await service(session).recover_stale()
        assert current.job.id in recovered
        next_claim = await service(session).claim(current.job.id, "result-worker")
        assert next_claim is not None
        bad_result = BuilderExecutionResult(
            uuid4(),
            BuilderArtifact("safe.tar.gz", "a" * 64, 1, "application/gzip"),
            None,
            None,
            {},
        )
        with pytest.raises(ValueError, match="generation mismatch"):
            await service(session).complete(current.job.id, next_claim.lease_token, bad_result)
        cancelled = await service(session).cancel(
            current.project.id, owner.id, correlation_id="cancel-running"
        )
        again = await service(session).cancel(
            current.project.id, owner.id, correlation_id="cancel-idempotent"
        )
        assert cancelled.generation.state == again.generation.state == "CANCELLED"
        assert await service(session).claim(current.job.id, "late-worker") is None
        await session.commit()


@pytest.mark.integration
async def test_exhausted_pending_job_is_terminal_during_recovery() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner = await create_user(session, "exhausted")
        current = await service(session).queue(
            owner_user_id=owner.id,
            prompt="Build a production website for exhausted retry recovery.",
            idempotency_key="ai-site-exhausted-recovery-key",
            correlation_id="exhausted-recovery",
        )
        current.job.attempt = current.job.max_attempts
        ready = await service(session).recover_stale()
        assert current.job.id not in ready
        assert current.job.state == "FAILED"
        assert current.generation.state == "FAILED"
        assert current.generation.error_category == "AI_GENERATION_RETRIES_EXHAUSTED"
        assert await service(session).claim(current.job.id, "exhausted-worker") is None
        await session.commit()
