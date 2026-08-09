from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from zylora_api.api.auth import get_google_service
from zylora_api.app import create_app
from zylora_api.core.config import get_settings
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import (
    RequestIdentity,
    get_admin_identity,
    get_auth_service,
    get_challenge_service,
    get_crypto,
    get_user_identity,
)
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.auth.service import SessionSecrets


class ScalarRows:
    def __init__(self, rows: list[Session]) -> None:
        self._rows = rows

    def all(self) -> list[Session]:
        return self._rows


class FakeSession:
    def __init__(self, session_model: Session) -> None:
        self.session_model = session_model
        self.commits = 0
        self.added: list[object] = []

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, statement: object) -> None:
        return None

    async def scalars(self, statement: object) -> ScalarRows:
        return ScalarRows([self.session_model])

    async def scalar(self, statement: object) -> Session:
        return self.session_model

    def add(self, model: object) -> None:
        self.added.append(model)


class FakeAuthService:
    def __init__(self, user: User, secrets: SessionSecrets) -> None:
        self.user = user
        self.secrets = secrets
        self.calls: list[str] = []

    async def signup(self, *args: object, **kwargs: object) -> None:
        self.calls.append("signup")

    async def resend_verification(self, *args: object, **kwargs: object) -> None:
        self.calls.append("resend")

    async def verify_email(self, *args: object, **kwargs: object) -> User:
        self.calls.append("verify")
        return self.user

    async def login(self, *args: object, **kwargs: object) -> tuple[User, SessionSecrets]:
        self.calls.append(f"login:{kwargs['audience']}")
        return self.user, self.secrets

    async def request_password_reset(self, *args: object, **kwargs: object) -> None:
        self.calls.append("reset_request")

    async def confirm_password_reset(self, *args: object, **kwargs: object) -> None:
        self.calls.append("reset_confirm")


class FakeChallengeService:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def enforce(self, *args: object, **kwargs: object) -> None:
        self.actions.append(str(kwargs["expected_action"]))


class FakeGoogleService:
    def __init__(self, user: User, secrets: SessionSecrets) -> None:
        self.user = user
        self.secrets = secrets

    async def start(self, **kwargs: object) -> str:
        return "https://accounts.google.com/authorize"

    async def finish(self, **kwargs: object) -> tuple[User, SessionSecrets]:
        return self.user, self.secrets

    async def cancel(self, **kwargs: object) -> None:
        return None


