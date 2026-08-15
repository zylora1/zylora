from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings, get_settings
from zylora_api.db.ai_builder_models import (
    AiGenerationArtifact,
    AiGenerationEvent,
    AiGenerationJob,
    AiSiteGeneration,
    AiSiteProject,
)
from zylora_api.db.auth_models import User
from zylora_api.db.models import OutboxEvent
from zylora_api.modules.ai_builder.client import BuilderExecutionResult
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.service import problem

ACTIVE_JOB_STATES = {"PENDING", "RUNNING", "RETRY_WAIT"}
TERMINAL_GENERATION_STATES = {"COMPLETED", "FAILED", "CANCELLED"}
TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"QUEUED", "CANCELLED"},
    "QUEUED": {"CLAIMED", "CANCELLED", "FAILED"},
    "CLAIMED": {"GENERATING", "QUEUED", "CANCELLED", "FAILED"},
    "GENERATING": {"VALIDATING", "QUEUED", "CANCELLED", "FAILED"},
    "VALIDATING": {"SCANNING", "QUEUED", "CANCELLED", "FAILED"},
    "SCANNING": {"SANDBOXING", "QUEUED", "CANCELLED", "FAILED"},
    "SANDBOXING": {"BUILDING", "QUEUED", "CANCELLED", "FAILED"},
    "BUILDING": {"STORING", "QUEUED", "CANCELLED", "FAILED"},
    "STORING": {"COMPLETED", "QUEUED", "CANCELLED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    job_id: UUID
    generation_id: UUID
    project_id: UUID
    owner_user_id: UUID
    lease_token: UUID
    prompt: str
    attempt: int
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    project: AiSiteProject
    generation: AiSiteGeneration
    job: AiGenerationJob
    artifact: AiGenerationArtifact | None


class AiSiteProjectService:
    """Canonical writer for AI projects, immutable versions, jobs, and artifacts."""

    def __init__(
        self, session: AsyncSession, crypto: AuthCrypto, settings: Settings | None = None
    ) -> None:
        self.session = session
        self.crypto = crypto
        self.settings = settings or get_settings()

    async def queue(
        self,
        *,
        owner_user_id: UUID,
        prompt: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProjectSnapshot:
        normalized = self._validate_prompt(prompt)
        self._validate_request_key(idempotency_key)
        await self._lock_owner(owner_user_id)
        existing = await self.session.scalar(
            select(AiSiteProject).where(
                AiSiteProject.owner_user_id == owner_user_id,
                AiSiteProject.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return await self.snapshot(existing)
        await self._enforce_quota(owner_user_id)
        project = AiSiteProject(
            owner_user_id=owner_user_id,
            prompt_ciphertext=self.crypto.encrypt(
                normalized, purpose=f"ai-site-project:{owner_user_id}:{idempotency_key}"
            ),
            prompt_digest=self.crypto.digest(normalized, purpose="ai-site-project-prompt"),
            status="QUEUED",
            idempotency_key=idempotency_key,
        )
        self.session.add(project)
        await self.session.flush()
        generation, job = await self._new_generation(
            project=project,
            prompt=normalized,
            request_key=idempotency_key,
            version_number=1,
            previous=None,
            correlation_id=correlation_id,
        )
        return ProjectSnapshot(project, generation, job, None)

    async def retry(
        self,
        project_id: UUID,
        owner_user_id: UUID,
        *,
        request_key: str,
        correlation_id: str,
    ) -> ProjectSnapshot:
        self._validate_request_key(request_key)
        await self._lock_owner(owner_user_id)
        project = await self._project_for_owner(project_id, owner_user_id, lock=True)
        duplicate = await self.session.scalar(
            select(AiSiteGeneration).where(
                AiSiteGeneration.project_id == project.id,
                AiSiteGeneration.request_key == request_key,
            )
        )
        if duplicate:
            return await self.snapshot(project, duplicate)
        previous = await self._latest_generation(project.id, lock=True)
        if previous.state != "FAILED" or not previous.retryable:
            raise problem(409, "ai_generation_not_retryable", "This generation cannot be retried.")
        await self._enforce_quota(owner_user_id)
        old_purpose = f"ai-generation:{owner_user_id}:{previous.id}"
        prompt = self.crypto.decrypt(previous.prompt_ciphertext, purpose=old_purpose)
        generation, job = await self._new_generation(
            project=project,
            prompt=prompt,
            request_key=request_key,
            version_number=previous.version_number + 1,
            previous=previous,
            correlation_id=correlation_id,
        )
        project.status = "QUEUED"
        project.safe_error_code = None
        project.builder_build_id = None
        project.artifact_digest = None
        return ProjectSnapshot(project, generation, job, None)

    async def cancel(
        self, project_id: UUID, owner_user_id: UUID, *, correlation_id: str
    ) -> ProjectSnapshot:
        project = await self._project_for_owner(project_id, owner_user_id, lock=True)
        generation = await self._latest_generation(project.id, lock=True)
        job = await self._job_for_generation(generation.id, lock=True)
        artifact = await self._artifact_for_generation(generation.id)
        if generation.state == "COMPLETED":
            raise problem(
                409, "ai_generation_already_completed", "Completed generations cannot be cancelled."
            )
        if generation.state == "CANCELLED":
            return ProjectSnapshot(project, generation, job, artifact)
        if generation.state == "FAILED":
            raise problem(
                409, "ai_generation_already_failed", "Failed generations are already stopped."
            )
        now = datetime.now(UTC)
        self._transition(generation, job, "CANCELLED", correlation_id=correlation_id)
        generation.cancelled_at = now
        generation.retryable = False
        generation.error_category = "JOB_CANCELLED"
        job.state = "CANCELLED"
        job.safe_error_code = "JOB_CANCELLED"
        job.finished_at = now
        self._clear_lease(job)
        project.status = "CANCELLED"
        project.safe_error_code = "JOB_CANCELLED"
        return ProjectSnapshot(project, generation, job, artifact)

    async def list_for_owner(self, owner_user_id: UUID) -> list[ProjectSnapshot]:
        projects = list(
            (
                await self.session.scalars(
                    select(AiSiteProject)
                    .where(AiSiteProject.owner_user_id == owner_user_id)
                    .order_by(AiSiteProject.updated_at.desc())
                    .limit(100)
                )
            ).all()
        )
        return [await self.snapshot(project) for project in projects]

    async def get_for_owner(self, project_id: UUID, owner_user_id: UUID) -> ProjectSnapshot:
        project = await self._project_for_owner(project_id, owner_user_id)
        return await self.snapshot(project)

    async def snapshot(
        self, project: AiSiteProject, generation: AiSiteGeneration | None = None
    ) -> ProjectSnapshot:
        current = generation or await self._latest_generation(project.id)
        job = await self._job_for_generation(current.id)
        artifact = await self._artifact_for_generation(current.id)
        return ProjectSnapshot(project, current, job, artifact)

    async def artifact_for_owner(
        self, project_id: UUID, generation_id: UUID, owner_user_id: UUID
    ) -> AiGenerationArtifact:
        await self._project_for_owner(project_id, owner_user_id)
        generation = await self.session.scalar(
            select(AiSiteGeneration).where(
                AiSiteGeneration.id == generation_id,
                AiSiteGeneration.project_id == project_id,
                AiSiteGeneration.owner_user_id == owner_user_id,
            )
        )
        if not generation or generation.state != "COMPLETED":
            raise problem(404, "ai_generation_artifact_not_found", "Preview artifact not found.")
        artifact = await self._artifact_for_generation(generation.id)
        if not artifact or artifact.owner_user_id != owner_user_id:
            raise problem(404, "ai_generation_artifact_not_found", "Preview artifact not found.")
        return artifact

    async def claim(self, job_id: UUID, worker_id: str) -> ExecutionClaim | None:
        now = datetime.now(UTC)
        job = await self.session.scalar(
            select(AiGenerationJob).where(AiGenerationJob.id == job_id).with_for_update()
        )
        if not job or job.state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return None
        if job.state == "RUNNING" and job.lease_expires_at and job.lease_expires_at > now:
            return None
        if job.state == "RETRY_WAIT" and job.retry_at and job.retry_at > now:
            return None
        generation = await self.session.scalar(
            select(AiSiteGeneration)
            .where(AiSiteGeneration.id == job.generation_id)
            .with_for_update()
        )
        project = await self.session.scalar(
            select(AiSiteProject).where(AiSiteProject.id == job.project_id).with_for_update()
        )
        if not generation or not project:
            self._terminal_job_failure(job, "INTERNAL_GENERATION_ERROR", now)
            return None
        if generation.state == "CANCELLED":
            job.state = "CANCELLED"
            job.finished_at = now
            self._clear_lease(job)
            return None
        if job.attempt >= job.max_attempts:
            self._terminal_failure(
                project, generation, job, "AI_GENERATION_RETRIES_EXHAUSTED", retryable=True
            )
            return None
        if generation.state != "QUEUED":
            self._transition(generation, job, "QUEUED", correlation_id=job.correlation_id)
        self._transition(generation, job, "CLAIMED", correlation_id=job.correlation_id)
        job.state = "RUNNING"
        job.attempt += 1
        token = uuid4()
        job.lease_token = token
        job.lease_owner = worker_id[:160]
        job.lease_expires_at = now + timedelta(seconds=self.settings.ai_job_lease_seconds)
        job.heartbeat_at = now
        job.retry_at = None
        job.started_at = job.started_at or now
        generation.started_at = generation.started_at or now
        self._transition(generation, job, "GENERATING", correlation_id=job.correlation_id)
        project.status = "GENERATING"
        project.builder_build_id = f"aig_{generation.id}"
        purpose = f"ai-generation:{job.owner_user_id}:{generation.id}"
        prompt = self.crypto.decrypt(generation.prompt_ciphertext, purpose=purpose)
        return ExecutionClaim(
            job.id,
            generation.id,
            project.id,
            job.owner_user_id,
            token,
            prompt,
            job.attempt,
            job.correlation_id,
        )

    async def complete(
        self, job_id: UUID, lease_token: UUID, result: BuilderExecutionResult
    ) -> ProjectSnapshot | None:
        now = datetime.now(UTC)
        locked = await self._locked_execution(job_id, lease_token)
        if not locked:
            return None
        project, generation, job = locked
        if generation.state == "CANCELLED" or job.state == "CANCELLED":
            return ProjectSnapshot(
                project, generation, job, await self._artifact_for_generation(generation.id)
            )
        if result.generation_id != generation.id:
            raise ValueError("builder result generation mismatch")
        for state in ("VALIDATING", "SCANNING", "SANDBOXING", "BUILDING", "STORING"):
            self._transition(
                generation,
                job,
                state,
                correlation_id=job.correlation_id,
                duration_ms=result.stage_durations_ms.get(state.lower()),
            )
        existing = await self._artifact_for_generation(generation.id)
        artifact = existing or AiGenerationArtifact(
            project_id=project.id,
            generation_id=generation.id,
            owner_user_id=job.owner_user_id,
            object_key=result.artifact.object_key,
            checksum_sha256=result.artifact.checksum_sha256,
            size_bytes=result.artifact.size_bytes,
            content_type=result.artifact.content_type,
        )
        if existing and (
            existing.object_key != result.artifact.object_key
            or existing.checksum_sha256 != result.artifact.checksum_sha256
        ):
            raise ValueError("immutable artifact conflict")
        if not existing:
            self.session.add(artifact)
        self._transition(generation, job, "COMPLETED", correlation_id=job.correlation_id)
        generation.completed_at = now
        generation.retryable = False
        generation.error_category = None
        generation.provider_name = result.provider_name
        generation.provider_model = result.provider_model
        job.state = "SUCCEEDED"
        job.finished_at = now
        job.safe_error_code = None
        job.internal_error_detail = None
        self._clear_lease(job)
        project.status = "READY"
        project.safe_error_code = None
        project.artifact_digest = result.artifact.checksum_sha256
        return ProjectSnapshot(project, generation, job, artifact)

    async def fail(
        self,
        job_id: UUID,
        lease_token: UUID,
        *,
        error_code: str,
        retryable: bool,
    ) -> ProjectSnapshot | None:
        locked = await self._locked_execution(job_id, lease_token)
        if not locked:
            return None
        project, generation, job = locked
        safe_code = error_code[:100]
        now = datetime.now(UTC)
        if retryable and job.attempt < job.max_attempts:
            job.state = "RETRY_WAIT"
            job.safe_error_code = safe_code
            job.internal_error_detail = safe_code
            job.retry_at = now + self._retry_delay(job)
            self._clear_lease(job)
            self._transition(generation, job, "QUEUED", correlation_id=job.correlation_id)
            generation.retryable = True
            generation.error_category = safe_code
            project.status = "QUEUED"
            project.safe_error_code = safe_code
        else:
            self._terminal_failure(project, generation, job, safe_code, retryable=retryable)
        return ProjectSnapshot(
            project, generation, job, await self._artifact_for_generation(generation.id)
        )

    async def recover_stale(self, limit: int = 100) -> list[UUID]:
        now = datetime.now(UTC)
        jobs = list(
            (
                await self.session.scalars(
                    select(AiGenerationJob)
                    .where(
                        or_(
                            (AiGenerationJob.state == "RUNNING")
                            & (AiGenerationJob.lease_expires_at < now),
                            (AiGenerationJob.state == "RETRY_WAIT")
                            & (AiGenerationJob.retry_at <= now),
                            AiGenerationJob.state == "PENDING",
                        )
                    )
                    .order_by(AiGenerationJob.queued_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        ready: list[UUID] = []
        for job in jobs:
            generation = await self.session.scalar(
                select(AiSiteGeneration)
                .where(AiSiteGeneration.id == job.generation_id)
                .with_for_update()
            )
            project = await self.session.scalar(
                select(AiSiteProject).where(AiSiteProject.id == job.project_id).with_for_update()
            )
            if not generation or not project or generation.state in TERMINAL_GENERATION_STATES:
                continue
            if job.attempt >= job.max_attempts:
                self._terminal_failure(
                    project, generation, job, "AI_GENERATION_RETRIES_EXHAUSTED", retryable=True
                )
                continue
            if generation.state != "QUEUED":
                self._transition(generation, job, "QUEUED", correlation_id=job.correlation_id)
            job.state = "PENDING"
            job.retry_at = None
            self._clear_lease(job)
            project.status = "QUEUED"
            ready.append(job.id)
        return ready

    async def _new_generation(
        self,
        *,
        project: AiSiteProject,
        prompt: str,
        request_key: str,
        version_number: int,
        previous: AiSiteGeneration | None,
        correlation_id: str,
    ) -> tuple[AiSiteGeneration, AiGenerationJob]:
        now = datetime.now(UTC)
        generation_id = uuid4()
        generation = AiSiteGeneration(
            id=generation_id,
            project_id=project.id,
            owner_user_id=project.owner_user_id,
            previous_generation_id=previous.id if previous else None,
            version_number=version_number,
            request_key=request_key,
            prompt_ciphertext=self.crypto.encrypt(
                prompt, purpose=f"ai-generation:{project.owner_user_id}:{generation_id}"
            ),
            prompt_digest=self.crypto.digest(prompt, purpose="ai-site-project-prompt"),
            state="CREATED",
            queued_at=now,
        )
        job = AiGenerationJob(
            id=uuid4(),
            project_id=project.id,
            generation_id=generation_id,
            owner_user_id=project.owner_user_id,
            state="PENDING",
            idempotency_key=f"ai-generation:{generation_id}",
            max_attempts=self.settings.ai_max_retries,
            correlation_id=correlation_id,
            queued_at=now,
        )
        # Flush the immutable generation before its leased execution row. These
        # models intentionally do not expose mutable ORM relationships, so an
        # explicit order keeps PostgreSQL foreign-key enforcement deterministic.
        self.session.add(generation)
        await self.session.flush()
        self.session.add(job)
        await self.session.flush()
        self._transition(generation, job, "QUEUED", correlation_id=correlation_id)
        self.session.add(
            OutboxEvent(
                aggregate_type="AI_GENERATION_JOB",
                aggregate_id=job.id,
                event_type="ai_generation.execute_requested",
                payload={"job_id": str(job.id)},
                correlation_id=correlation_id,
            )
        )
        return generation, job

    async def _locked_execution(
        self, job_id: UUID, lease_token: UUID
    ) -> tuple[AiSiteProject, AiSiteGeneration, AiGenerationJob] | None:
        job = await self.session.scalar(
            select(AiGenerationJob).where(AiGenerationJob.id == job_id).with_for_update()
        )
        if not job or job.state != "RUNNING" or job.lease_token != lease_token:
            return None
        generation = await self.session.scalar(
            select(AiSiteGeneration)
            .where(AiSiteGeneration.id == job.generation_id)
            .with_for_update()
        )
        project = await self.session.scalar(
            select(AiSiteProject).where(AiSiteProject.id == job.project_id).with_for_update()
        )
        if not project or not generation:
            return None
        return project, generation, job

    async def _project_for_owner(
        self, project_id: UUID, owner_user_id: UUID, *, lock: bool = False
    ) -> AiSiteProject:
        statement = select(AiSiteProject).where(
            AiSiteProject.id == project_id, AiSiteProject.owner_user_id == owner_user_id
        )
        if lock:
            statement = statement.with_for_update()
        project = await self.session.scalar(statement)
        if not project:
            raise problem(404, "ai_site_project_not_found", "AI website project not found.")
        return project

    async def _latest_generation(self, project_id: UUID, *, lock: bool = False) -> AiSiteGeneration:
        statement = (
            select(AiSiteGeneration)
            .where(AiSiteGeneration.project_id == project_id)
            .order_by(AiSiteGeneration.version_number.desc())
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        generation = await self.session.scalar(statement)
        if not generation:
            raise problem(409, "ai_generation_missing", "AI generation state is unavailable.")
        return generation

    async def _job_for_generation(
        self, generation_id: UUID, *, lock: bool = False
    ) -> AiGenerationJob:
        statement = select(AiGenerationJob).where(AiGenerationJob.generation_id == generation_id)
        if lock:
            statement = statement.with_for_update()
        job = await self.session.scalar(statement)
        if not job:
            raise problem(409, "ai_generation_job_missing", "AI generation job is unavailable.")
        return job

    async def _artifact_for_generation(self, generation_id: UUID) -> AiGenerationArtifact | None:
        return cast(
            AiGenerationArtifact | None,
            await self.session.scalar(
                select(AiGenerationArtifact).where(
                    AiGenerationArtifact.generation_id == generation_id
                )
            ),
        )

    async def _lock_owner(self, owner_user_id: UUID) -> None:
        owner = await self.session.scalar(
            select(User).where(User.id == owner_user_id).with_for_update()
        )
        if not owner:
            raise problem(404, "user_not_found", "The User account is unavailable.")

    async def _enforce_quota(self, owner_user_id: UUID) -> None:
        active = int(
            await self.session.scalar(
                select(func.count(AiGenerationJob.id)).where(
                    AiGenerationJob.owner_user_id == owner_user_id,
                    AiGenerationJob.state.in_(ACTIVE_JOB_STATES),
                )
            )
            or 0
        )
        if active >= self.settings.max_active_ai_jobs_per_user:
            raise problem(
                429,
                "ai_generation_concurrency_limit",
                "Wait for an active AI website generation to finish before starting another.",
            )
        cutoff = datetime.now(UTC) - timedelta(seconds=self.settings.ai_generation_window_seconds)
        recent = int(
            await self.session.scalar(
                select(func.count(AiSiteGeneration.id)).where(
                    AiSiteGeneration.owner_user_id == owner_user_id,
                    AiSiteGeneration.created_at >= cutoff,
                )
            )
            or 0
        )
        if recent >= self.settings.max_ai_generations_per_window:
            raise problem(
                429,
                "ai_generation_rate_limit",
                "The AI website generation limit has been reached. Try again later.",
            )

    def _transition(
        self,
        generation: AiSiteGeneration,
        job: AiGenerationJob,
        target: str,
        *,
        correlation_id: str,
        duration_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        source = generation.state
        if target == source:
            return
        if target not in TRANSITIONS.get(source, set()):
            raise ValueError(f"invalid AI generation transition {source}->{target}")
        generation.state = target
        self.session.add(
            AiGenerationEvent(
                generation_id=generation.id,
                job_id=job.id,
                from_state=source,
                to_state=target,
                attempt=job.attempt,
                duration_ms=duration_ms,
                details=details or {},
                correlation_id=correlation_id,
            )
        )

    def _terminal_failure(
        self,
        project: AiSiteProject,
        generation: AiSiteGeneration,
        job: AiGenerationJob,
        error_code: str,
        *,
        retryable: bool,
    ) -> None:
        now = datetime.now(UTC)
        self._transition(generation, job, "FAILED", correlation_id=job.correlation_id)
        generation.failed_at = now
        generation.retryable = retryable
        generation.error_category = error_code[:100]
        job.state = "FAILED"
        job.safe_error_code = error_code[:100]
        job.internal_error_detail = error_code[:100]
        job.finished_at = now
        self._clear_lease(job)
        project.status = "FAILED"
        project.safe_error_code = error_code[:100]

    @staticmethod
    def _terminal_job_failure(job: AiGenerationJob, code: str, now: datetime) -> None:
        job.state = "FAILED"
        job.safe_error_code = code
        job.internal_error_detail = code
        job.finished_at = now
        AiSiteProjectService._clear_lease(job)

    @staticmethod
    def _clear_lease(job: AiGenerationJob) -> None:
        job.lease_token = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None

    @staticmethod
    def _retry_delay(job: AiGenerationJob) -> timedelta:
        base = min(300, 15 * (2 ** max(0, job.attempt - 1)))
        jitter = job.id.int % max(1, base // 4 + 1)
        return timedelta(seconds=base + jitter)

    def _validate_prompt(self, prompt: str) -> str:
        normalized = prompt.strip()
        try:
            size = len(normalized.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as error:
            raise problem(
                422, "ai_site_prompt_invalid", "The website description is invalid."
            ) from error
        if not 20 <= len(normalized) <= 2000 or size > self.settings.max_ai_prompt_bytes:
            raise problem(
                422,
                "ai_site_prompt_invalid",
                "Describe the website within the supported prompt limit.",
            )
        return normalized

    @staticmethod
    def _validate_request_key(value: str) -> None:
        if not 16 <= len(value) <= 160:
            raise problem(
                422, "ai_site_idempotency_key_invalid", "AI project request key is invalid."
            )
