from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from zylora_api.modules.analytics.activation import AttributionInput, ProductAnalyticsService
from zylora_api.modules.analytics.schemas import PublicWebsiteEventRequest
from zylora_api.modules.auth.errors import AuthProblem


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (AttributionInput(), "DIRECT"),
        (AttributionInput(referrer="https://www.google.com/search?q=zylora"), "GOOGLE_ORGANIC"),
        (AttributionInput(utm_source="instagram"), "INSTAGRAM"),
        (AttributionInput(utm_source="whatsapp"), "WHATSAPP_OUTREACH"),
        (AttributionInput(utm_source="linkedin"), "LINKEDIN"),
        (AttributionInput(utm_source="youtube"), "YOUTUBE"),
        (AttributionInput(utm_source="partner"), "PARTNER"),
        (AttributionInput(utm_source="freelancer"), "FREELANCER"),
        (AttributionInput(utm_medium="organic", referrer="https://example.com"), "OTHER_ORGANIC"),
        (AttributionInput(utm_source="newsletter"), "OTHER"),
    ],
)
def test_normalize_source_is_deterministic(value: AttributionInput, expected: str) -> None:
    assert ProductAnalyticsService.normalize_source(value) == expected


def test_privacy_helpers_default_unknown_country_and_compute_changes() -> None:
    assert ProductAnalyticsService._country(None) == "ZZ"
    assert ProductAnalyticsService._country("india") == "ZZ"
    assert ProductAnalyticsService._country("in") == "IN"
    assert ProductAnalyticsService._bounded("  campaign  ", 5) == "campa"
    assert ProductAnalyticsService._change(0, 0) is None
    assert ProductAnalyticsService._change(4, 0) == 100.0
    assert ProductAnalyticsService._change(15, 10) == 50.0


@pytest.mark.asyncio
async def test_product_event_validation_rejects_unknown_sensitive_and_oversized_data() -> None:
    service = ProductAnalyticsService(AsyncMock())
    with pytest.raises(AuthProblem, match="event type"):
        await service.record_event(event_type="UNKNOWN", idempotency_key="valid-event-key-0001")
    with pytest.raises(AuthProblem, match="identifier"):
        await service.record_event(event_type="ACCOUNT_CREATED", idempotency_key="short")
    with pytest.raises(AuthProblem, match="properties"):
        await service.record_event(
            event_type="ACCOUNT_CREATED",
            idempotency_key="valid-event-key-0002",
            properties={"email": "private@example.com"},
        )
    with pytest.raises(AuthProblem, match="properties"):
        await service.record_event(
            event_type="ACCOUNT_CREATED",
            idempotency_key="valid-event-key-0003",
            properties={"safe": "x" * 5000},
        )


def test_public_product_event_contract_allows_only_form_open_without_content() -> None:
    accepted = PublicWebsiteEventRequest(
        event_id="event-identifier-0001",
        event_type="LEAD_FORM_OPENED",
        session_id="session-identifier-01",
        page_path="/services",
    )
    assert accepted.event_type == "LEAD_FORM_OPENED"
    with pytest.raises(ValidationError):
        PublicWebsiteEventRequest(
            event_id="event-identifier-0002",
            event_type="CHATBOT_MESSAGE",
            session_id="session-identifier-02",
            page_path="/",
        )
    with pytest.raises(ValidationError):
        PublicWebsiteEventRequest(
            event_id="event-identifier-0003",
            event_type="LEAD_FORM_OPENED",
            session_id="session-identifier-03",
            page_path="https://evil.example/",
        )


def test_attribution_model_has_no_precise_location_or_pii_fields() -> None:
    fields = set(AttributionInput.__dataclass_fields__)
    assert fields == {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "referrer",
        "landing_page",
    }
    assert {"email", "phone", "ip_address", "latitude", "longitude"}.isdisjoint(fields)
    assert uuid4()


@pytest.mark.asyncio
async def test_first_value_event_keys_remain_website_scoped_across_owner_projection_resets() -> (
    None
):
    website_id = uuid4()
    owner_id = uuid4()
    published_at = datetime(2026, 1, 1, tzinfo=UTC)
    state = SimpleNamespace(
        owner_user_id=owner_id,
        published_at=published_at,
        first_visitor_at=None,
        first_lead_at=None,
    )
    website = SimpleNamespace(id=website_id, owner_user_id=owner_id)
    lead = SimpleNamespace(
        id=uuid4(),
        website_id=website_id,
        owner_user_id=owner_id,
        captured_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    session = AsyncMock()
    session.scalar.return_value = website
    service = ProductAnalyticsService(session)
    service._value_state = AsyncMock(return_value=state)  # type: ignore[method-assign]
    service.record_event = AsyncMock(return_value=(SimpleNamespace(), False))  # type: ignore[method-assign]

    assert await service.mark_first_visitor(website, lead.captured_at) is True  # type: ignore[arg-type]
    assert await service.mark_lead_created(lead) is True  # type: ignore[arg-type]

    event_calls = service.record_event.await_args_list
    first_visitor = next(
        call for call in event_calls if call.kwargs["event_type"] == "FIRST_VISITOR"
    )
    first_lead = next(call for call in event_calls if call.kwargs["event_type"] == "FIRST_LEAD")
    assert first_visitor.kwargs["idempotency_key"] == f"first-visitor:{website_id}"
    assert first_lead.kwargs["idempotency_key"] == f"first-lead:{website_id}"
