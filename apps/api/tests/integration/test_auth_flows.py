from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.app import create_app
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import AuthIdentity, EmailVerification, User
from zylora_api.db.session import get_engine
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.http import get_email_sender
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.auth.service import AuthenticationService, SessionService


class CapturingEmailSender:
    def __init__(self) -> None:
        self.verification_codes: list[tuple[str, str]] = []
        self.reset_tokens: list[tuple[str, str]] = []

    async def send_verification(self, *, email: str, code: str) -> None:
        self.verification_codes.append((email, code))

    async def send_password_reset(self, *, email: str, token: str) -> None:
        self.reset_tokens.append((email, token))


@pytest.mark.integration
async def test_email_auth_lifecycle_is_single_use_hashed_and_revokes_sessions() -> None:
    settings = Settings(environment="test", storage_provider="memory", _env_file=None)
    crypto = AuthCrypto(settings.auth_secret)
    sender = CapturingEmailSender()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    email = f"phase2-{uuid4()}@example.com"
    password = "Initial-Password-42!"
    new_password = "Changed-Password-84!"
    ip_address = f"127.0.0.{uuid4().int % 200 + 1}"

    async with factory() as session:
        service = AuthenticationService(session, settings, crypto, sender)
        await service.signup(email, password, ip_address=ip_address, correlation_id="phase2-signup")
        user = await session.scalar(select(User).where(User.normalized_email == email))
        assert user is not None
        assert user.status == "PENDING_VERIFICATION"
        assert user.password_hash and password not in user.password_hash
        verification = await session.scalar(
            select(EmailVerification).where(EmailVerification.user_id == user.id)
        )
        assert verification is not None
        first_code = sender.verification_codes[-1][1]
        assert first_code.encode() not in verification.code_digest

        await service.resend_verification(
            email, ip_address=ip_address, correlation_id="phase2-resend"
        )
        second_code = sender.verification_codes[-1][1]
        assert second_code != first_code
        with pytest.raises(AuthProblem, match="Verification failed"):
            await service.verify_email(
                email,
                first_code,
                ip_address=ip_address,
                correlation_id="phase2-old-code",
            )
        user = await service.verify_email(
            email,
            second_code,
            ip_address=ip_address,
            correlation_id="phase2-verify",
        )
        assert user.status == "ACTIVE"
        assert user.verified_at is not None

        user, secrets = await service.login(
            email,
            password,
            audience="USER_WEB",
            ip_address=ip_address,
            user_agent="Mozilla/5.0 Windows Chrome",
            correlation_id="phase2-login",
        )
        assert secrets.token.encode() not in secrets.session.token_hash
        authenticated_session, authenticated_user = await service.sessions.authenticate(
            secrets.token, audience="USER_WEB"
        )
        assert authenticated_user.id == user.id
        assert authenticated_session.device_name == "Chrome on Windows"

        await service.request_password_reset(
            email, ip_address=ip_address, correlation_id="phase2-reset-request"
        )
        reset_token = sender.reset_tokens[-1][1]
        await service.confirm_password_reset(
            reset_token,
            new_password,
            ip_address=ip_address,
            correlation_id="phase2-reset-confirm",
        )
        with pytest.raises(AuthProblem, match="Authentication required"):
            await service.sessions.authenticate(secrets.token, audience="USER_WEB")
        with pytest.raises(AuthProblem, match="Reset failed"):
            await service.confirm_password_reset(
                reset_token,
                new_password,
                ip_address=ip_address,
                correlation_id="phase2-reset-reuse",
            )
        _, new_secrets = await service.login(
            email,
            new_password,
            audience="USER_WEB",
            ip_address=ip_address,
            user_agent="Mozilla/5.0 Windows Firefox",
            correlation_id="phase2-login-new",
        )
        assert new_secrets.session.id != secrets.session.id

        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(status="DELETED", auth_epoch=user.auth_epoch + 1)
        )
        await session.commit()


