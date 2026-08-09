from __future__ import annotations

from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import AuthIdentity, User
from zylora_api.db.session import get_engine
from zylora_api.modules.auth.errors import OAUTH_UNAVAILABLE, AuthProblem
from zylora_api.modules.auth.oauth import GoogleOAuthService, GoogleProfile
from zylora_api.modules.auth.security import AuthCrypto


class FakeGoogleAdapter:
    def __init__(self, profile: GoogleProfile) -> None:
        self.profile = profile
        self.last_nonce: str | None = None
        self.unavailable = False

    def authorization_url(
        self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str
    ) -> str:
        return (
            f"https://accounts.google.test/authorize?state={state}&nonce={nonce}"
            f"&code_challenge={code_challenge}&redirect_uri={redirect_uri}"
        )

    async def exchange(
        self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str
    ) -> GoogleProfile:
        if self.unavailable:
            raise OAUTH_UNAVAILABLE
        assert code == "authorization-code"
        assert len(code_verifier) >= 32
        assert redirect_uri.endswith("/api/v1/auth/google/callback")
        self.last_nonce = nonce
        return self.profile


@pytest.mark.integration
async def test_google_oauth_transaction_creates_and_reuses_one_verified_identity() -> None:
    settings = Settings(
        environment="test",
        storage_provider="memory",
        google_client_id="google-client",
        google_client_secret="google-secret",
        _env_file=None,
    )
    crypto = AuthCrypto(settings.auth_secret)
    email = f"google-{uuid4()}@example.com"
    adapter = FakeGoogleAdapter(GoogleProfile(subject=f"subject-{uuid4()}", email=email))
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)

    async with factory() as session:
        service = GoogleOAuthService(session, settings, crypto, adapter)
        start_url = await service.start(
            ip_address="127.0.0.21", correlation_id="google-start-first"
        )
        query = parse_qs(urlparse(start_url).query)
        state = query["state"][0]
        nonce = query["nonce"][0]
        user, first_session = await service.finish(
            state=state,
            code="authorization-code",
            ip_address="127.0.0.21",
            user_agent="Google OAuth test",
            correlation_id="google-first",
        )

        assert user.status == "ACTIVE"
        assert user.verified_at is not None
        assert user.password_hash is None
        assert adapter.last_nonce == nonce
        identity = await session.scalar(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user.id, AuthIdentity.provider == "GOOGLE"
            )
        )
        assert identity is not None

        second_url = await service.start(
            ip_address="127.0.0.22", correlation_id="google-start-second"
        )
        second_state = parse_qs(urlparse(second_url).query)["state"][0]
        same_user, second_session = await service.finish(
            state=second_state,
            code="authorization-code",
            ip_address="127.0.0.22",
            user_agent="Google OAuth test",
            correlation_id="google-second",
        )
        assert same_user.id == user.id
        assert second_session.session.id != first_session.session.id

        user_id = user.id
        user_auth_epoch = user.auth_epoch
        with pytest.raises(AuthProblem, match="Google sign-in failed"):
            await service.finish(
                state="invalid-state-value-with-enough-characters",
                code="authorization-code",
                ip_address="127.0.0.23",
                user_agent=None,
                correlation_id="google-invalid",
            )

        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(status="DELETED", auth_epoch=user_auth_epoch + 1)
        )
        await session.commit()


@pytest.mark.integration
async def test_google_verified_email_activates_pending_user_and_provider_outage_is_atomic() -> None:
    settings = Settings(
        environment="test",
        storage_provider="memory",
        google_client_id="google-client",
        google_client_secret="google-secret",
        _env_file=None,
    )
    crypto = AuthCrypto(settings.auth_secret)
    email = f"pending-google-{uuid4()}@example.com"
    adapter = FakeGoogleAdapter(GoogleProfile(subject=f"subject-{uuid4()}", email=email))
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)

    async with factory() as session:
        pending = User(
            account_type="USER",
            normalized_email=email,
            display_email=email,
            password_hash=crypto.hash_password("Pending-Password-42!"),
            status="PENDING_VERIFICATION",
        )
        session.add(pending)
        await session.commit()
        pending_id = pending.id
        service = GoogleOAuthService(session, settings, crypto, adapter)
        start_url = await service.start(ip_address="127.0.0.24", correlation_id="google-start-link")
        state = parse_qs(urlparse(start_url).query)["state"][0]
        linked, _ = await service.finish(
            state=state,
            code="authorization-code",
            ip_address="127.0.0.24",
            user_agent=None,
            correlation_id="google-link",
        )
        assert linked.id == pending_id
        assert linked.status == "ACTIVE"

        outage_url = await service.start(
            ip_address="127.0.0.25", correlation_id="google-start-outage"
        )
        outage_state = parse_qs(urlparse(outage_url).query)["state"][0]
        adapter.unavailable = True
        with pytest.raises(AuthProblem, match="Google sign-in unavailable"):
            await service.finish(
                state=outage_state,
                code="authorization-code",
                ip_address="127.0.0.25",
                user_agent=None,
                correlation_id="google-outage",
            )
        await session.rollback()
        await session.execute(
            update(User).where(User.id == pending_id).values(status="DELETED", auth_epoch=2)
        )
        await session.commit()
