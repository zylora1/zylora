from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from starlette.requests import Request
from zylora_api.api.commerce import request_country, require_idempotency_key
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import User
from zylora_api.modules.auth.errors import AuthProblem


def request(country: str, query: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/plans",
            "query_string": query,
            "headers": [(b"cf-ipcountry", country.encode())],
            "client": ("127.0.0.1", 1),
        }
    )


def user(country: str = "ZZ") -> User:
    return User(
        id=uuid4(),
        account_type="USER",
        normalized_email=f"phase7-{uuid4().hex}@example.com",
        display_email="phase7@example.com",
        status="ACTIVE",
        verified_at=datetime.now(UTC),
        billing_country_code=country,
    )


def test_region_claims_are_ignored_without_trusted_edge_signal() -> None:
    settings = Settings(
        environment="test",
        storage_provider="memory",
        cloudflare_country_header_trusted=False,
        _env_file=None,
    )
    account = user()
    assert request_country(request("IN", b"region=india"), settings, account) == "ZZ"
    assert account.billing_country_code == "ZZ"


def test_trusted_country_is_persisted_and_cannot_override_existing_billing_country() -> None:
    settings = Settings(
        environment="test",
        storage_provider="memory",
        cloudflare_country_header_trusted=True,
        _env_file=None,
    )
    new_account = user()
    assert request_country(request("IN"), settings, new_account) == "IN"
    assert new_account.billing_country_code == "IN"
    established = user("US")
    assert request_country(request("IN"), settings, established) == "US"


def test_idempotency_key_is_required_and_bounded() -> None:
    assert require_idempotency_key("phase7-operation-0001") == "phase7-operation-0001"
    with pytest.raises(AuthProblem) as missing:
        require_idempotency_key(None)
    assert missing.value.code == "idempotency_key_required"
    with pytest.raises(AuthProblem):
        require_idempotency_key("short")
