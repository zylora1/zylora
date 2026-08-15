from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_session
from zylora_api.modules.ai_builder.schemas import (
    AiArtifactAccessResponse,
    AiSiteProjectCreate,
    AiSiteProjectListResponse,
    AiSiteProjectResponse,
)
from zylora_api.modules.ai_builder.service import AiSiteProjectService, ProjectSnapshot
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.http import (
    RequestIdentity,
    correlation_id,
    get_crypto,
    get_user_identity,
    request_ip,
    require_csrf,
    require_json_origin,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.publishing.runtime import publication_storage_for
from zylora_api.modules.templates.service import problem

router = APIRouter(prefix="/api/v1", tags=["ai-website-builder"])

SAFE_ERROR_MESSAGES = {
    "PROVIDER_UNAVAILABLE": "The generation provider is temporarily unavailable.",
    "PROVIDER_RATE_LIMITED": "Generation capacity is temporarily busy. Zylora will retry safely.",
    "PROVIDER_TIMEOUT": "The generation provider took too long to respond.",
    "INVALID_PROVIDER_RESPONSE": "The generated project could not be validated.",
    "GENERATION_POLICY_REJECTED": "This request could not be generated under the website policy.",
    "GENERATED_PROJECT_INVALID": "The generated project did not meet the required structure.",
    "GENERATED_PROJECT_UNSAFE": "The generated project did not pass security validation.",
    "SANDBOX_BUILD_FAILED": "The generated website did not pass its production build.",
    "SANDBOX_TIMEOUT": "The isolated website build timed out.",
    "ARTIFACT_STORAGE_FAILED": "The completed build could not be stored safely.",
    "JOB_CANCELLED": "Generation was cancelled.",
    "AI_GENERATION_RETRIES_EXHAUSTED": "Generation could not complete after safe retries.",
    "AI_BUILDER_DISABLED": "AI website generation is not available right now.",
    "AI_BUILDER_UNAVAILABLE": "AI website generation is temporarily unavailable.",
    "AI_BUILDER_TIMEOUT": "The isolated generation service timed out.",
    "INTERNAL_GENERATION_ERROR": "The generation could not be completed safely.",
}


def response(snapshot: ProjectSnapshot) -> AiSiteProjectResponse:
    generation = snapshot.generation
    job = snapshot.job
    error = generation.error_category or job.safe_error_code
    return AiSiteProjectResponse(
        id=snapshot.project.id,
        status=generation.state,
        generation_id=generation.id,
        generation_version=generation.version_number,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        retryable=generation.retryable,
        can_cancel=generation.state not in {"COMPLETED", "FAILED", "CANCELLED"},
        can_retry=generation.state == "FAILED" and generation.retryable,
        preview_ready=generation.state == "COMPLETED" and snapshot.artifact is not None,
        artifact_digest=snapshot.artifact.checksum_sha256 if snapshot.artifact else None,
        safe_error_code=error,
        safe_error_message=SAFE_ERROR_MESSAGES.get(error) if error else None,
        queued_at=generation.queued_at,
        started_at=generation.started_at,
        completed_at=generation.completed_at,
        failed_at=generation.failed_at,
        cancelled_at=generation.cancelled_at,
        created_at=snapshot.project.created_at,
        updated_at=generation.updated_at,
    )


def service(session: AsyncSession, crypto: AuthCrypto, settings: Settings) -> AiSiteProjectService:
    return AiSiteProjectService(session, crypto, settings)


def require_generation_access(settings: Settings, owner_user_id: UUID) -> None:
    if not settings.ai_builder_enabled:
        raise problem(
            503, "ai_builder_unavailable", "AI website generation is not available right now."
        )
    if (
        settings.ai_builder_rollout_mode == "canary"
        and owner_user_id not in settings.ai_builder_canary_users
    ):
        raise problem(
            503, "ai_builder_unavailable", "AI website generation is not available right now."
        )


@router.get("/ai-site-projects", response_model=AiSiteProjectListResponse)
async def list_ai_site_projects(
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AiSiteProjectListResponse:
    items = [
        response(item)
        for item in await service(session, crypto, settings).list_for_owner(identity.user.id)
    ]
    return AiSiteProjectListResponse(items=items)


@router.get("/ai-site-projects/{project_id}", response_model=AiSiteProjectResponse)
async def get_ai_site_project(
    project_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AiSiteProjectResponse:
    return response(
        await service(session, crypto, settings).get_for_owner(project_id, identity.user.id)
    )


@router.post(
    "/ai-site-projects",
    response_model=AiSiteProjectResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_ai_site_project(
    payload: AiSiteProjectCreate,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=160)],
) -> AiSiteProjectResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    require_generation_access(settings, identity.user.id)
    snapshot = await service(session, crypto, settings).queue(
        owner_user_id=identity.user.id,
        prompt=payload.prompt,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id(request),
    )
    AuditService(session, crypto).record(
        "ai_site_project.queued",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="ai_site_project",
        target_id=str(snapshot.project.id),
        reason="AI_SITE_DESCRIPTION_SUBMITTED",
        ip_address=request_ip(request, settings),
        metadata={
            "generation_id": str(snapshot.generation.id),
            "prompt_digest": snapshot.generation.prompt_digest.hex(),
        },
    )
    await session.commit()
    return response(snapshot)


@router.post(
    "/ai-site-projects/{project_id}/retry",
    response_model=AiSiteProjectResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_ai_site_project(
    project_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=160)],
) -> AiSiteProjectResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    require_generation_access(settings, identity.user.id)
    snapshot = await service(session, crypto, settings).retry(
        project_id,
        identity.user.id,
        request_key=idempotency_key,
        correlation_id=correlation_id(request),
    )
    AuditService(session, crypto).record(
        "ai_site_generation.retried",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="ai_site_generation",
        target_id=str(snapshot.generation.id),
        reason="USER_RETRY",
        ip_address=request_ip(request, settings),
        metadata={"version": snapshot.generation.version_number},
    )
    await session.commit()
    return response(snapshot)


@router.post("/ai-site-projects/{project_id}/cancel", response_model=AiSiteProjectResponse)
async def cancel_ai_site_project(
    project_id: UUID,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> AiSiteProjectResponse:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    snapshot = await service(session, crypto, settings).cancel(
        project_id, identity.user.id, correlation_id=correlation_id(request)
    )
    AuditService(session, crypto).record(
        "ai_site_generation.cancelled",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="ai_site_generation",
        target_id=str(snapshot.generation.id),
        reason="USER_CANCEL",
        ip_address=request_ip(request, settings),
        metadata={"attempt": snapshot.job.attempt},
    )
    await session.commit()
    return response(snapshot)


@router.get(
    "/ai-site-projects/{project_id}/generations/{generation_id}/artifact",
    response_model=AiArtifactAccessResponse,
)
async def access_ai_generation_artifact(
    project_id: UUID,
    generation_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> AiArtifactAccessResponse:
    artifact = await service(session, crypto, settings).artifact_for_owner(
        project_id, generation_id, identity.user.id
    )
    storage = publication_storage_for(settings)
    try:
        download_url = await run_in_threadpool(
            storage.presign_get,
            artifact.object_key,
            settings.ai_artifact_url_ttl_seconds,
        )
    except Exception as error:
        raise problem(
            503, "ai_artifact_storage_unavailable", "Preview is temporarily unavailable."
        ) from error
    return AiArtifactAccessResponse(
        generation_id=generation_id,
        checksum_sha256=artifact.checksum_sha256,
        size_bytes=artifact.size_bytes,
        content_type=artifact.content_type,
        download_url=download_url,
        expires_in_seconds=settings.ai_artifact_url_ttl_seconds,
    )