@pytest.mark.integration
async def test_admin_audience_isolated_and_database_allows_only_one_super_admin() -> None:
    settings = Settings(environment="test", storage_provider="memory", _env_file=None)
    crypto = AuthCrypto(settings.auth_secret)
    sender = CapturingEmailSender()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    email = f"admin-{uuid4()}@example.com"
    password = "Admin-Password-42!"

    async with factory() as session:
        if await session.scalar(
            select(func.count(User.id)).where(User.account_type == "SUPER_ADMIN")
        ):
            pytest.skip("development database already contains its Super Admin")
        admin = User(
            account_type="SUPER_ADMIN",
            normalized_email=email,
            display_email=email,
            password_hash=crypto.hash_password(password),
            status="ACTIVE",
            verified_at=datetime.now(UTC),
        )
        session.add(admin)
        await session.flush()
        session.add(AuthIdentity(user_id=admin.id, provider="PASSWORD", provider_subject=email))
        await session.commit()
        admin_id = admin.id
        service = AuthenticationService(session, settings, crypto, sender)

        _, secrets = await service.login(
            email,
            password,
            audience="ADMIN_WEB",
            ip_address="127.0.0.2",
            user_agent="Mozilla/5.0 macOS Safari",
            correlation_id="phase2-admin-login",
        )
        with pytest.raises(AuthProblem, match="Authentication required"):
            await SessionService(session, settings, crypto).authenticate(
                secrets.token, audience="USER_WEB"
            )
        with pytest.raises(AuthProblem, match="Authentication failed"):
            await service.login(
                email,
                password,
                audience="USER_WEB",
                ip_address="127.0.0.2",
                user_agent="Mozilla/5.0",
                correlation_id="phase2-admin-user-boundary",
            )
        second = User(
            account_type="SUPER_ADMIN",
            normalized_email=f"second-{email}",
            display_email=f"second-{email}",
            status="ACTIVE",
            verified_at=datetime.now(UTC),
        )
        session.add(second)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        await session.execute(
            update(User)
            .where(User.id == admin_id)
            .values(account_type="USER", status="DELETED", auth_epoch=2)
        )
        await session.commit()


@pytest.mark.integration
async def test_auth_http_contract_rejects_unknown_fields_and_cross_origin() -> None:
    app = create_app()
    app.dependency_overrides[get_email_sender] = CapturingEmailSender
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        unknown = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": "contract@example.com",
                "password": "Contract-Password-42!",
                "account_type": "SUPER_ADMIN",
            },
        )
        cross_origin = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "Wrong-Password-42!"},
            headers={"Origin": "https://evil.example"},
        )

    assert unknown.status_code == 422
    assert unknown.headers["content-type"].startswith("application/problem+json")
    assert unknown.json()["code"] == "validation_failed"
    assert cross_origin.status_code == 403
    assert cross_origin.json()["code"] == "csrf_rejected"
    assert "correlation_id" in cross_origin.json()


@pytest.mark.integration
async def test_resend_budget_uses_progressive_account_and_ip_cooldown() -> None:
    settings = Settings(environment="test", storage_provider="memory", _env_file=None)
    crypto = AuthCrypto(settings.auth_secret)
    sender = CapturingEmailSender()
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    email = f"throttle-{uuid4()}@example.com"
    ip_address = f"10.12.{uuid4().int % 200 + 1}.{uuid4().int % 200 + 1}"

    async with factory() as session:
        service = AuthenticationService(session, settings, crypto, sender)
        await service.signup(
            email,
            "Throttle-Password-42!",
            ip_address=ip_address,
            correlation_id="throttle-signup",
        )
        for attempt in range(3):
            await service.resend_verification(
                email,
                ip_address=ip_address,
                correlation_id=f"throttle-resend-{attempt}",
            )

        with pytest.raises(AuthProblem) as caught:
            await service.resend_verification(
                email,
                ip_address=ip_address,
                correlation_id="throttle-resend-blocked",
            )

        assert caught.value.code == "rate_limited"
        assert caught.value.retry_after_seconds is not None
        assert 1 <= caught.value.retry_after_seconds <= 60
        user = await session.scalar(select(User).where(User.normalized_email == email))
        assert user is not None
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(status="DELETED", auth_epoch=user.auth_epoch + 1)
        )
        await session.commit()
