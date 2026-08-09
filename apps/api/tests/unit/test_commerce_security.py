from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.commerce.payments import DeterministicPaymentAdapter
from zylora_api.modules.commerce.service import calendar_period, region_for_country


def payload() -> bytes:
    now = datetime.now(UTC)
    return json.dumps(
        {
            "event_id": f"event-{uuid4().hex}",
            "provider_payment_id": f"provider-{uuid4().hex}",
            "payment_id": str(uuid4()),
            "amount_minor": 99900,
            "currency": "INR",
            "period_start": now.isoformat(),
            "period_end": (now + timedelta(days=30)).isoformat(),
        },
        separators=(",", ":"),
    ).encode()


def test_deterministic_verifier_is_test_only_and_rejects_untrusted_payloads() -> None:
    with pytest.raises(RuntimeError, match="test-only"):
        DeterministicPaymentAdapter(environment="production", secret="not-a-production-secret")
    adapter = DeterministicPaymentAdapter(environment="test", secret="phase7-secret")
    body = payload()
    with pytest.raises(AuthProblem) as rejected:
        adapter.verify(body, "forged-signature")
    assert rejected.value.code == "invalid_payment_signature"
    signature = hmac.new(b"phase7-secret", body, hashlib.sha256).hexdigest()
    verified = adapter.verify(body, signature)
    assert verified.amount_minor == 99900
    assert verified.currency == "INR"
    assert verified.raw_body_hash == hashlib.sha256(body).hexdigest()


def test_region_and_free_period_are_server_deterministic() -> None:
    assert region_for_country("IN") == "INDIA"
    assert region_for_country("US") == "INTERNATIONAL"
    start, end = calendar_period(datetime(2026, 12, 15, tzinfo=UTC))
    assert start == datetime(2026, 12, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)
