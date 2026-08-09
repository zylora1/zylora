from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Request, Response
from zylora_api.core.config import Settings
from zylora_api.core.problems import auth_problem_handler
from zylora_api.db.auth_models import Session, User
from zylora_api.modules.auth.errors import RATE_LIMITED, AuthProblem
from zylora_api.modules.auth.http import (
    RequestIdentity,
    clear_auth_cookies,
    request_ip,
    require_csrf,
    require_json_origin,
    set_auth_cookies,
)
from zylora_api.modules.auth.security import AuthCrypto


def make_request(headers: list[tuple[bytes, bytes]], cookies: str = "") -> Request:
    if cookies:
        headers.append((b"cookie", cookies.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_origin_and_json_contract_reject_cross_site_or_simple_requests() -> None:
    settings = Settings(_env_file=None)
    valid = make_request(
        [(b"content-type", b"application/json"), (b"origin", b"http://localhost:3000")]
    )
    require_json_origin(valid, settings)

    with pytest.raises(AuthProblem, match="Request rejected"):
        require_json_origin(make_request([(b"content-type", b"text/plain")]), settings)
    with pytest.raises(AuthProblem, match="Request rejected"):
        require_json_origin(
            make_request(
                [(b"content-type", b"application/json"), (b"origin", b"https://evil.test")]
            ),
            settings,
        )


def test_csrf_requires_matching_cookie_header_and_server_digest() -> None:
    crypto = AuthCrypto("test-auth-secret-with-more-than-thirty-two-characters")
    token = "csrf-value"
    model = Session(
        id=uuid4(),
        user_id=uuid4(),
        token_hash=b"x" * 32,
        csrf_hash=crypto.digest(token, purpose="csrf:USER_WEB"),
        audience="USER_WEB",
        auth_epoch=1,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    user = User(
        id=model.user_id,
        account_type="USER",
        normalized_email="user@example.com",
        display_email="user@example.com",
        status="ACTIVE",
        verified_at=datetime.now(UTC),
    )
    identity = RequestIdentity(model, user, "session")
    request = make_request([(b"x-csrf-token", token.encode())], cookies=f"zylora_user_csrf={token}")
    require_csrf(request, identity, crypto)

    with pytest.raises(AuthProblem):
        require_csrf(make_request([], cookies=f"zylora_user_csrf={token}"), identity, crypto)


def test_auth_cookie_names_are_audience_isolated_and_session_is_http_only() -> None:
    settings = Settings(_env_file=None)
    response = Response()
    set_auth_cookies(
        response,
        audience="ADMIN_WEB",
        token="opaque-session",
        csrf_token="csrf-value",
        settings=settings,
        max_age=1800,
    )
    headers = response.headers.getlist("set-cookie")

    assert any("zylora_admin_session=" in value and "HttpOnly" in value for value in headers)
    assert any("zylora_admin_csrf=" in value and "HttpOnly" not in value for value in headers)
    assert all("zylora_user_" not in value for value in headers)

    clear_auth_cookies(response, audience="ADMIN_WEB")
    assert any("Max-Age=0" in value for value in response.headers.getlist("set-cookie"))


async def test_rate_limit_problem_includes_retry_after_contract() -> None:
    request = make_request([])
    request.state.correlation_id = "rate-limit-test"

    response = await auth_problem_handler(request, RATE_LIMITED)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"


def test_request_ip_ignores_untrusted_forwarding_and_validates_trusted_proxy_input() -> None:
    spoofed = make_request([(b"x-forwarded-for", b"203.0.113.9")])
    assert request_ip(spoofed, Settings(_env_file=None)) == "127.0.0.1"

    trusted = Settings(trusted_proxy_ips="127.0.0.1", _env_file=None)
    assert request_ip(spoofed, trusted) == "203.0.113.9"
    malformed = make_request([(b"x-forwarded-for", b"not-an-ip")])
    assert request_ip(malformed, trusted) == "127.0.0.1"
