from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_session
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.challenge import ChallengeService
from zylora_api.modules.auth.http import (
    RequestIdentity,
    clear_auth_cookies,
    correlation_id,
    get_admin_identity,
    get_auth_service,
    get_challenge_service,
    get_crypto,
    request_ip,
    require_csrf,
    require_json_origin,
    set_auth_cookies,
)
from zylora_api.modules.auth.schemas import (
    AdminLoginRequest,
    AuthenticatedResponse,
    RevokeSessionRequest,
    SessionListResponse,
    SessionResponse,
    UserResponse,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.auth.service import AuthenticationService, SessionService

router = APIRouter(prefix="/api/v1/admin", tags=["super-admin-authentication"])


def admin_response(identity: RequestIdentity) -> UserResponse:
    user = identity.user
    return UserResponse(
        id=user.id,
        account_type=user.account_type,
        email=user.display_email,
        status=user.status,
        verified_at=user.verified_at,
        locale=user.locale,
        timezone=user.timezone,
    )


@router.post("/auth/login", response_model=AuthenticatedResponse)
async def login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthenticationService, Depends(get_auth_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> AuthenticatedResponse:
    require_json_origin(request, settings, admin=True)
    await challenge.enforce(
        payload.turnstile_token,
        expected_action="admin_login",
        remote_ip=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )
    user, secrets = await service.login(
        str(payload.email),
        payload.password,
        audience="ADMIN_WEB",
        ip_address=request_ip(request, settings),
        user_agent=request.headers.get("user-agent"),
        correlation_id=correlation_id(request),
    )
    set_auth_cookies(
        response,
        audience="ADMIN_WEB",
        token=secrets.token,
        csrf_token=secrets.csrf_token,
        settings=settings,
        max_age=settings.admin_session_minutes * 60,
    )
    return AuthenticatedResponse(
        user=UserResponse(
            id=user.id,
            account_type=user.account_type,
            email=user.display_email,
            status=user.status,
            verified_at=user.verified_at,
            locale=user.locale,
            timezone=user.timezone,
        ),
        csrf_token=secrets.csrf_token,
    )


@router.get("/me", response_model=UserResponse)
async def me(
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    await session.commit()
    return admin_response(identity)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> SessionListResponse:
    models = await SessionService(session, settings, crypto).list_for_user(
        identity.user, "ADMIN_WEB"
    )
    await session.commit()
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=model.id,
                audience=model.audience,
                issued_at=model.issued_at,
                last_seen_at=model.last_seen_at,
                expires_at=model.expires_at,
                device_name=model.device_name,
                current=model.id == identity.session.id,
            )
            for model in models
        ]
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> None:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)
    await SessionService(session, settings, crypto).revoke(identity.session, "ADMIN_LOGOUT")
    AuditService(session, crypto).record(
        "admin.auth.logout",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="session",
        target_id=str(identity.session.id),
        reason="ADMIN_LOGOUT",
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    clear_auth_cookies(response, audience="ADMIN_WEB")


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    payload: RevokeSessionRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_admin_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> None:
    require_json_origin(request, settings, admin=True)
    require_csrf(request, identity, crypto)
    service = SessionService(session, settings, crypto)
    target = await service.find_for_user(session_id, identity.user, "ADMIN_WEB")
    await service.revoke(target, payload.reason)
    AuditService(session, crypto).record(
        "admin.auth.session_revoked",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="session",
        target_id=str(target.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
    )
    await session.commit()
