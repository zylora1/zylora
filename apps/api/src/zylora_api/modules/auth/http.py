from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings, get_settings
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.auth.challenge import (
    ChallengeService,
    CloudflareTurnstileVerifier,
    TurnstileVerifier,
)
from zylora_api.modules.auth.delivery import EmailSender, SMTPEmailSender
from zylora_api.modules.auth.errors import CSRF_REJECTED
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.auth.service import Audience, AuthenticationService, SessionService

USER_COOKIE = "zylora_user_session"
USER_CSRF_COOKIE = "zylora_user_csrf"
ADMIN_COOKIE = "zylora_admin_session"
ADMIN_CSRF_COOKIE = "zylora_admin_csrf"


@lru_cache
def get_crypto() -> AuthCrypto:
    return AuthCrypto(get_settings().auth_secret)


def get_email_sender(settings: Annotated[Settings, Depends(get_settings)]) -> EmailSender:
    return SMTPEmailSender(settings)


def get_turnstile_verifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TurnstileVerifier:
    return CloudflareTurnstileVerifier(settings)


def get_challenge_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    verifier: Annotated[TurnstileVerifier, Depends(get_turnstile_verifier)],
) -> ChallengeService:
    return ChallengeService(session, settings, crypto, verifier)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> AuthenticationService:
    return AuthenticationService(session, settings, crypto, email_sender)


@dataclass(frozen=True)
class RequestIdentity:
    session: Session
    user: User
    token: str


def request_ip(request: Request, settings: Settings) -> str:
    peer = (request.client.host if request.client else "unknown")[:64]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and peer in settings.trusted_proxy_addresses:
        candidate = forwarded.split(",", 1)[0].strip()
        try:
            return str(ip_address(candidate))
        except ValueError:
            return peer
    return peer


def correlation_id(request: Request) -> str:
    return str(request.state.correlation_id)


def require_json_origin(request: Request, settings: Settings, *, admin: bool = False) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        raise CSRF_REJECTED
    origin = request.headers.get("origin")
    allowed = {settings.admin_origin} if admin else set(settings.allowed_origins)
    if origin is not None and origin not in allowed:
        raise CSRF_REJECTED
    if settings.environment in ("staging", "production") and origin is None:
        raise CSRF_REJECTED


async def authenticate_request(
    request: Request,
    session: AsyncSession,
    settings: Settings,
    crypto: AuthCrypto,
    *,
    audience: Audience,
) -> RequestIdentity:
    cookie_name = ADMIN_COOKIE if audience == "ADMIN_WEB" else USER_COOKIE
    token = request.cookies.get(cookie_name)
    model, user = await SessionService(session, settings, crypto).authenticate(
        token, audience=audience
    )
    return RequestIdentity(model, user, token or "")


async def get_user_identity(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> RequestIdentity:
    return await authenticate_request(request, session, settings, crypto, audience="USER_WEB")


async def get_admin_identity(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
) -> RequestIdentity:
    return await authenticate_request(request, session, settings, crypto, audience="ADMIN_WEB")


def require_csrf(request: Request, identity: RequestIdentity, crypto: AuthCrypto) -> None:
    csrf_cookie = (
        request.cookies.get(ADMIN_CSRF_COOKIE)
        if identity.session.audience == "ADMIN_WEB"
        else request.cookies.get(USER_CSRF_COOKIE)
    )
    header = request.headers.get("x-csrf-token")
    if not csrf_cookie or not header or csrf_cookie != header:
        raise CSRF_REJECTED
    expected = crypto.digest(header, purpose=f"csrf:{identity.session.audience}")
    if not crypto.constant_time_equal(expected, identity.session.csrf_hash):
        raise CSRF_REJECTED


def set_auth_cookies(
    response: Response,
    *,
    audience: Audience,
    token: str,
    csrf_token: str,
    settings: Settings,
    max_age: int,
) -> None:
    session_name = ADMIN_COOKIE if audience == "ADMIN_WEB" else USER_COOKIE
    csrf_name = ADMIN_CSRF_COOKIE if audience == "ADMIN_WEB" else USER_CSRF_COOKIE
    response.set_cookie(
        session_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        csrf_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_auth_cookies(response: Response, *, audience: Audience) -> None:
    session_name = ADMIN_COOKIE if audience == "ADMIN_WEB" else USER_COOKIE
    csrf_name = ADMIN_CSRF_COOKIE if audience == "ADMIN_WEB" else USER_CSRF_COOKIE
    response.delete_cookie(session_name, path="/")
    response.delete_cookie(csrf_name, path="/")
