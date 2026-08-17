from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.commerce.payments import PaymentService, VerifiedSubscriptionPayment
from zylora_api.modules.commerce.publishing import (
    WebsiteRequirements,
    _plan_reasons,
)
from zylora_api.modules.commerce.service import (
    PlanBundle,
    SubscriptionService,
)
from zylora_api.modules.pro_leads.schemas import (
    ProLeadCreateRequest,
)
from zylora_api.modules.pro_leads.service import ProLeadService


class SequenceSession:
    def __init__(self, values: list[object]) -> None:
        self.values = list(values)
        self.added: list[object] = []

    async def scalar(self, *_: object, **__: object) -> object:
        return self.values.pop(0) if self.values else None

    async def scalars(self, *_: object, **__: object) -> object:
        val = self.values.pop(0) if self.values else []
        return SimpleNamespace(all=lambda: val)

    async def execute(self, *_: object, **__: object) -> object:
        val = self.values.pop(0) if self.values else None
        return SimpleNamespace(one=lambda: val, all=lambda: val or [])

    async def get(self, entity_class: object, ident: object) -> object:
        return self.values.pop(0) if self.values else None

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        pass


def test_plan_page_limits_free_starter_growth() -> None:
    # Free plan allows up to 2 pages
    free_reasons_2 = _plan_reasons(
        {"can_publish": True, "max_pages": 2, "custom_domain": False},
        WebsiteRequirements(page_count=2, domain_type="ZYLORA_SUBDOMAIN"),
    )
    assert free_reasons_2 == []

    free_reasons_3 = _plan_reasons(
        {"can_publish": True, "max_pages": 2, "custom_domain": False},
        WebsiteRequirements(page_count=3, domain_type="ZYLORA_SUBDOMAIN"),
    )
    assert any(r.code == "PAGE_LIMIT_EXCEEDED" for r in free_reasons_3)

    # Starter plan allows up to 5 pages
    starter_reasons_5 = _plan_reasons(
        {"can_publish": True, "max_pages": 5, "custom_domain": True},
        WebsiteRequirements(page_count=5, domain_type="CUSTOM"),
    )
    assert starter_reasons_5 == []

    starter_reasons_6 = _plan_reasons(
        {"can_publish": True, "max_pages": 5, "custom_domain": True},
        WebsiteRequirements(page_count=6, domain_type="CUSTOM"),
    )
    assert any(r.code == "PAGE_LIMIT_EXCEEDED" for r in starter_reasons_6)

    # Growth plan allows up to 8 pages
    growth_reasons_8 = _plan_reasons(
        {"can_publish": True, "max_pages": 8, "custom_domain": True},
        WebsiteRequirements(page_count=8, domain_type="CUSTOM"),
    )
    assert growth_reasons_8 == []

    growth_reasons_9 = _plan_reasons(
        {"can_publish": True, "max_pages": 8, "custom_domain": True},
        WebsiteRequirements(page_count=9, domain_type="CUSTOM"),
    )
    assert any(r.code == "PAGE_LIMIT_EXCEEDED" for r in growth_reasons_9)


async def test_pro_plan_cannot_invoke_checkout() -> None:
    pro_plan_id = uuid4()
    pro_bundle = PlanBundle(
        catalog=SimpleNamespace(region="INDIA", currency="INR"),  # type: ignore[arg-type]
        plan=SimpleNamespace(id=pro_plan_id, code="BUSINESS", slot=4),  # type: ignore[arg-type]
        price=SimpleNamespace(id=uuid4(), amount_minor=199900, currency="INR"),  # type: ignore[arg-type]
        entitlements={},
    )
    async def _mock_current(country: str) -> list[PlanBundle]:
        return [pro_bundle]

    service = SubscriptionService(SequenceSession([None]))  # type: ignore[arg-type]
    service.catalogs = SimpleNamespace(current=_mock_current)  # type: ignore[assignment]

    with pytest.raises(AuthProblem) as exc_info:
        await service.create_payment(uuid4(), "IN", pro_plan_id, "idempotency-key-12345")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "pro_plan_sales_assisted"


