from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.commerce_models import (
    Payment,
    Plan,
    PlanCatalog,
    PlanEntitlement,
    PlanPrice,
    Subscription,
)
from zylora_api.modules.commerce.schemas import (
    CancelSubscriptionResponse,
    MoneyResponse,
    PlanListResponse,
    PlanResponse,
    SubscriptionResponse,
)
from zylora_api.modules.templates.service import problem

PLAN_CODES = ("FREE", "BASIC", "GROWTH", "BUSINESS")
REQUIRED_CAPABILITIES = frozenset(
    {
        "can_publish",
        "zylora_subdomain",
        "custom_domain",
        "remove_branding",
        "lead_capture_unlimited",
        "max_pages",
        "ai_monthly_credits",
        "whatsapp_monthly_notifications",
        "analytics_tier",
        "seo_tier",
    }
)
GRANTING_STATES = ("ACTIVE", "RENEWAL_PENDING", "PAST_DUE", "CANCELLED")


def region_for_country(country_code: str) -> str:
    return "INDIA" if country_code == "IN" else "INTERNATIONAL"


def entitlement_value(item: PlanEntitlement) -> bool | int | str:
    if item.value_type == "BOOLEAN" and item.value_bool is not None:
        return item.value_bool
    if item.value_type == "INTEGER" and item.value_int is not None:
        return item.value_int
    if item.value_type in {"ENUM", "UNLIMITED"} and item.value_text is not None:
        return item.value_text
    raise problem(500, "invalid_plan_catalog", "The active plan catalog is invalid.")


