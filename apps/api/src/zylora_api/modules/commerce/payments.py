from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.commerce_models import (
    ExportPurchase,
    Invoice,
    Payment,
    PaymentEvent,
    Plan,
    PlanCatalog,
    PlanEntitlement,
    PlanPrice,
    Subscription,
)
from zylora_api.db.models import OutboxEvent
from zylora_api.modules.commerce.service import entitlement_value, snapshot_entitlements
from zylora_api.modules.templates.service import problem


@dataclass(frozen=True)
class VerifiedSubscriptionPayment:
    provider: str
    provider_event_id: str
    provider_payment_reference: str
    payment_id: UUID
    amount_minor: int
    currency: str
    period_start: datetime
    period_end: datetime
    raw_body_hash: str
    evidence: dict[str, str | int]


@dataclass(frozen=True)
class VerifiedExportPayment:
    provider: str
    provider_event_id: str
    provider_payment_reference: str
    payment_id: UUID
    amount_minor: int
    currency: str
    raw_body_hash: str
    evidence: dict[str, str | int]


class DeterministicPaymentAdapter:
    """Test-only verifier; production cannot configure this adapter."""

    def __init__(self, *, environment: str, secret: str) -> None:
        if environment != "test":
            raise RuntimeError("The deterministic payment adapter is test-only.")
        self.secret = secret.encode()

    def verify(self, raw_body: bytes, signature: str) -> VerifiedSubscriptionPayment:
        expected = hmac.new(self.secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise problem(401, "invalid_payment_signature", "Payment verification failed.")
        payload = json.loads(raw_body)
        return VerifiedSubscriptionPayment(
            provider="TEST",
            provider_event_id=str(payload["event_id"]),
            provider_payment_reference=str(payload["provider_payment_id"]),
            payment_id=UUID(str(payload["payment_id"])),
            amount_minor=int(payload["amount_minor"]),
            currency=str(payload["currency"]),
            period_start=datetime.fromisoformat(str(payload["period_start"])),
            period_end=datetime.fromisoformat(str(payload["period_end"])),
            raw_body_hash=hashlib.sha256(raw_body).hexdigest(),
            evidence={"event_id": str(payload["event_id"])},
        )


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_subscription_payment(
        self, verified: VerifiedSubscriptionPayment
    ) -> Subscription:
        payment = await self.session.scalar(
            select(Payment).where(Payment.id == verified.payment_id).with_for_update()
        )
        if not payment:
            raise problem(404, "payment_not_found", "Payment not found.")
        if payment.purpose != "SUBSCRIPTION" or not payment.plan_id or not payment.price_id:
            raise problem(409, "payment_purpose_invalid", "Payment purpose verification failed.")
        duplicate = await self.session.scalar(
            select(PaymentEvent).where(
                PaymentEvent.provider == verified.provider,
                PaymentEvent.provider_event_id == verified.provider_event_id,
            )
        )
        if duplicate:
            if duplicate.payment_id != payment.id:
                raise problem(409, "payment_event_replay_mismatch", "Payment verification failed.")
            invoice = await self.session.scalar(
                select(Invoice).where(Invoice.payment_id == payment.id)
            )
            if not invoice:
                raise problem(
                    409, "payment_reconciliation_required", "Payment needs reconciliation."
                )
            return await self.session.get_one(Subscription, invoice.subscription_id)
        if verified.amount_minor != payment.expected_amount_minor:
            raise problem(409, "payment_amount_mismatch", "Payment amount verification failed.")
        if verified.currency != payment.expected_currency:
            raise problem(409, "payment_currency_mismatch", "Payment currency verification failed.")
        if verified.period_end <= verified.period_start:
            raise problem(409, "payment_period_invalid", "Payment period verification failed.")
        if payment.state in {"CAPTURED", "SETTLED"}:
            invoice = await self.session.scalar(
                select(Invoice).where(Invoice.payment_id == payment.id)
            )
            if invoice:
                return await self.session.get_one(Subscription, invoice.subscription_id)
        plan, price, catalog = (
            await self.session.execute(
                select(Plan, PlanPrice, PlanCatalog)
                .select_from(Plan)
                .join(PlanPrice, PlanPrice.id == payment.price_id)
                .join(PlanCatalog, PlanCatalog.id == Plan.catalog_id)
                .where(Plan.id == payment.plan_id)
            )
        ).one()
        entitlement_rows = list(
            (
                await self.session.scalars(
                    select(PlanEntitlement).where(PlanEntitlement.plan_id == plan.id)
                )
            ).all()
        )
        entitlements = snapshot_entitlements(
            {item.capability_key: entitlement_value(item) for item in entitlement_rows}
        )
        current = await self.session.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == payment.user_id,
                Subscription.state.in_(
                    (
                        "PENDING",
                        "AUTHENTICATING",
                        "ACTIVE",
                        "RENEWAL_PENDING",
                        "PAST_DUE",
                        "CANCELLED",
                    )
                ),
            )
            .with_for_update()
        )
        if current:
            current.state = "EXPIRED"
            current.version += 1
            await self.session.flush()
        subscription = Subscription(
            user_id=payment.user_id,
            catalog_id=catalog.id,
            plan_id=plan.id,
            price_id=price.id,
            state="ACTIVE",
            plan_code_snapshot=plan.code,
            entitlements_snapshot=entitlements,
            amount_minor=payment.expected_amount_minor,
            currency=payment.expected_currency,
            interval="MONTHLY",
            current_period_start=verified.period_start,
            current_period_end=verified.period_end,
            provider_subscription_reference=f"{verified.provider}:{verified.provider_payment_reference}",
            last_trusted_payment_id=payment.id,
        )
        self.session.add(subscription)
        await self.session.flush()
        now = datetime.now(UTC)
        payment.provider = verified.provider
        payment.provider_payment_reference = verified.provider_payment_reference
        payment.state = "CAPTURED"
        payment.trusted_at = now
        self.session.add(
            PaymentEvent(
                payment_id=payment.id,
                provider=verified.provider,
                provider_event_id=verified.provider_event_id,
                event_type="SUBSCRIPTION_CAPTURED",
                raw_body_hash=verified.raw_body_hash,
                signature_verified=True,
                processing_outcome="APPLIED",
                evidence=verified.evidence,
            )
        )
        self.session.add(
            Invoice(
                number=f"ZYL-{str(payment.id).replace('-', '').upper()[:20]}",
                user_id=payment.user_id,
                subscription_id=subscription.id,
                payment_id=payment.id,
                line_items=[
                    {
                        "plan_code": plan.code,
                        "description": f"{plan.name} monthly subscription",
                        "amount_minor": payment.expected_amount_minor,
                        "currency": payment.expected_currency,
                    }
                ],
                total_minor=payment.expected_amount_minor,
                currency=payment.expected_currency,
                state="PAID",
                issued_at=now,
                paid_at=now,
            )
        )
        return subscription

    async def process_export_payment(self, verified: VerifiedExportPayment) -> ExportPurchase:
        payment = await self.session.scalar(
            select(Payment).where(Payment.id == verified.payment_id).with_for_update()
        )
        if not payment:
            raise problem(404, "payment_not_found", "Payment not found.")
        if payment.purpose != "EXPORT" or not payment.export_purchase_id:
            raise problem(409, "payment_purpose_invalid", "Payment purpose verification failed.")
        duplicate = await self.session.scalar(
            select(PaymentEvent).where(
                PaymentEvent.provider == verified.provider,
                PaymentEvent.provider_event_id == verified.provider_event_id,
            )
        )
        if duplicate:
            if duplicate.payment_id != payment.id:
                raise problem(409, "payment_event_replay_mismatch", "Payment verification failed.")
            purchase = cast(
                ExportPurchase | None,
                await self.session.get(ExportPurchase, payment.export_purchase_id),
            )
            if not purchase:
                raise problem(
                    409, "payment_reconciliation_required", "Payment needs reconciliation."
                )
            return purchase
        if verified.amount_minor != payment.expected_amount_minor:
            raise problem(409, "payment_amount_mismatch", "Payment amount verification failed.")
        if verified.currency != payment.expected_currency:
            raise problem(409, "payment_currency_mismatch", "Payment currency verification failed.")
        purchase = cast(
            ExportPurchase | None,
            await self.session.scalar(
                select(ExportPurchase)
                .where(ExportPurchase.id == payment.export_purchase_id)
                .with_for_update()
            ),
        )
        if not purchase or purchase.owner_user_id != payment.user_id:
            raise problem(409, "payment_reference_invalid", "Payment verification failed.")
        if (
            purchase.amount_minor != payment.expected_amount_minor
            or purchase.currency != payment.expected_currency
            or purchase.state not in {"PAYMENT_PENDING", "PAID", "GENERATING", "READY"}
        ):
            raise problem(409, "export_purchase_state_invalid", "Payment verification failed.")
        if payment.state in {"CAPTURED", "SETTLED"}:
            return purchase
        now = datetime.now(UTC)
        payment.provider = verified.provider
        payment.provider_payment_reference = verified.provider_payment_reference
        payment.state = "CAPTURED"
        payment.trusted_at = now
        self.session.add(
            PaymentEvent(
                payment_id=payment.id,
                provider=verified.provider,
                provider_event_id=verified.provider_event_id,
                event_type="EXPORT_CAPTURED",
                raw_body_hash=verified.raw_body_hash,
                signature_verified=True,
                processing_outcome="APPLIED",
                evidence=verified.evidence,
            )
        )
        purchase.paid_at = now
        if purchase.state in {"PAYMENT_PENDING", "PAID"}:
            purchase.state = "GENERATING"
            purchase.generation_requested_at = now
            self.session.add(
                OutboxEvent(
                    aggregate_type="EXPORT_PURCHASE",
                    aggregate_id=purchase.id,
                    event_type="export.generate_requested",
                    payload={"purchase_id": str(purchase.id)},
                    correlation_id=f"payment:{payment.id}",
                )
            )
        return purchase
