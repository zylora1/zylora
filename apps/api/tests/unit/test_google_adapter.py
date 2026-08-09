from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import httpx
import pytest
from zylora_api.core.config import Settings
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.oauth import GoogleOIDCAdapter


class FakeOAuthClient:
    token: ClassVar[dict[str, str]] = {"id_token": "signed-id-token"}
    failure: ClassVar[Exception | None] = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def fetch_token(self, endpoint: str, **kwargs: Any) -> dict[str, str]:
        if self.failure:
            raise self.failure
        assert endpoint.endswith("/token")
        assert kwargs["code_verifier"] == "verifier"
        return self.token

    async def aclose(self) -> None:
        return None


class FakeHTTPClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> FakeHTTPClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, endpoint: str) -> FakeResponse:
        assert endpoint.endswith("/certs")
        return FakeResponse()


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, list[dict[str, str]]]:
        return {"keys": [{"kid": "key-1"}]}


@dataclass
class FakeToken:
    claims: dict[str, object]


class FakeRegistry:
    validated: dict[str, object] | None = None

    def __init__(self, **kwargs: object) -> None:
        self.options = kwargs

    def validate(self, claims: dict[str, object]) -> None:
        self.validated = claims


def oauth_settings() -> Settings:
    return Settings(
        environment="test",
        storage_provider="memory",
        google_client_id="client-id",
        google_client_secret="client-secret",
        _env_file=None,
    )


def test_authorization_url_contains_state_nonce_pkce_and_allowlisted_redirect() -> None:
    adapter = GoogleOIDCAdapter(oauth_settings())
    url = adapter.authorization_url(
        state="state-value",
        nonce="nonce-value",
        code_challenge="pkce-value",
        redirect_uri="https://app.example/api/v1/auth/google/callback",
    )

    assert "state=state-value" in url
    assert "nonce=nonce-value" in url
    assert "code_challenge=pkce-value" in url
    assert "scope=openid+email+profile" in url


def test_authorization_url_fails_closed_without_client_configuration() -> None:
    adapter = GoogleOIDCAdapter(
        Settings(environment="test", storage_provider="memory", _env_file=None)
    )

    with pytest.raises(AuthProblem, match="Google sign-in unavailable"):
        adapter.authorization_url(
            state="state", nonce="nonce", code_challenge="pkce", redirect_uri="https://app"
        )


async def test_exchange_validates_signed_oidc_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    from zylora_api.modules.auth import oauth

    claims: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": "client-id",
        "sub": "google-subject",
        "email": "person@example.com",
        "email_verified": True,
        "nonce": "nonce-value",
    }
    monkeypatch.setattr(oauth, "AsyncOAuth2Client", FakeOAuthClient)
    monkeypatch.setattr(oauth.httpx, "AsyncClient", FakeHTTPClient)
    monkeypatch.setattr(oauth.KeySet, "import_key_set", lambda value: value)
    monkeypatch.setattr(oauth.jwt, "decode", lambda *args, **kwargs: FakeToken(claims))
    monkeypatch.setattr(oauth, "JWTClaimsRegistry", FakeRegistry)

    profile = await GoogleOIDCAdapter(oauth_settings()).exchange(
        code="authorization-code",
        code_verifier="verifier",
        nonce="nonce-value",
        redirect_uri="https://app.example/api/v1/auth/google/callback",
    )

    assert profile.subject == "google-subject"
    assert profile.email == "person@example.com"


@pytest.mark.parametrize("token", [{}, {"access_token": "not-an-id-token"}])
async def test_exchange_rejects_missing_id_token(
    monkeypatch: pytest.MonkeyPatch, token: dict[str, str]
) -> None:
    from zylora_api.modules.auth import oauth

    monkeypatch.setattr(FakeOAuthClient, "token", token)
    monkeypatch.setattr(FakeOAuthClient, "failure", None)
    monkeypatch.setattr(oauth, "AsyncOAuth2Client", FakeOAuthClient)

    with pytest.raises(AuthProblem, match="Google sign-in failed"):
        await GoogleOIDCAdapter(oauth_settings()).exchange(
            code="authorization-code",
            code_verifier="verifier",
            nonce="nonce-value",
            redirect_uri="https://app.example/api/v1/auth/google/callback",
        )


async def test_exchange_maps_provider_network_failure_to_safe_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from zylora_api.modules.auth import oauth

    request = httpx.Request("POST", "https://oauth2.googleapis.com/token")
    monkeypatch.setattr(FakeOAuthClient, "failure", httpx.ConnectError("offline", request=request))
    monkeypatch.setattr(oauth, "AsyncOAuth2Client", FakeOAuthClient)

    with pytest.raises(AuthProblem, match="Google sign-in unavailable"):
        await GoogleOIDCAdapter(oauth_settings()).exchange(
            code="authorization-code",
            code_verifier="verifier",
            nonce="nonce-value",
            redirect_uri="https://app.example/api/v1/auth/google/callback",
        )