async def test_user_auth_route_matrix_and_cookie_contracts() -> None:
    crypto = AuthCrypto(get_settings().auth_secret)
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        account_type="USER",
        normalized_email="person@example.com",
        display_email="person@example.com",
        status="ACTIVE",
        verified_at=now,
        locale="en",
        timezone="UTC",
        auth_epoch=1,
    )
    model = Session(
        id=uuid4(),
        user_id=user.id,
        token_hash=b"s" * 32,
        csrf_hash=crypto.digest("csrf-value", purpose="csrf:USER_WEB"),
        audience="USER_WEB",
        auth_epoch=1,
        issued_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=1),
    )
    secrets = SessionSecrets(model, "opaque-token", "csrf-value")
    auth = FakeAuthService(user, secrets)
    challenge = FakeChallengeService()
    database = FakeSession(model)
    identity = RequestIdentity(model, user, "opaque-token")
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_challenge_service] = lambda: challenge
    app.dependency_overrides[get_google_service] = lambda: FakeGoogleService(user, secrets)
    app.dependency_overrides[get_user_identity] = lambda: identity
    app.dependency_overrides[get_session] = lambda: database

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "person@example.com", "password": "Strong-Password-42!"},
        )
        verify = await client.post(
            "/api/v1/auth/verify-email",
            json={"email": "person@example.com", "code": "123456"},
        )
        resend = await client.post(
            "/api/v1/auth/resend-verification", json={"email": "person@example.com"}
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "person@example.com", "password": "Strong-Password-42!"},
        )
        reset_request = await client.post(
            "/api/v1/auth/password-reset/request", json={"email": "person@example.com"}
        )
        reset_confirm = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "x" * 48, "new_password": "Changed-Password-42!"},
        )
        oauth_start = await client.post("/api/v1/auth/google/start", json={})
        oauth_callback = await client.get(
            "/api/v1/auth/google/callback", params={"state": "s" * 40, "code": "code"}
        )
        oauth_cancelled = await client.get(
            "/api/v1/auth/google/callback",
            params={"state": "s" * 40, "error": "access_denied"},
        )
        me = await client.get("/api/v1/auth/me")
        sessions = await client.get("/api/v1/auth/sessions")
        client.cookies.set("zylora_user_csrf", "csrf-value")
        logout = await client.post(
            "/api/v1/auth/logout", json={}, headers={"X-CSRF-Token": "csrf-value"}
        )
        client.cookies.set("zylora_user_csrf", "csrf-value")
        revoke = await client.request(
            "DELETE",
            f"/api/v1/auth/sessions/{model.id}",
            json={"reason": "USER_REQUEST"},
            headers={"X-CSRF-Token": "csrf-value"},
        )
        client.cookies.set("zylora_user_csrf", "csrf-value")
        logout_all = await client.post(
            "/api/v1/auth/logout-all",
            json={"reason": "SECURITY_REVIEW"},
            headers={"X-CSRF-Token": "csrf-value"},
        )

    assert [signup.status_code, verify.status_code, resend.status_code] == [202, 200, 202]
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    assert reset_request.status_code == 202
    assert reset_confirm.status_code == 200
    assert oauth_start.json()["authorization_url"].startswith("https://accounts.google.com")
    assert oauth_callback.status_code == 303
    assert oauth_callback.headers["location"] == "http://localhost:3000/app"
    assert "zylora_user_session=" in oauth_callback.headers["set-cookie"]
    assert oauth_cancelled.status_code == 303
    assert oauth_cancelled.headers["location"].endswith("/login?oauth_error=cancelled")
    assert me.json()["account_type"] == "USER"
    assert sessions.json()["sessions"][0]["current"] is True
    assert logout.status_code == 204
    assert revoke.status_code == 204
    assert logout_all.status_code == 204
    assert challenge.actions == [
        "signup",
        "verify_email",
        "verify_email",
        "login",
        "password_recovery",
        "password_recovery",
        "login",
    ]
    assert set(auth.calls) >= {
        "signup",
        "verify",
        "resend",
        "login:USER_WEB",
        "reset_request",
        "reset_confirm",
    }


async def test_admin_routes_use_the_admin_audience_and_cookie_namespace() -> None:
    crypto = AuthCrypto(get_settings().auth_secret)
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        account_type="SUPER_ADMIN",
        normalized_email="admin@example.com",
        display_email="admin@example.com",
        status="ACTIVE",
        verified_at=now,
        locale="en",
        timezone="UTC",
        auth_epoch=1,
    )
    model = Session(
        id=uuid4(),
        user_id=user.id,
        token_hash=b"a" * 32,
        csrf_hash=crypto.digest("admin-csrf", purpose="csrf:ADMIN_WEB"),
        audience="ADMIN_WEB",
        auth_epoch=1,
        issued_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    secrets = SessionSecrets(model, "admin-token", "admin-csrf")
    auth = FakeAuthService(user, secrets)
    challenge = FakeChallengeService()
    database = FakeSession(model)
    identity = RequestIdentity(model, user, "admin-token")
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_challenge_service] = lambda: challenge
    app.dependency_overrides[get_admin_identity] = lambda: identity
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_crypto] = lambda: crypto

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@example.com", "password": "Admin-Password-42!"},
        )
        me = await client.get("/api/v1/admin/me")
        sessions = await client.get("/api/v1/admin/sessions")
        client.cookies.set("zylora_admin_csrf", "admin-csrf")
        logout = await client.post(
            "/api/v1/admin/auth/logout", json={}, headers={"X-CSRF-Token": "admin-csrf"}
        )
        client.cookies.set("zylora_admin_csrf", "admin-csrf")
        revoke = await client.request(
            "DELETE",
            f"/api/v1/admin/sessions/{model.id}",
            json={"reason": "SECURITY_REVIEW"},
            headers={"X-CSRF-Token": "admin-csrf"},
        )

    assert login.status_code == 200
    assert "zylora_admin_session=" in login.headers["set-cookie"]
    assert "zylora_user_session=" not in login.headers["set-cookie"]
    assert me.json()["account_type"] == "SUPER_ADMIN"
    assert sessions.json()["sessions"][0]["audience"] == "ADMIN_WEB"
    assert logout.status_code == 204
    assert revoke.status_code == 204
    assert "login:ADMIN_WEB" in auth.calls
    assert challenge.actions == ["admin_login"]
