from __future__ import annotations

from typing import Any

import httpx
import pytest
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import AuditLog
from zylora_api.modules.auth.challenge import (
    ChallengeService,
    CloudflareTurnstileVerifier,
    TurnstileProviderUnavailable,
    TurnstileResponse,
)
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, model: object) -> None:
        self.added.append(model)

    async def commit(self) -> None:
        self.commits += 1


class FakeVerifier:
    def __init__(self, response: TurnstileResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    async def verify(self, **kwargs: str) -> TurnstileResponse:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def enabled_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        storage_provider="memory",
        turnstile_enabled=True,
        turnstile_site_key="site-key",
        turnstile_secret_key="secret-key",
        turnstile_allowed_hostnames="testserver",
    )


def service(verifier: FakeVerifier) -> tuple[ChallengeService, FakeSession]:
    settings = enabled_settings()
    session = FakeSession()
    return (
        ChallengeService(session, settings, AuthCrypto(settings.auth_secret), verifier),  # type: ignore[arg-type]
        session,
    )


async def test_valid_challenge_accepts_exact_action_and_hostname() -> None:
    verifier = FakeVerifier(TurnstileResponse(success=True, hostname="testserver", action="login"))
    challenge, session = service(verifier)

    decision = await challenge.enforce(
        "valid-token", expected_action="login", remote_ip="203.0.113.7", correlation_id="cid"
    )

    assert decision is not None and decision.hostname == "testserver"
    assert verifier.calls[0]["token"] == "valid-token"
    assert verifier.calls[0]["remote_ip"] == "203.0.113.7"
    assert len(verifier.calls[0]["idempotency_key"]) == 36
    assert session.commits == 0


async def test_official_test_secret_accepts_only_cloudflare_test_action() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        turnstile_enabled=True,
        turnstile_site_key="1x00000000000000000000AA",
        turnstile_secret_key="1x0000000000000000000000000000000AA",
        turnstile_allowed_hostnames="testserver",
    )
    session = FakeSession()
    verifier = FakeVerifier(TurnstileResponse(success=True, hostname="testserver", action="test"))
    challenge = ChallengeService(
        session,
        settings,
        AuthCrypto(settings.auth_secret),
        verifier,  # type: ignore[arg-type]
    )

    decision = await challenge.enforce(
        "test-token", expected_action="signup", remote_ip="203.0.113.7", correlation_id="cid"
    )

    assert decision is not None and decision.hostname == "testserver"
    assert session.commits == 0


async def test_official_test_secret_accepts_cloudflare_actionless_dummy_response() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        turnstile_enabled=True,
        turnstile_site_key="1x00000000000000000000AA",
        turnstile_secret_key="1x0000000000000000000000000000000AA",
        turnstile_allowed_hostnames="testserver",
    )
    session = FakeSession()
    verifier = FakeVerifier(TurnstileResponse(success=True, hostname="testserver"))
    challenge = ChallengeService(
        session,
        settings,
        AuthCrypto(settings.auth_secret),
        verifier,  # type: ignore[arg-type]
    )

    assert (
        await challenge.enforce(
            "test-token", expected_action="signup", remote_ip="203.0.113.7", correlation_id="cid"
        )
    ) is not None


async def test_official_test_secret_keeps_non_test_action_strict() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        turnstile_enabled=True,
        turnstile_site_key="1x00000000000000000000AA",
        turnstile_secret_key="1x0000000000000000000000000000000AA",
        turnstile_allowed_hostnames="testserver",
    )
    session = FakeSession()
    verifier = FakeVerifier(TurnstileResponse(success=True, hostname="testserver", action="login"))
    challenge = ChallengeService(
        session,
        settings,
        AuthCrypto(settings.auth_secret),
        verifier,  # type: ignore[arg-type]
    )

    with pytest.raises(AuthProblem) as caught:
        await challenge.enforce(
            "test-token", expected_action="signup", remote_ip="203.0.113.7", correlation_id="cid"
        )

    assert caught.value.code == "challenge_failed"
    audit = next(model for model in session.added if isinstance(model, AuditLog))
    assert audit.reason == "action_mismatch"


@pytest.mark.parametrize(
    ("response", "expected_code", "expected_reason"),
    [
        (None, "challenge_required", "missing"),
        (
            TurnstileResponse(success=False, **{"error-codes": ["invalid-input-response"]}),
            "challenge_failed",
            "invalid",
        ),
        (
            TurnstileResponse(success=False, **{"error-codes": ["timeout-or-duplicate"]}),
            "challenge_failed",
            "expired_or_replayed",
        ),
        (
            TurnstileResponse(success=True, hostname="evil.example", action="login"),
            "challenge_failed",
            "hostname_mismatch",
        ),
        (
            TurnstileResponse(success=True, hostname="testserver", action="signup"),
            "challenge_failed",
            "action_mismatch",
        ),
        (TurnstileProviderUnavailable(), "challenge_unavailable", "provider_unavailable"),
    ],
)
async def test_challenge_failures_are_closed_and_safely_audited(
    response: TurnstileResponse | Exception | None,
    expected_code: str,
    expected_reason: str,
) -> None:
    verifier = FakeVerifier(response or TurnstileResponse(success=True))
    challenge, session = service(verifier)

    with pytest.raises(AuthProblem) as caught:
        await challenge.enforce(
            None if response is None else "sensitive-token",
            expected_action="login",
            remote_ip="203.0.113.7",
            correlation_id="cid",
        )

    assert caught.value.code == expected_code
    assert session.commits == 1
    audit = next(model for model in session.added if isinstance(model, AuditLog))
    assert audit.reason == expected_reason
    assert audit.metadata_json == {"action": "login"}
    assert "sensitive-token" not in repr(audit)
    assert verifier.calls == [] if response is None else verifier.calls


async def test_disabled_challenge_never_calls_provider() -> None:
    settings = Settings(_env_file=None, environment="test", storage_provider="memory")
    verifier = FakeVerifier(TurnstileProviderUnavailable())
    session = FakeSession()
    challenge = ChallengeService(
        session,
        settings,
        AuthCrypto(settings.auth_secret),
        verifier,  # type: ignore[arg-type]
    )
    assert (
        await challenge.enforce(
            None, expected_action="login", remote_ip="127.0.0.1", correlation_id="cid"
        )
        is None
    )
    assert verifier.calls == []


async def test_provider_sends_only_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"success": True, "hostname": "testserver", "action": "login"}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured["client"] = kwargs

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> FakeResponse:
            captured["url"] = url
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    result = await CloudflareTurnstileVerifier(enabled_settings()).verify(
        token="valid-token", remote_ip="203.0.113.7", idempotency_key="request-id"
    )

    assert result.success is True
    assert captured["url"] == CloudflareTurnstileVerifier.SITEVERIFY_URL
    assert captured["json"] == {
        "secret": "secret-key",
        "response": "valid-token",
        "remoteip": "203.0.113.7",
        "idempotency_key": "request-id",
    }


async def test_provider_transport_failure_is_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> BrokenClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("provider down")

    monkeypatch.setattr(httpx, "AsyncClient", BrokenClient)
    with pytest.raises(TurnstileProviderUnavailable):
        await CloudflareTurnstileVerifier(enabled_settings()).verify(
            token="valid-token", remote_ip="203.0.113.7", idempotency_key="request-id"
        )