def calendar_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    start = datetime(current.year, current.month, 1, tzinfo=UTC)
    if current.month == 12:
        end = datetime(current.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(current.year, current.month + 1, 1, tzinfo=UTC)
    return start, end


@dataclass(frozen=True)
class PlanBundle:
    catalog: PlanCatalog
    plan: Plan
    price: PlanPrice
    entitlements: dict[str, bool | int | str]

    def response(self) -> PlanResponse:
        return PlanResponse(
            id=self.plan.id,
            code=self.plan.code,
            name=self.plan.name,
            description=self.plan.description,
            slot=self.plan.slot,
            most_popular=self.plan.most_popular,
            price=MoneyResponse(
                amount_minor=self.price.amount_minor,
                currency=self.price.currency,
            ),
            interval="MONTHLY",
            entitlements=self.entitlements,
        )


@dataclass(frozen=True)
class EffectivePlan:
    bundle: PlanBundle
    entitlements: dict[str, bool | int | str]
    period_start: datetime
    period_end: datetime
    subscription: Subscription | None


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current(self, country_code: str) -> list[PlanBundle]:
        region = region_for_country(country_code)
        catalog = await self.session.scalar(
            select(PlanCatalog).where(
                PlanCatalog.region == region,
                PlanCatalog.interval == "MONTHLY",
                PlanCatalog.status == "PUBLISHED",
                PlanCatalog.effective_at <= datetime.now(UTC),
            )
        )
        if not catalog:
            raise problem(503, "plan_catalog_unavailable", "Plans are temporarily unavailable.")
        plan_rows = (
            await self.session.execute(
                select(Plan, PlanPrice)
                .join(PlanPrice, PlanPrice.plan_id == Plan.id)
                .where(
                    Plan.catalog_id == catalog.id,
                    Plan.visible.is_(True),
                    PlanPrice.active.is_(True),
                    PlanPrice.interval == "MONTHLY",
                    PlanPrice.currency == catalog.currency,
                )
                .order_by(Plan.slot)
            )
        ).all()
        entitlements = list(
            (
                await self.session.scalars(
                    select(PlanEntitlement).where(
                        PlanEntitlement.plan_id.in_([plan.id for plan, _ in plan_rows])
                    )
                )
            ).all()
        )
        grouped: dict[UUID, dict[str, bool | int | str]] = {}
        for item in entitlements:
            grouped.setdefault(item.plan_id, {})[item.capability_key] = entitlement_value(item)
        bundles = [
            PlanBundle(catalog, plan, price, grouped.get(plan.id, {})) for plan, price in plan_rows
        ]
        self._validate(bundles)
        return bundles

    @staticmethod
    def _validate(bundles: list[PlanBundle]) -> None:
        codes = tuple(item.plan.code for item in bundles)
        slots = tuple(item.plan.slot for item in bundles)
        if codes != PLAN_CODES or slots != (1, 2, 3, 4):
            raise problem(500, "invalid_plan_catalog", "The active plan catalog is invalid.")
        for item in bundles:
            if set(item.entitlements) != REQUIRED_CAPABILITIES:
                raise problem(500, "invalid_plan_catalog", "The active plan catalog is invalid.")
        popular = [item.plan.code for item in bundles if item.plan.most_popular]
        if popular != ["GROWTH"]:
            raise problem(500, "invalid_plan_catalog", "The active plan catalog is invalid.")

    async def response(self, country_code: str) -> PlanListResponse:
        bundles = await self.current(country_code)
        return PlanListResponse(
            region=bundles[0].catalog.region,
            country_code=country_code,
            currency=bundles[0].catalog.currency,
            interval="MONTHLY",
            items=[item.response() for item in bundles],
        )


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.catalogs = CatalogService(session)

    async def effective(
        self, user_id: UUID, country_code: str, *, for_update: bool = False
    ) -> EffectivePlan:
        statement = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.state.in_(GRANTING_STATES),
                Subscription.current_period_end > datetime.now(UTC),
            )
            .order_by(Subscription.created_at.desc())
        )
        if for_update:
            statement = statement.with_for_update()
        subscription = await self.session.scalar(statement)
        if subscription:
            plan, price, catalog = (
                await self.session.execute(
                    select(Plan, PlanPrice, PlanCatalog)
                    .select_from(Plan)
                    .join(PlanPrice, PlanPrice.id == subscription.price_id)
                    .join(PlanCatalog, PlanCatalog.id == subscription.catalog_id)
                    .where(Plan.id == subscription.plan_id)
                )
            ).one()
            bundle = PlanBundle(catalog, plan, price, subscription.entitlements_snapshot)
            return EffectivePlan(
                bundle=bundle,
                entitlements=subscription.entitlements_snapshot,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end,
                subscription=subscription,
            )
        free = (await self.catalogs.current(country_code))[0]
        start, end = calendar_period()
        return EffectivePlan(free, free.entitlements, start, end, None)

    async def response(self, user_id: UUID, country_code: str) -> SubscriptionResponse:
        effective = await self.effective(user_id, country_code)
        return SubscriptionResponse(
            plan_code=effective.bundle.plan.code,
            state=effective.subscription.state if effective.subscription else "ACTIVE",
            is_paid=effective.bundle.price.amount_minor > 0,
            price=MoneyResponse(
                amount_minor=effective.bundle.price.amount_minor,
                currency=effective.bundle.price.currency,
            ),
            interval="MONTHLY",
            current_period_start=effective.period_start,
            current_period_end=effective.period_end,
            cancel_at_period_end=(
                effective.subscription.cancel_at_period_end if effective.subscription else False
            ),
            entitlements=effective.entitlements,
        )

    async def cancel(self, user_id: UUID, country_code: str) -> CancelSubscriptionResponse:
        effective = await self.effective(user_id, country_code, for_update=True)
        subscription = effective.subscription
        if not subscription:
            raise problem(409, "free_plan_cannot_cancel", "The Free plan has no paid renewal.")
        subscription.cancel_at_period_end = True
        subscription.state = "CANCELLED"
        subscription.version += 1
        return CancelSubscriptionResponse(
            plan_code=subscription.plan_code_snapshot,
            state=subscription.state,
            cancel_at_period_end=True,
            current_period_end=subscription.current_period_end,
            message=(
                "Your plan remains active until the current period ends. "
                "Website content is preserved."
            ),
        )

    async def create_payment(
        self,
        user_id: UUID,
        country_code: str,
        plan_id: UUID,
        idempotency_key: str,
    ) -> Payment:
        existing = await self.session.scalar(
            select(Payment).where(
                Payment.user_id == user_id,
                Payment.idempotency_key == idempotency_key,
            )
        )
        if existing:
            if existing.plan_id != plan_id:
                raise problem(
                    409,
                    "idempotency_key_reused",
                    "This idempotency key was already used for another plan.",
                )
            return existing
        bundles = await self.catalogs.current(country_code)
        bundle = next((item for item in bundles if item.plan.id == plan_id), None)
        if not bundle:
            raise problem(404, "plan_not_found", "Plan not found for your billing region.")
        if bundle.plan.code == "FREE":
            raise problem(409, "free_plan_requires_no_payment", "The Free plan needs no checkout.")
        payment = Payment(
            user_id=user_id,
            plan_id=bundle.plan.id,
            price_id=bundle.price.id,
            purpose="SUBSCRIPTION",
            state="CREATED",
            expected_amount_minor=bundle.price.amount_minor,
            expected_currency=bundle.price.currency,
            provider="UNSELECTED",
            idempotency_key=idempotency_key,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment


def snapshot_entitlements(entitlements: dict[str, Any]) -> dict[str, bool | int | str]:
    result: dict[str, bool | int | str] = {}
    for key, value in entitlements.items():
        if not isinstance(value, (bool, int, str)):
            raise problem(500, "invalid_plan_catalog", "The active plan catalog is invalid.")
        result[key] = value
    return result
