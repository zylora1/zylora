from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar, Literal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import (
    AuthAttempt,
    AuthIdentity,
    EmailVerification,
    PasswordReset,
    Session,
    User,
)
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.delivery import EmailSender
from zylora_api.modules.auth.errors import (
    ACCOUNT_UNAVAILABLE,
    AUTHENTICATION_REQUIRED,
    DELIVERY_UNAVAILABLE,
    FORBIDDEN,
    INVALID_CREDENTIALS,
    RESET_INVALID,
    VERIFICATION_INVALID,
    rate_limited,
)
from zylora_api.modules.auth.security import AuthCrypto

Audience = Literal["USER_WEB", "ADMIN_WEB"]


@dataclass(frozen=True)
class SessionSecrets:
    session: Session
    token: str
    csrf_token: str


class AbuseService:
    WINDOW = timedelta(minutes=15)
    BACKOFF_SECONDS: ClassVar[dict[int, int]] = {3: 60, 4: 300}
    REQUEST_BUDGET_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {"oauth_start", "signup", "verification_resend", "password_reset_request"}
    )

    def __init__(self, session: AsyncSession, crypto: AuthCrypto) -> None:
        self._session = session
        self._crypto = crypto

    async def enforce(
        self,
        *,
        action: str,
        subject: str | None,
        ip_address: str,
    ) -> None:
        now = datetime.now(UTC)
        subject_digest = (
            self._crypto.digest(subject, purpose="attempt-subject") if subject else None
        )
        ip_digest = self._crypto.digest(ip_address, purpose="attempt-ip")
        conditions = [AuthAttempt.action == action, AuthAttempt.created_at >= now - self.WINDOW]
        identity_condition = AuthAttempt.ip_digest == ip_digest
        if subject_digest is not None:
            identity_condition = identity_condition | (AuthAttempt.subject_digest == subject_digest)
        if action not in self.REQUEST_BUDGET_ACTIONS:
            conditions.append(AuthAttempt.outcome.in_(("FAILED", "BLOCKED")))
        count, last_attempt_at = (
            await self._session.execute(
                select(func.count(AuthAttempt.id), func.max(AuthAttempt.created_at)).where(
                    *conditions,
                    identity_condition,
                )
            )
        ).one()
        attempt_count = int(count or 0)
        if attempt_count < 3 or last_attempt_at is None:
            return
        backoff_seconds = self.BACKOFF_SECONDS.get(attempt_count, 900)
        remaining = int(
            (last_attempt_at + timedelta(seconds=backoff_seconds) - now).total_seconds()
        )
        if remaining > 0:
            retry_after = max(1, remaining)
            self.record(action, subject, ip_address, "BLOCKED", "progressive_backoff")
            await self._session.commit()
            raise rate_limited(retry_after)

    def record(
        self,
        action: str,
        subject: str | None,
        ip_address: str,
        outcome: str,
        reason: str | None = None,
    ) -> None:
        self._session.add(
            AuthAttempt(
                action=action,
                subject_digest=(
                    self._crypto.digest(subject, purpose="attempt-subject") if subject else None
                ),
                ip_digest=self._crypto.digest(ip_address, purpose="attempt-ip"),
                outcome=outcome,
                reason_code=reason,
            )
        )


