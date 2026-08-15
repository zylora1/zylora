from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_session
from zylora_api.modules.analytics.activation import AttributionInput
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.challenge import ChallengeService
from zylora_api.modules.auth.http import (
    RequestIdentity,
    clear_auth_cookies,
    correlation_id,
    get_auth_service,
    get_challenge_service,
    get_crypto,
    get_user_identity,
    request_ip,
    require_csrf,
    require_json_origin,
    set_auth_cookies,
)
from zylora_api.modules.auth.oauth import GoogleOAuthService, GoogleOIDCAdapter
from zylora_api.modules.auth.schemas import (
    AuthAcceptedResponse,
    AuthenticatedResponse,
    ChallengeConfigResponse,
    ChallengedRequest,
    EmailRequest,
    LoginRequest,
    LogoutAllRequest,
    OAuthStartRequest,
    OAuthStartResponse,
    PasswordResetConfirmRequest,
    RevokeSessionRequest,
    SessionListResponse,
    SessionResponse,
    SignupRequest,
    UserResponse,
    VerificationRequiredResponse,
    VerifyEmailRequest,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.auth.service import AuthenticationService, SessionService

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def _attribution(payload: object) -> AttributionInput:
    value = getattr(payload, "attribution", None)
    return AttributionInput(**value.model_dump()) if value is not None else AttributionInput()


def _signup_country(request: Request, settings: Settings) -> str:
    # Cloudflare strips and supplies this header at the production edge; local/client
    # values are ignored.
    if settings.environment != "production":
        return "ZZ"
    candidate = (request.headers.get("cf-ipcountry") or "").strip().upper()
    return candidate if len(candidate) == 2 and candidate.isalpha() else "ZZ"


async def enforce_challenge(
    payload: ChallengedRequest,
    request: Request,
    settings: Settings,
    service: ChallengeService,
    *,
    action: str,
) -> None:
    await service.enforce(
        payload.turnstile_token,
        expected_action=action,
        remote_ip=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        account_type=user.account_type,
        email=user.display_email,
        status=user.status,
        verified_at=user.verified_at,
        locale=user.locale,
        timezone=user.timezone,
    )


def get_google_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> GoogleOAuthService:
    return GoogleOAuthService(session, settings, crypto, GoogleOIDCAdapter(settings))


@router.get("/challenge/config", response_model=ChallengeConfigResponse)
async def challenge_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChallengeConfigResponse:
    return ChallengeConfigResponse(
        enabled=settings.turnstile_enabled,
        site_key=settings.turnstile_site_key if settings.turnstile_enabled else None,
    )


@router.post(
    "/signup",
    response_model=VerificationRequiredResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def signup(
    payload: SignupRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthenticationService, Depends(get_auth_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> VerificationRequiredResponse:
    require_json_origin(request, settings)
    await enforce_challenge(payload, request, settings, challenge, action="signup")
    await service.signup(
        str(payload.email),
        payload.password,
        ip_address=request_ip(request, settings),
        correlation_id=correlation_id(request),
        attribution=_attribution(payload),
        country_code=_signup_country(request, settings),
    )
    return VerificationRequiredResponse(expires_in_seconds=settings.verification_minutes * 60)


@router.post("/verify-email", response_model=UserResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthenticationService, Depends(get_auth_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> UserResponse:
    require_json_origin(request, settings)
    await enforce_challenge(payload, request, settings, challenge, action="verify_email")
    user = await service.verify_email(
        str(payload.email),
        payload.code,
        ip_address=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )
    return user_response(user)


@router.post(
    "/resend-verification",
    response_model=AuthAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification(
    payload: EmailRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthenticationService, Depends(get_auth_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> AuthAcceptedResponse:
    require_json_origin(request, settings)
    await enforce_challenge(payload, request, settings, challenge, action="verify_email")
    await service.resend_verification(
        str(payload.email),
        ip_address=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )
    return AuthAcceptedResponse()


@router.post("/login", response_model=AuthenticatedResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthenticationService, Depends(get_auth_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> AuthenticatedResponse:
    require_json_origin(request, settings)
    await enforce_challenge(payload, request, settings, challenge, action="login")
    user, secrets = await service.login(
        str(payload.email),
        payload.password,
        audience="USER_WEB",
        ip_address=request_ip(request, settings),
        user_agent=request.headers.get("user-agent"),
        correlation_id=correlation_id(request),
    )
    set_auth_cookies(
        response,
        audience="USER_WEB",
        token=secrets.token,
        csrf_token=secrets.csrf_token,
        settings=settings,
        max_age=settings.user_session_minutes * 60,
    )
    return AuthenticatedResponse(user=user_response(user), csrf_token=secrets.csrf_token)


@router.post(
    "/password-reset/request",
    response_model=AuthAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    payload: EmailRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthenticationService, Depends(get_auth_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> AuthAcceptedResponse:
    require_json_origin(request, settings)
    await enforce_challenge(payload, request, settings, challenge, action="password_recovery")
    await service.request_password_reset(
        str(payload.email),
        ip_address=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )
    return AuthAcceptedResponse()


@router.post("/password-reset/confirm", response_model=AuthAcceptedResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthenticationService, Depends(get_auth_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> AuthAcceptedResponse:
    require_json_origin(request, settings)
    await enforce_challenge(payload, request, settings, challenge, action="password_recovery")
    await service.confirm_password_reset(
        payload.token,
        payload.new_password,
        ip_address=request_ip(request, settings),
        correlation_id=correlation_id(request),
    )
    return AuthAcceptedResponse()


@router.post("/google/start", response_model=OAuthStartResponse)
async def google_start(
    payload: OAuthStartRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[GoogleOAuthService, Depends(get_google_service)],
    challenge: Annotated[ChallengeService, Depends(get_challenge_service)],
) -> OAuthStartResponse:
    require_json_origin(request, settings)
    await enforce_challenge(payload, request, settings, challenge, action="login")
    return OAuthStartResponse(
        authorization_url=await service.start(
            ip_address=request_ip(request, settings),
            correlation_id=correlation_id(request),
            attribution=_attribution(payload),
            country_code=_signup_country(request, settings),
        )
    )


@router.get("/google/callback", response_model=None)
async def google_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[GoogleOAuthService, Depends(get_google_service)],
    state: str = Query(min_length=32, max_length=512),
    code: str | None = Query(default=None, min_length=1, max_length=4096),
    error: str | None = Query(default=None, max_length=200),
) -> Response:
    user_origin = settings.allowed_origins[0].rstrip("/")
    if error or not code:
        await service.cancel(
            state=state,
            ip_address=request_ip(request, settings),
            correlation_id=correlation_id(request),
        )
        return RedirectResponse(
            url=f"{user_origin}/login?oauth_error=cancelled",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    _user, secrets = await service.finish(
        state=state,
        code=code,
        ip_address=request_ip(request, settings),
        user_agent=request.headers.get("user-agent"),
        correlation_id=correlation_id(request),
    )
    response = RedirectResponse(url=f"{user_origin}/app", status_code=status.HTTP_303_SEE_OTHER)
    set_auth_cookies(
        response,
        audience="USER_WEB",
        token=secrets.token,
        csrf_token=secrets.csrf_token,
        settings=settings,
        max_age=settings.user_session_minutes * 60,
    )
    return response


@router.get("/me", response_model=UserResponse)
async def me(
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    await session.commit()
    return user_response(identity.user)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> SessionListResponse:
    models = await SessionService(session, settings, crypto).list_for_user(
        identity.user, "USER_WEB"
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> None:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    await SessionService(session, settings, crypto).revoke(identity.session, "USER_LOGOUT")
    AuditService(session, crypto).record(
        "auth.logout",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="session",
        target_id=str(identity.session.id),
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    clear_auth_cookies(response, audience="USER_WEB")


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    payload: LogoutAllRequest,
    request: Request,
    response: Response,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> None:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    await SessionService(session, settings, crypto).revoke_all(identity.user, payload.reason)
    identity.user.auth_epoch += 1
    AuditService(session, crypto).record(
        "auth.logout_all",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="user",
        target_id=str(identity.user.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
    )
    await session.commit()
    clear_auth_cookies(response, audience="USER_WEB")


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    payload: RevokeSessionRequest,
    request: Request,
    identity: Annotated[RequestIdentity, Depends(get_user_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> None:
    require_json_origin(request, settings)
    require_csrf(request, identity, crypto)
    service = SessionService(session, settings, crypto)
    target = await service.find_for_user(session_id, identity.user, "USER_WEB")
    await service.revoke(target, payload.reason)
    AuditService(session, crypto).record(
        "auth.session_revoked",
        correlation_id=correlation_id(request),
        actor_user_id=identity.user.id,
        target_type="session",
        target_id=str(target.id),
        reason=payload.reason,
        ip_address=request_ip(request, settings),
    )
    await session.commit()
