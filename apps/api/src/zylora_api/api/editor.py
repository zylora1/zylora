from __future__ import annotations

import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_session
from zylora_api.db.website_models import AiOperation, Website
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
from zylora_api.modules.editor.provider import AiPlanner, get_ai_planner
from zylora_api.modules.editor.revisions import AiCreditService, RevisionService
from zylora_api.modules.editor.schemas import (
    AiEditRequest,
    AiUsageListResponse,
    AiUsageResponse,
    CreditResponse,
    EditorMutationResponse,
    EditorStateResponse,
    ManualEditRequest,
    RestoreRequest,
    RevisionResponse,
)
from zylora_api.modules.editor.service import AppliedEdit, EditorService
from zylora_api.modules.websites.service import WebsiteService

router = APIRouter(prefix="/api/v1", tags=["editor"])


def planner_dependency(settings: Annotated[Settings, Depends(get_settings)]) -> AiPlanner:
    return get_ai_planner(settings)


async def state_response(
    session: AsyncSession, website: Website, user_id: UUID
) -> EditorStateResponse:
    revisions = RevisionService(session)
    current = await revisions.current(website)
    history = await revisions.history(website.id)
    account = await AiCreditService(session).account(user_id)
    return EditorStateResponse(
        website_id=website.id,
        display_name=website.display_name,
        status=website.status,
        revision=website.revision,
        document=current.document,
        revisions=[
            RevisionResponse(
                id=item.id,
                revision=item.revision,
                source=item.source,
                edit_summary=item.edit_summary,
                checksum=item.checksum,
                created_at=item.created_at,
            )
            for item in history
        ],
        credits=CreditResponse(
            balance=account.balance,
            allowance=account.allowance,
            period_start=account.period_start,
            period_end=account.period_end,
        ),
    )


async def mutation_response(
    session: AsyncSession,
    applied: AppliedEdit,
    user_id: UUID,
    operation_id: UUID,
    source: str,
) -> EditorMutationResponse:
    state = await state_response(session, applied.website, user_id)
    return EditorMutationResponse(
        **state.model_dump(),
        operation_id=operation_id,
        source=source,
        summary=applied.version.edit_summary,
        credits_used=applied.credits_used,
    )


def secure_mutation(
    request: Request, identity: RequestIdentity, settings: Settings, crypto: AuthCrypto
) -> None:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)


def record_edit_audit(
    session: AsyncSession,
    crypto: AuthCrypto,
    request: Request,
    settings: Settings,
    identity: RequestIdentity,
    website_id: UUID,
    source: str,
    summary: str,
    credits_used: int,
) -> None:
    AuditService(session, crypto).record(
        "website.editor_change_applied",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="website",
        target_id=str(website_id),
        reason=f"{source}_EDIT",
        ip_address=request_ip(request, settings),
        metadata={"source": source, "summary": summary, "credits_used": credits_used},
    )


@router.get("/websites/{website_id}/editor", response_model=EditorStateResponse)
async def editor_state(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EditorStateResponse:
    website = await WebsiteService(session).get_for_owner(website_id, identity.user.id)
    result = await state_response(session, website, identity.user.id)
    await session.commit()
    return result


@router.post("/websites/{website_id}/editor/edits", response_model=EditorMutationResponse)
async def manual_edit(
    website_id: UUID,
    payload: ManualEditRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> EditorMutationResponse:
    secure_mutation(request, identity, settings, crypto)
    applied = await EditorService(session).manual_edit(website_id, identity.user.id, payload)
    record_edit_audit(
        session,
        crypto,
        request,
        settings,
        identity,
        website_id,
        "MANUAL",
        applied.version.edit_summary,
        0,
    )
    result = await mutation_response(
        session, applied, identity.user.id, payload.operation_id, "MANUAL"
    )
    await session.commit()
    return result


@router.post("/websites/{website_id}/editor/ai-edits", response_model=EditorMutationResponse)
async def ai_edit(
    website_id: UUID,
    payload: AiEditRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    planner: Annotated[AiPlanner, Depends(planner_dependency)],
) -> EditorMutationResponse:
    secure_mutation(request, identity, settings, crypto)
    safety_identifier = hashlib.sha256(f"zylora-ai:{identity.user.id}".encode()).hexdigest()
    applied = await EditorService(session).ai_edit(
        website_id, identity.user.id, payload, planner, safety_identifier
    )
    record_edit_audit(
        session,
        crypto,
        request,
        settings,
        identity,
        website_id,
        "AI",
        applied.version.edit_summary,
        applied.credits_used,
    )
    result = await mutation_response(session, applied, identity.user.id, payload.operation_id, "AI")
    await session.commit()
    return result


@router.post(
    "/websites/{website_id}/editor/versions/{version_id}/restore",
    response_model=EditorMutationResponse,
)
async def restore_revision(
    website_id: UUID,
    version_id: UUID,
    payload: RestoreRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> EditorMutationResponse:
    secure_mutation(request, identity, settings, crypto)
    applied = await EditorService(session).restore(
        website_id,
        identity.user.id,
        version_id,
        payload.operation_id,
        payload.base_revision,
    )
    record_edit_audit(
        session,
        crypto,
        request,
        settings,
        identity,
        website_id,
        "RESTORE",
        applied.version.edit_summary,
        0,
    )
    result = await mutation_response(
        session, applied, identity.user.id, payload.operation_id, "RESTORE"
    )
    await session.commit()
    return result


@router.get("/websites/{website_id}/editor/ai-usage", response_model=AiUsageListResponse)
async def ai_usage(
    website_id: UUID,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AiUsageListResponse:
    await WebsiteService(session).get_for_owner(website_id, identity.user.id)
    operations = list(
        (
            await session.scalars(
                select(AiOperation)
                .where(
                    AiOperation.website_id == website_id,
                    AiOperation.user_id == identity.user.id,
                )
                .order_by(AiOperation.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    return AiUsageListResponse(
        items=[
            AiUsageResponse(
                operation_id=item.id,
                status=item.status,
                provider=item.provider,
                model=item.model,
                cost_credits=item.cost_credits,
                usage=item.usage,
                latency_ms=item.latency_ms,
                created_at=item.created_at,
            )
            for item in operations
        ]
    )
