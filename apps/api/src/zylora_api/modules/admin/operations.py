from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from zylora_api.db.auth_models import AuditLog, AuthIdentity, User
from zylora_api.db.commerce_models import (
    ExportPrice,
    Invoice,
    Payment,
    Plan,
    PlanEntitlement,
    PlanPrice,
    Subscription,
)
from zylora_api.db.deployment_models import Domain
from zylora_api.db.lead_models import (
    AnalyticsDailyRollup,
    Lead,
    LeadCreditAccount,
    LeadCreditLedger,
    TransactionalEmail,
)
from zylora_api.db.template_models import Template
from zylora_api.db.website_models import AiCreditAccount, AiCreditLedger, Website
from zylora_api.modules.admin.schemas import (
    AdminMetric,
    AdminOperationListResponse,
    AdminOverviewResponse,
    AdminRecord,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserSummary,
)
from zylora_api.modules.leads.credits import LeadCreditPolicyService

AdminSection = Literal[
    "websites",
    "commerce",
    "leads-credits",
    "domains",
    "communications",
    "analytics",
    "audit",
    "configuration",
]


class AdminOperationsService:
    """Read-only, server-authoritative operational projections for the sole Super Admin."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(self) -> AdminOverviewResponse:
        window_start = date.today() - timedelta(days=29)
        users = await self._count(User, User.account_type == "USER")
        websites = await self._count(Website)
        drafts = await self._count(Website, Website.status == "DRAFT")
        live = await self._count(Website, Website.status == "PUBLISHED")
        templates = await self._count(Template)
        subscriptions = await self._count(Subscription, Subscription.state == "ACTIVE")
        payments = await self._count(Payment, Payment.state.in_(("CAPTURED", "SETTLED")))
        leads = await self._count(Lead)
        domains = await self._count(Domain, Domain.is_active.is_(True))
        page_views, measured_leads = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(AnalyticsDailyRollup.page_views), 0),
                    func.coalesce(func.sum(AnalyticsDailyRollup.leads), 0),
                ).where(AnalyticsDailyRollup.bucket_date >= window_start)
            )
        ).one()
        return AdminOverviewResponse(
            generated_at=datetime.now(UTC),
            metrics=[
                AdminMetric(key="users", label="Users", value=users),
                AdminMetric(key="websites", label="Websites", value=websites),
                AdminMetric(key="drafts", label="Drafts", value=drafts),
                AdminMetric(key="live", label="Live Websites", value=live),
                AdminMetric(key="templates", label="Templates", value=templates),
                AdminMetric(key="subscriptions", label="Active subscriptions", value=subscriptions),
                AdminMetric(key="payments", label="Trusted payments", value=payments),
                AdminMetric(key="leads", label="Captured Leads", value=leads),
                AdminMetric(key="domains", label="Active domains", value=domains),
            ],
            analytics_window_start=window_start,
            page_views_last_30_days=int(page_views),
            leads_last_30_days=int(measured_leads),
        )

    async def users(self, query: str | None, limit: int) -> AdminUserListResponse:
        statement = select(User).where(User.account_type == "USER")
        if query:
            statement = statement.where(User.display_email.ilike(f"%{query.strip()}%"))
        users = list(
            (
                await self.session.scalars(statement.order_by(User.created_at.desc()).limit(limit))
            ).all()
        )
        return AdminUserListResponse(items=[await self._user_summary(user) for user in users])

    async def user_detail(self, user_id: UUID) -> AdminUserDetail | None:
        user = await self.session.scalar(
            select(User).where(User.id == user_id, User.account_type == "USER")
        )
        if not user:
            return None
        summary = await self._user_summary(user)
        websites = list(
            (
                await self.session.scalars(
                    select(Website)
                    .where(Website.owner_user_id == user.id)
                    .order_by(Website.updated_at.desc())
                    .limit(100)
                )
            ).all()
        )
        subscriptions = list(
            (
                await self.session.scalars(
                    select(Subscription)
                    .where(Subscription.user_id == user.id)
                    .order_by(Subscription.updated_at.desc())
                    .limit(50)
                )
            ).all()
        )
        payments = list(
            (
                await self.session.scalars(
                    select(Payment)
                    .where(Payment.user_id == user.id)
                    .order_by(Payment.created_at.desc())
                    .limit(50)
                )
            ).all()
        )
        invoices = list(
            (
                await self.session.scalars(
                    select(Invoice)
                    .where(Invoice.user_id == user.id)
                    .order_by(Invoice.issued_at.desc())
                    .limit(50)
                )
            ).all()
        )
        lead_credit_account = await self.session.get(LeadCreditAccount, user.id)
        ai_credit_account = await self.session.get(AiCreditAccount, user.id)
        lead_ledger = list(
            (
                await self.session.scalars(
                    select(LeadCreditLedger)
                    .where(LeadCreditLedger.user_id == user.id)
                    .order_by(LeadCreditLedger.created_at.desc())
                    .limit(50)
                )
            ).all()
        )
        ai_ledger = list(
            (
                await self.session.scalars(
                    select(AiCreditLedger)
                    .where(AiCreditLedger.user_id == user.id)
                    .order_by(AiCreditLedger.created_at.desc())
                    .limit(50)
                )
            ).all()
        )
        leads = list(
            (
                await self.session.scalars(
                    select(Lead)
                    .where(Lead.owner_user_id == user.id)
                    .order_by(Lead.captured_at.desc())
                    .limit(50)
                )
            ).all()
        )
        domains = list(
            (
                await self.session.scalars(
                    select(Domain)
                    .where(Domain.owner_user_id == user.id)
                    .order_by(Domain.updated_at.desc())
                    .limit(50)
                )
            ).all()
        )
        audit = list(
            (
                await self.session.scalars(
                    select(AuditLog)
                    .where(
                        or_(
                            AuditLog.actor_user_id == user.id,
                            (AuditLog.target_type == "user") & (AuditLog.target_id == str(user.id)),
                        )
                    )
                    .order_by(AuditLog.occurred_at.desc())
                    .limit(100)
                )
            ).all()
        )
        credit_records: list[AdminRecord] = []
        if lead_credit_account:
            credit_records.append(
                AdminRecord(
                    id=lead_credit_account.id,
                    label="Lead credit account",
                    occurred_at=lead_credit_account.updated_at,
                    attributes={"balance": lead_credit_account.balance},
                )
            )
        if ai_credit_account:
            credit_records.append(
                AdminRecord(
                    id=ai_credit_account.user_id,
                    label="AI credit account",
                    occurred_at=ai_credit_account.updated_at,
                    attributes={
                        "balance": ai_credit_account.balance,
                        "allowance": ai_credit_account.allowance,
                    },
                )
            )
        credit_records.extend(
            [
                AdminRecord(
                    id=item.id,
                    label=item.entry_type,
                    detail=item.reason,
                    occurred_at=item.created_at,
                    attributes={"delta": item.delta, "resulting_balance": item.resulting_balance},
                )
                for item in lead_ledger
            ]
        )
        credit_records.extend(
            [
                AdminRecord(
                    id=item.id,
                    label=f"AI credit · {item.entry_type}",
                    detail=item.reason,
                    occurred_at=item.created_at,
                    attributes={"delta": item.delta, "resulting_balance": item.resulting_balance},
                )
                for item in ai_ledger
            ]
        )
        return AdminUserDetail(
            **summary.model_dump(),
            websites=[
                AdminRecord(
                    id=site.id,
                    label=site.display_name,
                    detail=f"Revision {site.revision}",
                    status=site.status,
                    occurred_at=site.updated_at,
                    attributes={"live": site.live_owner_user_id is not None},
                )
                for site in websites
            ],
            subscriptions=[
                AdminRecord(
                    id=item.id,
                    label=item.plan_code_snapshot,
                    detail=f"{item.amount_minor} {item.currency} / {item.interval}",
                    status=item.state,
                    occurred_at=item.updated_at,
                    attributes={"cancel_at_period_end": item.cancel_at_period_end},
                )
                for item in subscriptions
            ],
            payments=[
                *[
                    AdminRecord(
                        id=item.id,
                        label=item.purpose,
                        detail=f"{item.expected_amount_minor} {item.expected_currency}",
                        status=item.state,
                        occurred_at=item.created_at,
                        attributes={"trusted": item.trusted_at is not None},
                    )
                    for item in payments
                ],
                *[
                    AdminRecord(
                        id=item.id,
                        label=f"Invoice · {item.number}",
                        detail=f"{item.total_minor} {item.currency}",
                        status=item.state,
                        occurred_at=item.issued_at,
                    )
                    for item in invoices
                ],
            ],
            credit_ledger=credit_records,
            leads=[
                AdminRecord(
                    id=item.id,
                    label=item.name,
                    detail=f"{item.source} on {item.page_path or '/'}",
                    status=item.status,
                    occurred_at=item.captured_at,
                    attributes={"whatsapp_queued": item.whatsapp_notification_queued},
                )
                for item in leads
            ],
            domains=[
                AdminRecord(
                    id=item.id,
                    label=item.display_hostname,
                    detail=item.type,
                    status=item.state,
                    occurred_at=item.updated_at,
                    attributes={"tls": item.tls_status, "active": item.is_active},
                )
                for item in domains
            ],
            audit_activity=[self._audit_record(item) for item in audit],
        )

    async def section(self, section: AdminSection, limit: int) -> AdminOperationListResponse:
        return AdminOperationListResponse(
            section=section, items=await self._section_records(section, limit)
        )

    async def _user_summary(self, user: User) -> AdminUserSummary:
        methods = list(
            (
                await self.session.scalars(
                    select(AuthIdentity.provider)
                    .where(AuthIdentity.user_id == user.id)
                    .order_by(AuthIdentity.provider)
                )
            ).all()
        )
        website_count = await self._count(Website, Website.owner_user_id == user.id)
        draft_count = await self._count(
            Website, Website.owner_user_id == user.id, Website.status == "DRAFT"
        )
        live = await self.session.scalar(
            select(Website)
            .where(Website.live_owner_user_id == user.id)
            .order_by(Website.updated_at.desc())
            .limit(1)
        )
        subscription = await self.session.scalar(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.updated_at.desc())
            .limit(1)
        )
        return AdminUserSummary(
            id=user.id,
            email=user.display_email,
            status=user.status,
            signup_methods=methods,
            verified_at=user.verified_at,
            created_at=user.created_at,
            website_count=website_count,
            draft_count=draft_count,
            live_website_id=live.id if live else None,
            live_website_name=live.display_name if live else None,
            plan_code=subscription.plan_code_snapshot if subscription else "FREE",
            subscription_state=subscription.state if subscription else None,
        )

    async def _section_records(self, section: AdminSection, limit: int) -> list[AdminRecord]:
        if section == "websites":
            rows = (
                await self.session.execute(
                    select(Website, User)
                    .join(User, User.id == Website.owner_user_id)
                    .order_by(Website.updated_at.desc())
                    .limit(limit)
                )
            ).all()
            return [
                AdminRecord(
                    id=site.id,
                    label=site.display_name,
                    detail=owner.display_email,
                    status=site.status,
                    occurred_at=site.updated_at,
                    attributes={
                        "revision": site.revision,
                        "live": site.live_owner_user_id is not None,
                    },
                )
                for site, owner in rows
            ]
        if section == "commerce":
            return await self._commerce_records(limit)
        if section == "leads-credits":
            return await self._lead_credit_records(limit)
        if section == "domains":
            domain_rows = (
                await self.session.execute(
                    select(Domain, Website, User)
                    .join(Website, Website.id == Domain.website_id)
                    .join(User, User.id == Domain.owner_user_id)
                    .order_by(Domain.updated_at.desc())
                    .limit(limit)
                )
            ).all()
            return [
                AdminRecord(
                    id=domain.id,
                    label=domain.display_hostname,
                    detail=f"{website.display_name} · {owner.display_email}",
                    status=domain.state,
                    occurred_at=domain.updated_at,
                    attributes={"tls": domain.tls_status, "active": domain.is_active},
                )
                for domain, website, owner in domain_rows
            ]
        if section == "communications":
            recipient = aliased(User)
            communication_rows = (
                await self.session.execute(
                    select(TransactionalEmail, recipient.display_email)
                    .outerjoin(recipient, recipient.id == TransactionalEmail.recipient_user_id)
                    .order_by(TransactionalEmail.updated_at.desc())
                    .limit(limit)
                )
            ).all()
            return [
                AdminRecord(
                    id=email.id,
                    label=email.kind,
                    detail=display_email,
                    status=email.state,
                    occurred_at=email.updated_at,
                    attributes={"attempts": email.attempts, "error_code": email.last_error_code},
                )
                for email, display_email in communication_rows
            ]
        if section == "analytics":
            analytics_rows = (
                await self.session.execute(
                    select(AnalyticsDailyRollup, Website)
                    .join(Website, Website.id == AnalyticsDailyRollup.website_id)
                    .order_by(AnalyticsDailyRollup.bucket_date.desc())
                    .limit(limit)
                )
            ).all()
            return [
                AdminRecord(
                    id=rollup.id,
                    label=website.display_name,
                    detail=f"{rollup.bucket_date.isoformat()} · {rollup.timezone}",
                    occurred_at=rollup.bucket_date,
                    attributes={
                        "page_views": rollup.page_views,
                        "sessions": rollup.sessions,
                        "visitors": rollup.visitors,
                        "leads": rollup.leads,
                        "conversions": rollup.conversions,
                    },
                )
                for rollup, website in analytics_rows
            ]
        if section == "audit":
            actor = aliased(User)
            audit_rows = (
                await self.session.execute(
                    select(AuditLog, actor.display_email)
                    .outerjoin(actor, actor.id == AuditLog.actor_user_id)
                    .order_by(AuditLog.occurred_at.desc())
                    .limit(limit)
                )
            ).all()
            return [self._audit_record(log, display_email) for log, display_email in audit_rows]
        if section == "configuration":
            policy = await LeadCreditPolicyService(self.session).current()
            prices = list(
                (
                    await self.session.scalars(
                        select(ExportPrice).order_by(ExportPrice.created_at.desc())
                    )
                ).all()
            )
            return [
                AdminRecord(
                    id="lead_zero_balance_policy",
                    label="Lead zero-credit policy",
                    detail="Server-authoritative public lead capture behavior",
                    status=policy.policy,
                ),
                *[
                    AdminRecord(
                        id=price.id,
                        label=f"Website ZIP export · {price.currency}",
                        detail=f"{price.amount_minor} minor units · v{price.version}",
                        status="ACTIVE" if price.active else "INACTIVE",
                        occurred_at=price.effective_at,
                    )
                    for price in prices[:limit]
                ],
            ][:limit]
        raise ValueError(f"Unsupported admin section: {section}")

    async def _commerce_records(self, limit: int) -> list[AdminRecord]:
        plans = (
            await self.session.execute(
                select(Plan, PlanPrice)
                .join(PlanPrice, PlanPrice.plan_id == Plan.id)
                .where(PlanPrice.active.is_(True))
                .order_by(Plan.slot, PlanPrice.currency)
                .limit(limit)
            )
        ).all()
        subscriptions = (
            await self.session.execute(
                select(Subscription, User)
                .join(User, User.id == Subscription.user_id)
                .order_by(Subscription.updated_at.desc())
                .limit(limit)
            )
        ).all()
        payments = (
            await self.session.execute(
                select(Payment, User)
                .join(User, User.id == Payment.user_id)
                .order_by(Payment.created_at.desc())
                .limit(limit)
            )
        ).all()
        entitlements = (
            await self.session.execute(
                select(PlanEntitlement, Plan)
                .join(Plan, Plan.id == PlanEntitlement.plan_id)
                .order_by(Plan.slot, PlanEntitlement.capability_key)
                .limit(limit)
            )
        ).all()
        invoices = (
            await self.session.execute(
                select(Invoice, User)
                .join(User, User.id == Invoice.user_id)
                .order_by(Invoice.issued_at.desc())
                .limit(limit)
            )
        ).all()
        return [
            *[
                AdminRecord(
                    id=price.id,
                    label=f"Plan price · {plan.code}",
                    detail=f"{price.amount_minor} {price.currency} / {price.interval}",
                    status="ACTIVE" if price.active else "INACTIVE",
                    occurred_at=price.created_at,
                    attributes={"most_popular": plan.most_popular, "visible": plan.visible},
                )
                for plan, price in plans
            ],
            *[
                AdminRecord(
                    id=entitlement.id,
                    label=f"Entitlement · {plan.code}",
                    detail=entitlement.capability_key,
                    status=entitlement.value_type,
                    attributes={
                        "value_bool": entitlement.value_bool,
                        "value_int": entitlement.value_int,
                        "value_text": entitlement.value_text,
                    },
                )
                for entitlement, plan in entitlements
            ],
            *[
                AdminRecord(
                    id=subscription.id,
                    label=f"Subscription · {subscription.plan_code_snapshot}",
                    detail=user.display_email,
                    status=subscription.state,
                    occurred_at=subscription.updated_at,
                    attributes={
                        "amount_minor": subscription.amount_minor,
                        "currency": subscription.currency,
                    },
                )
                for subscription, user in subscriptions
            ],
            *[
                AdminRecord(
                    id=payment.id,
                    label=f"Payment · {payment.purpose}",
                    detail=user.display_email,
                    status=payment.state,
                    occurred_at=payment.created_at,
                    attributes={
                        "amount_minor": payment.expected_amount_minor,
                        "currency": payment.expected_currency,
                        "trusted": payment.trusted_at is not None,
                    },
                )
                for payment, user in payments
            ],
            *[
                AdminRecord(
                    id=invoice.id,
                    label=f"Invoice · {invoice.number}",
                    detail=user.display_email,
                    status=invoice.state,
                    occurred_at=invoice.issued_at,
                    attributes={"total_minor": invoice.total_minor, "currency": invoice.currency},
                )
                for invoice, user in invoices
            ],
        ][:limit]

    async def _lead_credit_records(self, limit: int) -> list[AdminRecord]:
        lead_rows = (
            await self.session.execute(
                select(Lead, Website, User)
                .join(Website, Website.id == Lead.website_id)
                .join(User, User.id == Lead.owner_user_id)
                .order_by(Lead.captured_at.desc())
                .limit(limit)
            )
        ).all()
        ledger_rows = (
            await self.session.execute(
                select(LeadCreditLedger, User)
                .join(User, User.id == LeadCreditLedger.user_id)
                .order_by(LeadCreditLedger.created_at.desc())
                .limit(limit)
            )
        ).all()
        ai_accounts = (
            await self.session.execute(
                select(AiCreditAccount, User)
                .join(User, User.id == AiCreditAccount.user_id)
                .order_by(AiCreditAccount.updated_at.desc())
                .limit(limit)
            )
        ).all()
        return [
            *[
                AdminRecord(
                    id=lead.id,
                    label=f"Lead · {lead.source}",
                    detail=f"{website.display_name} · {owner.display_email}",
                    status=lead.status,
                    occurred_at=lead.captured_at,
                    attributes={"whatsapp_queued": lead.whatsapp_notification_queued},
                )
                for lead, website, owner in lead_rows
            ],
            *[
                AdminRecord(
                    id=entry.id,
                    label=f"Lead credit · {entry.entry_type}",
                    detail=user.display_email,
                    occurred_at=entry.created_at,
                    attributes={"delta": entry.delta, "balance": entry.resulting_balance},
                )
                for entry, user in ledger_rows
            ],
            *[
                AdminRecord(
                    id=account.user_id,
                    label="AI credit account",
                    detail=user.display_email,
                    occurred_at=account.updated_at,
                    attributes={"balance": account.balance, "allowance": account.allowance},
                )
                for account, user in ai_accounts
            ],
        ][:limit]

    @staticmethod
    def _audit_record(log: AuditLog, actor_email: str | None = None) -> AdminRecord:
        return AdminRecord(
            id=log.id,
            label=log.event_type,
            detail=actor_email or log.target_type,
            occurred_at=log.occurred_at,
            attributes={
                "target_id": log.target_id,
                "reason": log.reason,
                "correlation_id": log.correlation_id,
            },
        )

    async def _count(self, model: type[object], *conditions: ColumnElement[bool]) -> int:
        statement = select(func.count()).select_from(model)
        if conditions:
            statement = statement.where(*conditions)
        return int(await self.session.scalar(statement) or 0)
