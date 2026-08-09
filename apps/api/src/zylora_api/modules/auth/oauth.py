from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from joserfc import jwt
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import AuthIdentity, OAuthTransaction, User
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.errors import OAUTH_INVALID, OAUTH_UNAVAILABLE, AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.auth.service import AbuseService, SessionSecrets, SessionService


@dataclass(frozen=True)
class GoogleProfile:
    subject: str
    email: str


class GoogleProvider(Protocol):
    def authorization_url(
        self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str
    ) -> str: ...

    async def exchange(
        self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str
    ) -> GoogleProfile: ...


class GoogleOIDCAdapter:
    AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105
    JWKS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
    ISSUERS = ("https://accounts.google.com", "accounts.google.com")

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def authorization_url(
        self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str
    ) -> str:
        if not self._settings.google_client_id:
            raise OAUTH_UNAVAILABLE
        query = urlencode(
            {
                "client_id": self._settings.google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return f"{self.AUTHORIZATION_ENDPOINT}?{query}"

    async def exchange(
        self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str
    ) -> GoogleProfile:
        if not self._settings.google_client_id or not self._settings.google_client_secret:
            raise OAUTH_UNAVAILABLE
        try:
            oauth_client = cast(
                Any,
                AsyncOAuth2Client(
                    client_id=self._settings.google_client_id,
                    client_secret=self._settings.google_client_secret,
                    redirect_uri=redirect_uri,
                ),
            )
            try:
                token = await oauth_client.fetch_token(
                    self.TOKEN_ENDPOINT,
                    code=code,
                    code_verifier=code_verifier,
                )
            finally:
                await oauth_client.aclose()
            id_token = token.get("id_token")
            if not isinstance(id_token, str):
                raise OAUTH_INVALID
            async with httpx.AsyncClient(timeout=10) as http_client:
                response = await http_client.get(self.JWKS_ENDPOINT)
                response.raise_for_status()
                jwks = response.json()
            token = jwt.decode(
                id_token,
                KeySet.import_key_set(jwks),
                algorithms=["RS256"],
            )
            registry = JWTClaimsRegistry(
                leeway=30,
                iss={"essential": True, "values": list(self.ISSUERS)},
                aud={"essential": True, "value": self._settings.google_client_id},
                sub={"essential": True},
                exp={"essential": True},
                iat={"essential": True},
                nonce={"essential": True, "value": nonce},
                email={"essential": True},
                email_verified={"essential": True, "value": True},
            )
            registry.validate(token.claims)
            return GoogleProfile(subject=str(token.claims["sub"]), email=str(token.claims["email"]))
        except (httpx.HTTPError, OSError) as error:
            raise OAUTH_UNAVAILABLE from error
        except Exception as error:
            if error is OAUTH_UNAVAILABLE:
                raise
            raise OAUTH_INVALID from error


class GoogleOAuthService:
    TRANSACTION_TTL = timedelta(minutes=10)

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        crypto: AuthCrypto,
        adapter: GoogleProvider,
    ) -> None:
        self._session = session
        self._settings = settings
        self._crypto = crypto
        self._adapter = adapter
        self._sessions = SessionService(session, settings, crypto)
        self._audit = AuditService(session, crypto)
        self._abuse = AbuseService(session, crypto)

    async def start(self, *, ip_address: str, correlation_id: str) -> str:
        await self._abuse.enforce(action="oauth_start", subject=None, ip_address=ip_address)
        state = self._crypto.token()
        nonce = self._crypto.token()
        verifier = self._crypto.token(48)
        redirect_uri = self._settings.google_redirect_uri
        try:
            authorization_url = self._adapter.authorization_url(
                state=state,
                nonce=nonce,
                code_challenge=self._crypto.pkce_challenge(verifier),
                redirect_uri=redirect_uri,
            )
        except AuthProblem as error:
            self._abuse.record("oauth_start", None, ip_address, "FAILED", error.code)
            self._audit.record(
                "auth.google_start_failed",
                correlation_id=correlation_id,
                target_type="oauth_transaction",
                reason=error.code,
                ip_address=ip_address,
            )
            await self._session.commit()
            raise
        self._session.add(
            OAuthTransaction(
                state_digest=self._crypto.digest(state, purpose="oauth-state"),
                nonce_digest=self._crypto.digest(nonce, purpose="oauth-nonce"),
                nonce_ciphertext=self._crypto.encrypt(nonce, purpose="oauth-nonce"),
                code_verifier_digest=self._crypto.digest(verifier, purpose="oauth-pkce"),
                code_verifier_ciphertext=self._crypto.encrypt(verifier, purpose="oauth-pkce"),
                redirect_uri=redirect_uri,
                expires_at=datetime.now(UTC) + self.TRANSACTION_TTL,
            )
        )
        self._abuse.record("oauth_start", None, ip_address, "SUCCEEDED")
        await self._session.commit()
        return authorization_url

    async def cancel(self, *, state: str, ip_address: str, correlation_id: str) -> None:
        await self._abuse.enforce(action="oauth_callback", subject=None, ip_address=ip_address)
        transaction = await self._session.scalar(
            select(OAuthTransaction)
            .where(
                OAuthTransaction.state_digest == self._crypto.digest(state, purpose="oauth-state")
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if transaction is not None and transaction.consumed_at is None:
            transaction.consumed_at = now
        self._abuse.record("oauth_callback", None, ip_address, "FAILED", "provider_denied")
        self._audit.record(
            "auth.google_login_cancelled",
            correlation_id=correlation_id,
            target_type="oauth_transaction",
            reason="provider_denied",
            ip_address=ip_address,
        )
        await self._session.commit()

    async def finish(
        self,
        *,
        state: str,
        code: str,
        ip_address: str,
        user_agent: str | None,
        correlation_id: str,
    ) -> tuple[User, SessionSecrets]:
        await self._abuse.enforce(action="oauth_callback", subject=None, ip_address=ip_address)
        try:
            result = await self._finish_unthrottled(
                state=state,
                code=code,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
            )
        except AuthProblem as error:
            await self._session.rollback()
            self._abuse.record("oauth_callback", None, ip_address, "FAILED", error.code)
            self._audit.record(
                "auth.google_login_failed",
                correlation_id=correlation_id,
                target_type="oauth_transaction",
                reason=error.code,
                ip_address=ip_address,
            )
            await self._session.commit()
            raise
        self._abuse.record("oauth_callback", None, ip_address, "SUCCEEDED")
        await self._session.commit()
        return result

    async def _finish_unthrottled(
        self,
        *,
        state: str,
        code: str,
        ip_address: str,
        user_agent: str | None,
        correlation_id: str,
    ) -> tuple[User, SessionSecrets]:
        transaction = await self._session.scalar(
            select(OAuthTransaction)
            .where(
                OAuthTransaction.state_digest == self._crypto.digest(state, purpose="oauth-state")
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            transaction is None
            or transaction.consumed_at is not None
            or transaction.expires_at <= now
        ):
            raise OAUTH_INVALID
        transaction.consumed_at = now
        nonce = self._crypto.decrypt(transaction.nonce_ciphertext, purpose="oauth-nonce")
        if not self._crypto.constant_time_equal(
            transaction.nonce_digest, self._crypto.digest(nonce, purpose="oauth-nonce")
        ):
            raise OAUTH_INVALID
        verifier = self._crypto.decrypt(transaction.code_verifier_ciphertext, purpose="oauth-pkce")
        if not self._crypto.constant_time_equal(
            transaction.code_verifier_digest,
            self._crypto.digest(verifier, purpose="oauth-pkce"),
        ):
            raise OAUTH_INVALID
        profile = await self._adapter.exchange(
            code=code,
            code_verifier=verifier,
            nonce=nonce,
            redirect_uri=transaction.redirect_uri,
        )
        normalized, display = self._crypto.normalize_email(profile.email)
        identity = await self._session.scalar(
            select(AuthIdentity).where(
                AuthIdentity.provider == "GOOGLE",
                AuthIdentity.provider_subject == profile.subject,
            )
        )
        user = await self._session.get(User, identity.user_id) if identity else None
        if user is None:
            user = await self._session.scalar(
                select(User).where(User.normalized_email == normalized).with_for_update()
            )
            if user is not None and user.account_type != "USER":
                raise OAUTH_INVALID
            if user is None:
                user = User(
                    account_type="USER",
                    normalized_email=normalized,
                    display_email=display,
                    status="ACTIVE",
                    verified_at=now,
                )
                self._session.add(user)
                await self._session.flush()
            elif user.status == "PENDING_VERIFICATION":
                user.status = "ACTIVE"
                user.verified_at = now
                user.version += 1
            elif user.status != "ACTIVE":
                raise OAUTH_INVALID
            self._session.add(
                AuthIdentity(
                    user_id=user.id,
                    provider="GOOGLE",
                    provider_subject=profile.subject,
                )
            )
        if user.status != "ACTIVE" or user.account_type != "USER":
            raise OAUTH_INVALID
        secrets = await self._sessions.create(
            user, audience="USER_WEB", ip_address=ip_address, user_agent=user_agent
        )
        self._audit.record(
            "auth.google_login_succeeded",
            correlation_id=correlation_id,
            actor_user_id=user.id,
            target_type="session",
            target_id=str(secrets.session.id),
            ip_address=ip_address,
        )
        await self._session.commit()
        return user, secrets
