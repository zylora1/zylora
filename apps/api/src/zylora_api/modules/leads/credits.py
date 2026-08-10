from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import User
from zylora_api.db.lead_models import Lead, LeadCreditAccount, LeadCreditLedger
from zylora_api.db.models import PlatformMetadata
from zylora_api.modules.templates.service import problem

ALLOW_DEBT = "ALLOW_DEBT"
REJECT_NEW = "REJECT_NEW"
ZERO_CREDIT_POLICIES = frozenset({ALLOW_DEBT, REJECT_NEW})
POLICY_KEY = "lead_zero_balance_policy"


@dataclass(frozen=True)
class LeadCreditPolicy:
    policy: str


class LeadCreditPolicyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current(self) -> LeadCreditPolicy:
        record = await self.session.get(PlatformMetadata, POLICY_KEY)
        candidate = record.value.get("policy") if record else ALLOW_DEBT
        return LeadCreditPolicy(candidate if candidate in ZERO_CREDIT_POLICIES else ALLOW_DEBT)

    async def configure(self, policy: str) -> LeadCreditPolicy:
        if policy not in ZERO_CREDIT_POLICIES:
            raise problem(422, "invalid_zero_credit_policy", "Lead credit policy is invalid.")
        record = await self.session.get(PlatformMetadata, POLICY_KEY, with_for_update=True)
        if record:
            record.value = {"policy": policy}
            record.version += 1
        else:
            self.session.add(PlatformMetadata(key=POLICY_KEY, value={"policy": policy}, version=1))
        return LeadCreditPolicy(policy)


class CreditLedgerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def balance_for(self, user_id: UUID) -> int:
        account = await self.session.scalar(
            select(LeadCreditAccount).where(LeadCreditAccount.user_id == user_id)
        )
        return account.balance if account else 0

    async def ensure_capture_allowed(self, user_id: UUID) -> None:
        await self._advisory_lock(user_id)
        account = await self._locked_account(user_id)
        policy = await LeadCreditPolicyService(self.session).current()
        if policy.policy == REJECT_NEW and account.balance < 1:
            raise problem(
                409,
                "lead_credits_exhausted",
                "Lead capture is temporarily unavailable for this Website.",
            )

    async def consume_for_lead(self, lead: Lead) -> LeadCreditLedger:
        await self._advisory_lock(lead.owner_user_id)
        existing = await self.session.scalar(
            select(LeadCreditLedger).where(LeadCreditLedger.lead_id == lead.id)
        )
        if existing:
            return existing
        account = await self._locked_account(lead.owner_user_id)
        policy = await LeadCreditPolicyService(self.session).current()
        if policy.policy == REJECT_NEW and account.balance < 1:
            raise problem(
                409,
                "lead_credits_exhausted",
                "Lead capture is temporarily unavailable for this Website.",
            )
        account.balance -= 1
        account.version += 1
        ledger = LeadCreditLedger(
            user_id=lead.owner_user_id,
            lead_id=lead.id,
            entry_type="LEAD_CAPTURE",
            delta=-1,
            resulting_balance=account.balance,
            idempotency_key=f"lead:{lead.id}",
            reason="VALID_LEAD_CAPTURED",
        )
        self.session.add(ledger)
        return ledger

    async def adjust(
        self,
        *,
        user_id: UUID,
        actor_user_id: UUID,
        delta: int,
        idempotency_key: str,
        reason: str,
    ) -> LeadCreditLedger:
        if delta == 0 or abs(delta) > 1_000_000:
            raise problem(422, "invalid_lead_credit_adjustment", "Credit adjustment is invalid.")
        if not reason.strip() or len(reason.strip()) > 240:
            raise problem(422, "invalid_lead_credit_reason", "Provide a valid adjustment reason.")
        user = await self.session.get(User, user_id)
        if not user or user.account_type != "USER" or user.status != "ACTIVE":
            raise problem(404, "user_not_found", "User not found.")
        await self._advisory_lock(user_id)
        existing = await self.session.scalar(
            select(LeadCreditLedger).where(
                LeadCreditLedger.user_id == user_id,
                LeadCreditLedger.idempotency_key == idempotency_key,
            )
        )
        if existing:
            if existing.delta != delta or existing.reason != reason.strip():
                raise problem(
                    409,
                    "idempotency_key_reused",
                    "This idempotency key was used for another credit adjustment.",
                )
            return existing
        account = await self._locked_account(user_id)
        account.balance += delta
        account.version += 1
        entry_type = "ADMIN_GRANT" if delta > 0 else "CORRECTION"
        ledger = LeadCreditLedger(
            user_id=user_id,
            actor_user_id=actor_user_id,
            entry_type=entry_type,
            delta=delta,
            resulting_balance=account.balance,
            idempotency_key=idempotency_key,
            reason=reason.strip(),
        )
        self.session.add(ledger)
        return ledger

    async def _locked_account(self, user_id: UUID) -> LeadCreditAccount:
        account = await self.session.scalar(
            select(LeadCreditAccount).where(LeadCreditAccount.user_id == user_id).with_for_update()
        )
        if account:
            return account
        account = LeadCreditAccount(user_id=user_id, balance=0, version=1)
        self.session.add(account)
        await self.session.flush()
        return account

    async def _advisory_lock(self, user_id: UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
            {"value": f"lead-credit:{user_id}"},
        )
