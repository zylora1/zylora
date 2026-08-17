from __future__ import annotations

import pytest
from pydantic import ValidationError
from zylora_api.core.config import Settings
from zylora_api.modules.pro_leads.schemas import ProLeadCreateRequest
from zylora_api.modules.pro_leads.service import ProLeadService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pro_lead_free_text_website_type(async_session):
    settings = Settings()
    service = ProLeadService(async_session, settings)

    # 1. Valid free-text values
    req = ProLeadCreateRequest(
        name="Arun Kumar",
        email="arun@example.com",
        website_type="Clinic / healthcare website for dental practice",
        preferred_contact_time="Weekdays 5-7 PM",
    )
    lead = await service.submit_pro_enquiry(req, client_ip="127.0.0.1", correlation_id="c1")
    assert lead.reference_id.startswith("ZPRO-")
    assert lead.website_type == "Clinic / healthcare website for dental practice"
    assert lead.status == "PENDING"

    # 2. Empty / whitespace-only website_type -> validation error
    with pytest.raises(ValidationError):
        ProLeadCreateRequest(
            name="Arun Kumar",
            email="arun@example.com",
            website_type="   ",
            preferred_contact_time="Weekdays 5-7 PM",
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pro_lead_honeypot_rejection(async_session):
    settings = Settings()
    service = ProLeadService(async_session, settings)

    # Honeypot filled by bot
    req = ProLeadCreateRequest(
        name="Bot Spammer",
        email="bot@spam.com",
        website_type="Restaurant website",
        preferred_contact_time="Anytime",
        company_website_url="https://spam.example.com",  # Honeypot!
    )
    result = await service.submit_pro_enquiry(req, client_ip="192.168.1.100", correlation_id="c2")
    assert result.is_spam is True
    assert result.reference_id == "ZPRO-HONEYPOT"
    assert result.id == "00000000-0000-0000-0000-000000000000"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pro_lead_duplicate_suppression(async_session):
    settings = Settings()
    service = ProLeadService(async_session, settings)

    req = ProLeadCreateRequest(
        name="Priya Sharma",
        email="priya@example.com",
        website_type="Architecture portfolio",
        preferred_contact_time="Mornings 10 AM",
    )

    # First submission
    lead1 = await service.submit_pro_enquiry(req, client_ip="127.0.0.1", correlation_id="c3")
    ref1 = lead1.reference_id

    # Second submission (identical request within 24h)
    lead2 = await service.submit_pro_enquiry(req, client_ip="127.0.0.1", correlation_id="c4")
    ref2 = lead2.reference_id

    # Must return the existing reference ID without creating a duplicate
    assert ref1 == ref2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pro_lead_admin_status_transitions(async_session):
    settings = Settings()
    service = ProLeadService(async_session, settings)

    req = ProLeadCreateRequest(
        name="Vikram Seth",
        email="vikram@example.com",
        website_type="School website",
        preferred_contact_time="Evenings",
    )
    lead = await service.submit_pro_enquiry(req, client_ip="127.0.0.1", correlation_id="c5")
    assert lead.status == "PENDING"
    assert lead.amount_received is None

    # 1. Mark CLOSED with amount
    closed = await service.update_status(lead.id, "CLOSED", amount_received=126500)
    assert closed.status == "CLOSED"
    assert closed.amount_received == 126500
    assert closed.resolved_at is not None

    # Summary metric check
    summary = await service.get_summary()
    assert summary.total_pro_leads == 1
    assert summary.closed == 1
    assert summary.amount_received == 126500