class SessionService:
    def __init__(self, session: AsyncSession, settings: Settings, crypto: AuthCrypto) -> None:
        self._session = session
        self._settings = settings
        self._crypto = crypto

    async def create(
        self,
        user: User,
        *,
        audience: Audience,
        ip_address: str,
        user_agent: str | None,
    ) -> SessionSecrets:
        token = self._crypto.token()
        csrf_token = self._crypto.token()
        minutes = (
            self._settings.admin_session_minutes
            if audience == "ADMIN_WEB"
            else self._settings.user_session_minutes
        )
        model = Session(
            user_id=user.id,
            token_hash=self._crypto.digest(token, purpose=f"session:{audience}"),
            csrf_hash=self._crypto.digest(csrf_token, purpose=f"csrf:{audience}"),
            audience=audience,
            auth_epoch=user.auth_epoch,
            expires_at=datetime.now(UTC) + timedelta(minutes=minutes),
            ip_address=ip_address,
            user_agent=(user_agent or "")[:512] or None,
            device_name=self._device_name(user_agent),
        )
        self._session.add(model)
        await self._session.flush()
        return SessionSecrets(model, token, csrf_token)

    async def authenticate(self, token: str | None, *, audience: Audience) -> tuple[Session, User]:
        if not token:
            raise AUTHENTICATION_REQUIRED
        now = datetime.now(UTC)
        row = (
            await self._session.execute(
                select(Session, User)
                .join(User, User.id == Session.user_id)
                .where(
                    Session.token_hash == self._crypto.digest(token, purpose=f"session:{audience}"),
                    Session.audience == audience,
                )
            )
        ).one_or_none()
        if row is None:
            raise AUTHENTICATION_REQUIRED
        model, user = row
        required_type = "SUPER_ADMIN" if audience == "ADMIN_WEB" else "USER"
        valid = (
            model.revoked_at is None
            and model.expires_at > now
            and model.auth_epoch == user.auth_epoch
            and user.status == "ACTIVE"
            and user.account_type == required_type
        )
        if not valid:
            raise AUTHENTICATION_REQUIRED
        model.last_seen_at = now
        return model, user

    def validate_csrf(self, model: Session, csrf_token: str | None) -> None:
        if not csrf_token:
            raise FORBIDDEN
        expected = self._crypto.digest(csrf_token, purpose=f"csrf:{model.audience}")
        if not self._crypto.constant_time_equal(expected, model.csrf_hash):
            raise FORBIDDEN

    async def revoke(self, model: Session, reason: str) -> None:
        model.revoked_at = datetime.now(UTC)
        model.revocation_reason = reason

    async def revoke_all(self, user: User, reason: str) -> None:
        await self._session.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revocation_reason=reason)
        )

    async def list_for_user(self, user: User, audience: Audience) -> list[Session]:
        return list(
            (
                await self._session.scalars(
                    select(Session)
                    .where(
                        Session.user_id == user.id,
                        Session.audience == audience,
                        Session.revoked_at.is_(None),
                        Session.expires_at > datetime.now(UTC),
                    )
                    .order_by(Session.last_seen_at.desc())
                )
            ).all()
        )

    async def find_for_user(self, session_id: UUID, user: User, audience: Audience) -> Session:
        model = await self._session.scalar(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user.id,
                Session.audience == audience,
                Session.revoked_at.is_(None),
            )
        )
        if model is None:
            raise FORBIDDEN
        return model

    @staticmethod
    def _device_name(user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        lowered = user_agent.casefold()
        browser = next(
            (
                name
                for needle, name in (
                    ("edg/", "Edge"),
                    ("firefox", "Firefox"),
                    ("chrome", "Chrome"),
                    ("safari", "Safari"),
                )
                if needle in lowered
            ),
            "Browser",
        )
        platform = next(
            (
                name
                for needle, name in (
                    ("windows", "Windows"),
                    ("macintosh", "macOS"),
                    ("iphone", "iPhone"),
                    ("android", "Android"),
                    ("linux", "Linux"),
                )
                if needle in lowered
            ),
            "Unknown device",
        )
        return f"{browser} on {platform}"


class AuthenticationService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        crypto: AuthCrypto,
        email_sender: EmailSender,
    ) -> None:
        self.session = session
        self.settings = settings
        self.crypto = crypto
        self.email_sender = email_sender
        self.sessions = SessionService(session, settings, crypto)
        self.abuse = AbuseService(session, crypto)
        self.audit = AuditService(session, crypto)

    async def signup(
        self, email: str, password: str, *, ip_address: str, correlation_id: str
    ) -> None:
        normalized, display = self.crypto.normalize_email(email)
        await self.abuse.enforce(
            action="signup",
            subject=normalized,
            ip_address=ip_address,
        )
        existing = await self.session.scalar(
            select(User).where(User.normalized_email == normalized)
        )
        if existing is not None:
            self.abuse.record("signup", normalized, ip_address, "SUCCEEDED", "generic_existing")
            await self.session.commit()
            return

        user = User(
            account_type="USER",
            normalized_email=normalized,
            display_email=display,
            password_hash=self.crypto.hash_password(password),
            status="PENDING_VERIFICATION",
        )
        self.session.add(user)
        await self.session.flush()
        self.session.add(
            AuthIdentity(user_id=user.id, provider="PASSWORD", provider_subject=normalized)
        )
        code = await self._new_verification(user)
        self.abuse.record("signup", normalized, ip_address, "SUCCEEDED")
        self.audit.record(
            "auth.user_registered",
            correlation_id=correlation_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            ip_address=ip_address,
        )
        await self.session.commit()
        try:
            await self.email_sender.send_verification(email=display, code=code)
        except Exception as error:
            raise DELIVERY_UNAVAILABLE from error

    async def resend_verification(
        self, email: str, *, ip_address: str, correlation_id: str
    ) -> None:
        normalized, _ = self.crypto.normalize_email(email)
        await self.abuse.enforce(
            action="verification_resend",
            subject=normalized,
            ip_address=ip_address,
        )
        user = await self.session.scalar(select(User).where(User.normalized_email == normalized))
        if user is None or user.status != "PENDING_VERIFICATION":
            self.abuse.record("verification_resend", normalized, ip_address, "SUCCEEDED", "generic")
            await self.session.commit()
            return
        code = await self._new_verification(user)
        self.audit.record(
            "auth.verification_resent",
            correlation_id=correlation_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            ip_address=ip_address,
        )
        self.abuse.record("verification_resend", normalized, ip_address, "SUCCEEDED")
        await self.session.commit()
        try:
            await self.email_sender.send_verification(email=user.display_email, code=code)
        except Exception as error:
            raise DELIVERY_UNAVAILABLE from error

    async def verify_email(
        self, email: str, code: str, *, ip_address: str, correlation_id: str
    ) -> User:
        normalized, _ = self.crypto.normalize_email(email)
        await self.abuse.enforce(
            action="email_verification",
            subject=normalized,
            ip_address=ip_address,
        )
        user = await self.session.scalar(select(User).where(User.normalized_email == normalized))
        if user is None:
            self.abuse.record("email_verification", normalized, ip_address, "FAILED", "invalid")
            await self.session.commit()
            raise VERIFICATION_INVALID
        verification = await self.session.scalar(
            select(EmailVerification)
            .where(
                EmailVerification.user_id == user.id,
                EmailVerification.consumed_at.is_(None),
                EmailVerification.superseded_at.is_(None),
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        valid = (
            verification is not None
            and verification.expires_at > now
            and verification.attempts < verification.max_attempts
            and self.crypto.constant_time_equal(
                verification.code_digest,
                self.crypto.digest(
                    code, purpose=f"verification:{user.id}:{verification.generation}"
                ),
            )
        )
        if not valid:
            if verification is not None:
                verification.attempts += 1
                if verification.attempts >= verification.max_attempts:
                    verification.superseded_at = now
            self.abuse.record("email_verification", normalized, ip_address, "FAILED", "invalid")
            await self.session.commit()
            raise VERIFICATION_INVALID
        assert verification is not None
        verification.consumed_at = now
        user.status = "ACTIVE"
        user.verified_at = now
        user.version += 1
        self.abuse.record("email_verification", normalized, ip_address, "SUCCEEDED")
        self.audit.record(
            "auth.email_verified",
            correlation_id=correlation_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            ip_address=ip_address,
        )
        await self.session.commit()
        return user

    async def login(
        self,
        email: str,
        password: str,
        *,
        audience: Audience,
        ip_address: str,
        user_agent: str | None,
        correlation_id: str,
    ) -> tuple[User, SessionSecrets]:
        normalized, _ = self.crypto.normalize_email(email)
        action = "admin_login" if audience == "ADMIN_WEB" else "user_login"
        await self.abuse.enforce(
            action=action,
            subject=normalized,
            ip_address=ip_address,
        )
        user = await self.session.scalar(select(User).where(User.normalized_email == normalized))
        expected_type = "SUPER_ADMIN" if audience == "ADMIN_WEB" else "USER"
        password_ok = self.crypto.verify_password(user.password_hash if user else None, password)
        if user is None or not password_ok or user.account_type != expected_type:
            self.abuse.record(action, normalized, ip_address, "FAILED", "invalid_credentials")
            self.audit.record(
                "auth.login_failed",
                correlation_id=correlation_id,
                target_type="account",
                reason="invalid_credentials",
                ip_address=ip_address,
                metadata={"audience": audience},
            )
            await self.session.commit()
            raise INVALID_CREDENTIALS
        if user.status != "ACTIVE":
            self.abuse.record(action, normalized, ip_address, "FAILED", "account_unavailable")
            await self.session.commit()
            raise ACCOUNT_UNAVAILABLE
        if user.password_hash and self.crypto.password_needs_rehash(user.password_hash):
            user.password_hash = self.crypto.hash_password(
                password, admin=user.account_type == "SUPER_ADMIN"
            )
        secrets = await self.sessions.create(
            user, audience=audience, ip_address=ip_address, user_agent=user_agent
        )
        self.abuse.record(action, normalized, ip_address, "SUCCEEDED")
        self.audit.record(
            "auth.login_succeeded",
            correlation_id=correlation_id,
            actor_user_id=user.id,
            target_type="session",
            target_id=str(secrets.session.id),
            ip_address=ip_address,
            metadata={"audience": audience},
        )
        await self.session.commit()
        return user, secrets

    async def request_password_reset(
        self, email: str, *, ip_address: str, correlation_id: str
    ) -> None:
        normalized, _ = self.crypto.normalize_email(email)
        await self.abuse.enforce(
            action="password_reset_request",
            subject=normalized,
            ip_address=ip_address,
        )
        user = await self.session.scalar(select(User).where(User.normalized_email == normalized))
        if user is None or user.status != "ACTIVE" or user.password_hash is None:
            self.abuse.record(
                "password_reset_request", normalized, ip_address, "SUCCEEDED", "generic"
            )
            await self.session.commit()
            return
        now = datetime.now(UTC)
        await self.session.execute(
            update(PasswordReset)
            .where(
                PasswordReset.user_id == user.id,
                PasswordReset.consumed_at.is_(None),
                PasswordReset.superseded_at.is_(None),
            )
            .values(superseded_at=now)
        )
        token = self.crypto.token(48)
        reset = PasswordReset(
            user_id=user.id,
            token_digest=self.crypto.digest(token, purpose="password-reset"),
            expires_at=now + timedelta(minutes=self.settings.password_reset_minutes),
        )
        self.session.add(reset)
        self.abuse.record("password_reset_request", normalized, ip_address, "SUCCEEDED")
        self.audit.record(
            "auth.password_reset_requested",
            correlation_id=correlation_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            ip_address=ip_address,
        )
        await self.session.commit()
        try:
            await self.email_sender.send_password_reset(email=user.display_email, token=token)
        except Exception as error:
            raise DELIVERY_UNAVAILABLE from error

    async def confirm_password_reset(
        self, token: str, new_password: str, *, ip_address: str, correlation_id: str
    ) -> None:
        await self.abuse.enforce(
            action="password_reset_confirm",
            subject=None,
            ip_address=ip_address,
        )
        reset = await self.session.scalar(
            select(PasswordReset)
            .where(
                PasswordReset.token_digest == self.crypto.digest(token, purpose="password-reset")
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            reset is None
            or reset.consumed_at is not None
            or reset.superseded_at is not None
            or reset.expires_at <= now
        ):
            self.abuse.record("password_reset_confirm", None, ip_address, "FAILED", "invalid")
            await self.session.commit()
            raise RESET_INVALID
        user = await self.session.get(User, reset.user_id, with_for_update=True)
        if user is None or user.status != "ACTIVE":
            raise RESET_INVALID
        user.password_hash = self.crypto.hash_password(
            new_password, admin=user.account_type == "SUPER_ADMIN"
        )
        user.auth_epoch += 1
        user.version += 1
        reset.consumed_at = now
        await self.sessions.revoke_all(user, "PASSWORD_RESET")
        self.abuse.record("password_reset_confirm", None, ip_address, "SUCCEEDED")
        self.audit.record(
            "auth.password_reset_completed",
            correlation_id=correlation_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            ip_address=ip_address,
        )
        await self.session.commit()

    async def _new_verification(self, user: User) -> str:
        now = datetime.now(UTC)
        current = await self.session.scalar(
            select(EmailVerification)
            .where(
                EmailVerification.user_id == user.id,
                EmailVerification.consumed_at.is_(None),
                EmailVerification.superseded_at.is_(None),
            )
            .with_for_update()
        )
        generation = 1
        if current is not None:
            current.superseded_at = now
            generation = current.generation + 1
            await self.session.flush()
        code = self.crypto.verification_code()
        self.session.add(
            EmailVerification(
                user_id=user.id,
                code_digest=self.crypto.digest(
                    code, purpose=f"verification:{user.id}:{generation}"
                ),
                expires_at=now + timedelta(minutes=self.settings.verification_minutes),
                generation=generation,
            )
        )
        return code