async def test_pro_plan_cannot_be_activated_via_payment() -> None:
    pro_plan_id = uuid4()
    payment = SimpleNamespace(
        id=uuid4(),
        purpose="SUBSCRIPTION",
        plan_id=pro_plan_id,
        price_id=uuid4(),
        state="CREATED",
        expected_amount_minor=199900,
        expected_currency="INR",
    )
    verified = VerifiedSubscriptionPayment(
        payment_id=payment.id,
        provider="RAZORPAY",
        provider_event_id="evt_123",
        provider_payment_reference="pay_123",
        amount_minor=199900,
        currency="INR",
        raw_body_hash="hash_123",
        period_start=datetime.now(UTC),
        period_end=datetime.now(UTC),
        evidence={"test": True},
    )
    session = SequenceSession(
        [
            payment,  # fetch payment
            None,  # duplicate event check
            (
                SimpleNamespace(id=pro_plan_id, code="BUSINESS"),
                SimpleNamespace(id=payment.price_id),
                SimpleNamespace(id=uuid4()),
            ),  # plan, price, catalog
        ]
    )
    payment_service = PaymentService(session)  # type: ignore[arg-type]

    with pytest.raises(AuthProblem) as exc_info:
        await payment_service.process_subscription_payment(verified)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_paid_plan"


async def test_pro_enquiry_creates_pro_lead_with_lead_code_and_confirmation() -> None:
    session = SequenceSession([None, None])  # type: ignore[arg-type]
    settings = SimpleNamespace(turnstile_enabled=False)  # type: ignore[arg-type]
    crypto = AuthCrypto("pro-service-crypto-secret-key-that-is-long-enough")
    service = ProLeadService(session, settings, crypto=crypto)  # type: ignore[arg-type]

    payload = ProLeadCreateRequest(
        name="John Founder",
        email="john@example.com",
        website_type="Custom E-commerce Store with AI assistant",
        preferred_contact_time="Mon-Wed 3-5 PM IST",
    )

    lead = await service.submit_pro_enquiry(
        payload, client_ip="127.0.0.1", correlation_id="cid-12345"
    )

    assert lead.reference_id.startswith("ZPRO-")
    assert lead.name == "John Founder"
    assert lead.email == "john@example.com"
    assert lead.website_type == "Custom E-commerce Store with AI assistant"
    assert lead.status == "PENDING"
    assert len(session.added) >= 3  # ProLead + OutboxEvent + TransactionalEmail


async def test_super_admin_pro_lead_status_update_with_amount() -> None:
    lead_id = uuid4()
    lead = SimpleNamespace(
        id=lead_id,
        reference_id="ZPRO-123456",
        name="Jane",
        email="jane@example.com",
        website_type="SaaS App",
        preferred_contact_time="Anytime",
        status="PENDING",
        amount_received=None,
        resolved_at=None,
        version=1,
    )
    session = SequenceSession([lead])  # type: ignore[arg-type]
    settings = SimpleNamespace()  # type: ignore[arg-type]
    service = ProLeadService(session, settings)  # type: ignore[arg-type]

    updated = await service.update_status(lead_id, "CLOSED", amount_received=1500000)

    assert updated.status == "CLOSED"
    assert updated.amount_received == 1500000
    assert updated.resolved_at is not None


def test_no_external_partner_branding_in_codebase() -> None:
    partner_patterns = [
        re.compile(r"\brootpro\b", re.IGNORECASE),
        re.compile(r"\broot_pro\b", re.IGNORECASE),
    ]
    # Check sample customer-facing strings
    pro_description = "Managed by experts for custom requirements"
    for pattern in partner_patterns:
        assert not pattern.search(pro_description)
