from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import User
from zylora_api.db.website_models import OwnershipTransfer, Website, WebsiteOwnership
from zylora_api.modules.templates.service import problem


class OwnershipService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def transfer(
        self,
        website_id: UUID,
        sender_user_id: UUID,
        recipient_normalized_email: str,
        idempotency_key: str,
    ) -> OwnershipTransfer:
        previous = await self.session.scalar(
            select(OwnershipTransfer).where(
                OwnershipTransfer.sender_user_id == sender_user_id,
                OwnershipTransfer.idempotency_key == idempotency_key,
            )
        )
        if previous:
            if previous.website_id != website_id:
                raise problem(
                    409,
                    "idempotency_key_reused",
                    "This idempotency key was already used for another Website.",
                )
            return previous
        website = await self.session.scalar(
            select(Website).where(Website.id == website_id).with_for_update()
        )
        if not website or website.owner_user_id != sender_user_id:
            raise problem(404, "website_not_found", "Website not found.")
        if website.status not in {"DRAFT", "UNPUBLISHED", "FAILED"}:
            raise problem(
                409,
                "website_must_be_unpublished",
                "Unpublish this Website before transferring ownership.",
            )
        recipient = await self.session.scalar(
            select(User).where(
                User.normalized_email == recipient_normalized_email,
                User.account_type == "USER",
                User.status == "ACTIVE",
            )
        )
        if not recipient:
            raise problem(404, "transfer_recipient_not_found", "Recipient User not found.")
        if recipient.id == sender_user_id:
            raise problem(409, "self_transfer_forbidden", "A Website cannot be transferred to you.")
        current = await self.session.scalar(
            select(WebsiteOwnership)
            .where(
                WebsiteOwnership.website_id == website.id,
                WebsiteOwnership.ended_at.is_(None),
            )
            .with_for_update()
        )
        if not current or current.owner_user_id != sender_user_id:
            raise problem(409, "ownership_state_invalid", "Website ownership needs review.")
        now = datetime.now(UTC)
        transfer = OwnershipTransfer(
            website_id=website.id,
            sender_user_id=sender_user_id,
            recipient_user_id=recipient.id,
            status="COMPLETED",
            idempotency_key=idempotency_key,
            completed_at=now,
        )
        self.session.add(transfer)
        await self.session.flush()
        current.ended_at = now
        current.transfer_id = transfer.id
        self.session.add(
            WebsiteOwnership(
                website_id=website.id,
                owner_user_id=recipient.id,
                started_at=now,
                transfer_id=transfer.id,
                acquisition_reason="TRANSFER",
            )
        )
        website.owner_user_id = recipient.id
        website.live_owner_user_id = None
        website.status = "DRAFT"
        website.publication_domain_type = None
        website.publish_request_idempotency_key = None
        return transfer
