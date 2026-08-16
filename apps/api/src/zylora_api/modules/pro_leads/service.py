from __future__ import annotations

import hashlib
import logging
import secrets
import string
from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import Settings
from zylora_api.db.lead_models import ProLead
from zylora_api.db.models import OutboxEvent
from zylora_api.modules.auth.challenge import ChallengeService
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.pro_leads.schemas import (
    ProLeadCreateRequest,
    ProLeadSummaryResponse,
)
from zylora_api.modules.templates.service import problem

UTC = UTC
logger = logging.getLogger(__name__)


class ProLeadService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        challenge_service: ChallengeService | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.challenge_service = challenge_service
        self.redis_client = redis_client

    async def _generate_reference_id(self) -> str:
        for _ in range(10):
            num = 100000 + secrets.randbelow(900000)
            ref_id = f"ZPRO-{num}"
            existing = await self.session.scalar(
                select(ProLead).where(ProLead.reference_id == ref_id)
            )
            if not existing:
                return ref_id
        # Fallback to random alphanumeric string
        alphabet = string.ascii_uppercase + string.digits
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        return f"ZPRO-{suffix}"

    @staticmethod
    def _compute_fingerprint(
        normalized_email: str, website_type: str, preferred_contact_time: str
    ) -> str:
        raw = (
            f"{normalized_email}:"
            f"{website_type.strip().lower()}:"
            f"{preferred_contact_time.strip().lower()}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def _check_ip_rate_limit(self, client_ip: str) -> None:
        if not self.redis_client:
            return
        key = f"pro_lead:ip:{client_ip}"
        try:
            current = await self.redis_client.incr(key)
            if current == 1:
                await self.redis_client.expire(key, 1800)  # 30 minutes
            if current > 3:
                raise problem(
                    429,
                    "rate_limit_exceeded",
                    "Too many Pro enquiries from this IP address. Please try again later.",
                )
        except AuthProblem:
            raise
        except Exception as exc:
            logger.warning("Redis IP rate limit check failed: %s", exc)

    async def _check_email_rate_limit(self, normalized_email: str) -> None:
        if not self.redis_client:
            return
        key = f"pro_lead:email:{normalized_email}"
        try:
            current = await self.redis_client.incr(key)
            if current == 1:
                await self.redis_client.expire(key, 86400)  # 24 hours
            if current > 5:
                raise problem(
                    429,
                    "rate_limit_exceeded",
                    "Too many submissions for this email address.",
                )
        except AuthProblem:
            raise
        except Exception as exc:
            logger.warning("Redis email rate limit check failed: %s", exc)

    async def submit_pro_enquiry(
        self,
        payload: ProLeadCreateRequest,
        *,
        client_ip: str,
        correlation_id: str,
    ) -> ProLead:
        # 1. Honeypot check
        if payload.company_website_url and payload.company_website_url.strip():
            # Silent rejection: return synthetic ProLead record without DB insert or email dispatch
            return ProLead(
                id=UUID("00000000-0000-0000-0000-000000000000"),
                reference_id="ZPRO-HONEYPOT",
                name=payload.name,
                email=payload.email,
                website_type=payload.website_type,
                preferred_contact_time=payload.preferred_contact_time,
                status="PENDING",
                idempotency_key=f"honeypot-{correlation_id}",
                request_fingerprint="honeypot",
                is_spam=True,
                spam_score=100,
                spam_reason_code="HONEYPOT_TRIGGERED",
            )

        # 2. Turnstile Verification
        if self.challenge_service and self.settings.turnstile_enabled:
            await self.challenge_service.enforce(
                payload.turnstile_token,
                expected_action="pro_enquiry",
                remote_ip=client_ip,
                correlation_id=correlation_id,
            )

        normalized_email = payload.email.strip().lower()
        fingerprint = self._compute_fingerprint(
            normalized_email, payload.website_type, payload.preferred_contact_time
        )

        # 3. IP Rate Limit
        await self._check_ip_rate_limit(client_ip)

        # 4. Email Rate Limit
        await self._check_email_rate_limit(normalized_email)

        # 5. Duplicate suppression check (24h window)
        twenty_four_hours_ago = datetime.now(UTC) - timedelta(hours=24)
        existing_duplicate = await self.session.scalar(
            select(ProLead)
            .where(
                ProLead.request_fingerprint == fingerprint,
                ProLead.submitted_at >= twenty_four_hours_ago,
                ProLead.is_spam.is_(False),
            )
            .order_by(ProLead.submitted_at.desc())
            .limit(1)
        )
        if existing_duplicate:
            # Return existing duplicate without inserting or sending email
            return existing_duplicate

        # 6. Save ProLead
        reference_id = await self._generate_reference_id()
        idempotency_key = f"pro-lead:{fingerprint}:{int(datetime.now(UTC).timestamp())}"
        pro_lead = ProLead(
            reference_id=reference_id,
            name=payload.name,
            email=payload.email,
            website_type=payload.website_type,
            preferred_contact_time=payload.preferred_contact_time,
            status="PENDING",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            is_spam=False,
        )
        self.session.add(pro_lead)
        await self.session.flush()

        # 7. Outbox Events for Admin & Customer Emails
        self.session.add(
            OutboxEvent(
                aggregate_type="ProLead",
                aggregate_id=pro_lead.id,
                event_type="PRO_LEAD_SUBMITTED",
                event_version=1,
                payload={
                    "pro_lead_id": str(pro_lead.id),
                    "reference_id": reference_id,
                    "name": pro_lead.name,
                    "email": pro_lead.email,
                    "website_type": pro_lead.website_type,
                    "preferred_contact_time": pro_lead.preferred_contact_time,
                    "submitted_at": pro_lead.submitted_at.isoformat(),
                },
            )
        )

        return pro_lead

    async def list_pro_leads(self) -> list[ProLead]:
        statement = (
            select(ProLead).where(ProLead.is_spam.is_(False)).order_by(ProLead.submitted_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get_summary(self) -> ProLeadSummaryResponse:
        total = (
            await self.session.scalar(
                select(func.count(ProLead.id)).where(ProLead.is_spam.is_(False))
            )
            or 0
        )
        closed = (
            await self.session.scalar(
                select(func.count(ProLead.id)).where(
                    ProLead.is_spam.is_(False), ProLead.status == "CLOSED"
                )
            )
            or 0
        )
        not_closed = (
            await self.session.scalar(
                select(func.count(ProLead.id)).where(
                    ProLead.is_spam.is_(False), ProLead.status == "NOT_CLOSED"
                )
            )
            or 0
        )
        pending = (
            await self.session.scalar(
                select(func.count(ProLead.id)).where(
                    ProLead.is_spam.is_(False), ProLead.status == "PENDING"
                )
            )
            or 0
        )
        amount_received = (
            await self.session.scalar(
                select(func.coalesce(func.sum(ProLead.amount_received), 0)).where(
                    ProLead.is_spam.is_(False), ProLead.status == "CLOSED"
                )
            )
            or 0
        )

        return ProLeadSummaryResponse(
            total_pro_leads=total,
            closed=closed,
            not_closed=not_closed,
            pending=pending,
            amount_received=int(amount_received),
        )

    async def update_status(
        self, pro_lead_id: UUID, new_status: str, amount_received: int | None = None
    ) -> ProLead:
        pro_lead = await self.session.get(ProLead, pro_lead_id)
        if not pro_lead:
            raise problem(404, "pro_lead_not_found", "Pro lead not found.")
        if new_status == "CLOSED":
            if amount_received is None or amount_received < 0:
                raise problem(
                    400,
                    "invalid_amount",
                    "Amount received is required when marking lead as closed.",
                )
            pro_lead.status = "CLOSED"
            pro_lead.amount_received = amount_received
            pro_lead.resolved_at = datetime.now(UTC)
        elif new_status == "NOT_CLOSED":
            pro_lead.status = "NOT_CLOSED"
            pro_lead.resolved_at = datetime.now(UTC)
        else:
            raise problem(400, "invalid_status", "Status must be CLOSED or NOT_CLOSED.")

        pro_lead.updated_at = datetime.now(UTC)
        await self.session.flush()
        return pro_lead
