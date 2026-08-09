from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.errors import (
    CHALLENGE_FAILED,
    CHALLENGE_REQUIRED,
    CHALLENGE_UNAVAILABLE,
)
from zylora_api.modules.auth.security import AuthCrypto


class TurnstileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    hostname: str | None = None
    action: str | None = None
    error_codes: list[str] = Field(default_factory=list, alias="error-codes")


class TurnstileProviderUnavailable(Exception):
    """Provider transport/configuration failed without exposing sensitive details."""


class TurnstileVerifier(Protocol):
    async def verify(
        self,
        *,
        token: str,
        remote_ip: str,
        idempotency_key: str,
    ) -> TurnstileResponse: ...


class CloudflareTurnstileVerifier:
    SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def verify(
        self,
        *,
        token: str,
        remote_ip: str,
        idempotency_key: str,
    ) -> TurnstileResponse:
        secret = self._settings.turnstile_secret_key
        if not secret:
            raise TurnstileProviderUnavailable
        if not token or len(token) > 2048:
            return TurnstileResponse(success=False, **{"error-codes": ["invalid-input-response"]})
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.turnstile_timeout_seconds
            ) as client:
                response = await client.post(
                    self.SITEVERIFY_URL,
                    json={
                        "secret": secret,
                        "response": token,
                        "remoteip": remote_ip,
                        "idempotency_key": idempotency_key,
                    },
                )
                response.raise_for_status()
                return TurnstileResponse.model_validate(response.json())
        except (httpx.HTTPError, OSError, ValueError, ValidationError) as error:
            raise TurnstileProviderUnavailable from error


@dataclass(frozen=True)
class ChallengeDecision:
    action: str
    hostname: str


class ChallengeService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        crypto: AuthCrypto,
        verifier: TurnstileVerifier,
    ) -> None:
        self._session = session
        self._settings = settings
        self._verifier = verifier
        self._audit = AuditService(session, crypto)

    async def enforce(
        self,
        token: str | None,
        *,
        expected_action: str,
        remote_ip: str,
        correlation_id: str,
    ) -> ChallengeDecision | None:
        if not self._settings.turnstile_enabled:
            return None
        if token is None or not token.strip():
            await self._reject(
                expected_action,
                remote_ip,
                correlation_id,
                reason="missing",
                problem=CHALLENGE_REQUIRED,
            )
        assert token is not None
        try:
            result = await self._verifier.verify(
                token=token,
                remote_ip=remote_ip,
                idempotency_key=str(uuid4()),
            )
        except TurnstileProviderUnavailable:
            await self._reject(
                expected_action,
                remote_ip,
                correlation_id,
                reason="provider_unavailable",
                problem=CHALLENGE_UNAVAILABLE,
            )
        if not result.success:
            reason = (
                "expired_or_replayed" if "timeout-or-duplicate" in result.error_codes else "invalid"
            )
            await self._reject(
                expected_action,
                remote_ip,
                correlation_id,
                reason=reason,
                problem=CHALLENGE_FAILED,
            )
        hostname = result.hostname or ""
        if hostname not in self._settings.turnstile_allowed_hostname_values:
            await self._reject(
                expected_action,
                remote_ip,
                correlation_id,
                reason="hostname_mismatch",
                problem=CHALLENGE_FAILED,
            )
        if result.action != expected_action:
            await self._reject(
                expected_action,
                remote_ip,
                correlation_id,
                reason="action_mismatch",
                problem=CHALLENGE_FAILED,
            )
        return ChallengeDecision(action=expected_action, hostname=hostname)

    async def _reject(
        self,
        action: str,
        remote_ip: str,
        correlation_id: str,
        *,
        reason: str,
        problem: Exception,
    ) -> None:
        self._audit.record(
            "auth.challenge_rejected",
            correlation_id=correlation_id,
            target_type="turnstile_challenge",
            reason=reason,
            ip_address=remote_ip,
            metadata={"action": action},
        )
        await self._session.commit()
        raise problem
