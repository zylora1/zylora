from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.commerce.payments import PaymentService, VerifiedSubscriptionPayment
from zylora_api.modules.commerce.publishing import WebsiteRequirements, _plan_reasons


class SequenceSession:
    def __init__(self, values: list[object | None]) -> None:
        self.values = values

    async def scalar(self, _: object) -> object | None:
        return self.values.pop(0)

    async def get_one(self, _: object, __: object) -> object:
        return "existing-subscription"


def verified(**changes: object) -> VerifiedSubscriptionPayment:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "provider": "TEST",
        "provider_event_id": f"event-{uuid4().hex}",
        "provider_payment_reference": f"reference-{uuid4().hex}",
        "payment_id": uuid4(),
        "amount_minor": 900,
        "currency": "USD",
        "period_start": now,
        "period_end": now + timedelta(days=30),
        "raw_body_hash": "a" * 64,
        "evidence": {"verified": 1},
    }
    values.update(changes)
    return VerifiedSubscriptionPayment(**values)  # type: ignore[arg-type]


def payment() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        expected_amount_minor=900,
        expected_currency="USD",
        state="CREATED",
        purpose="SUBSCRIPTION",
        plan_id=uuid4(),
        price_id=uuid4(),
    )


async def test_payment_verification_fails_closed_for_invalid_evidence() -> None:
    with pytest.raises(AuthProblem) as missing:
        await PaymentService(SequenceSession([None])).process_subscription_payment(verified())  # type: ignore[arg-type]
    assert missing.value.code == "payment_not_found"

    captured = payment()
    with pytest.raises(AuthProblem) as duplicate:
        await PaymentService(
            SequenceSession([captured, SimpleNamespace(payment_id=captured.id), None])
        ).process_subscription_payment(  # type: ignore[arg-type]
            verified(payment_id=captured.id)
        )
    assert duplicate.value.code == "payment_reconciliation_required"

    for replacement, code in [
        ({"amount_minor": 901}, "payment_amount_mismatch"),
        ({"currency": "INR"}, "payment_currency_mismatch"),
        (
            {
                "period_end": datetime.now(UTC),
                "period_start": datetime.now(UTC) + timedelta(days=1),
            },
            "payment_period_invalid",
        ),
    ]:
        candidate = payment()
        with pytest.raises(AuthProblem) as rejected:
            await PaymentService(SequenceSession([candidate, None])).process_subscription_payment(  # type: ignore[arg-type]
                verified(payment_id=candidate.id, **replacement)
            )
        assert rejected.value.code == code


async def test_captured_payment_replay_returns_the_existing_subscription() -> None:
    captured = payment()
    captured.state = "CAPTURED"
    result = await PaymentService(
        SequenceSession([captured, None, SimpleNamespace(subscription_id=uuid4())])  # type: ignore[arg-type]
    ).process_subscription_payment(verified(payment_id=captured.id))
    assert result == "existing-subscription"


def test_publish_reasons_enforce_page_domain_and_publish_capabilities() -> None:
    reasons = _plan_reasons(
        {"can_publish": False, "max_pages": 1, "custom_domain": False},
        WebsiteRequirements(page_count=2, domain_type="CUSTOM"),
    )
    assert [reason.code for reason in reasons] == [
        "PUBLISHING_NOT_INCLUDED",
        "PAGE_LIMIT_EXCEEDED",
        "CUSTOM_DOMAIN_NOT_INCLUDED",
    ]
