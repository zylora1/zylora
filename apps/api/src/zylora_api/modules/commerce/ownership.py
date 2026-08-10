from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import User
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import OwnershipTransfer, Website, WebsiteOwnership
from zylora_api.modules.notifications.service import NotificationService
from zylora_api.modules.templates.service import problem

TRANSFER_CONFIRMATION_VERSION = "OWNER_TRANSFER_V1"
ACTIVE_TRANSFER_STATES = ("REQUESTED", "VALIDATED", "DEACTIVATING")
OFFLINE_TRANSFER_STATES = {"DRAFT", "UNPUBLISHED", "FAILED"}


class OwnershipService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def validate_recipient(
        self,
        website_id: UUID,
        sender_user_id: UUID,
        recipient_normalized_email: str,
    ) -> tuple[Website, User]:
        website = await self.session.scalar(
            select(Website).where(
                Website.id == website_id,
                Website.owner_user_id == sender_user_id,
            )
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        recipient = await self._recipient(sender_user_id, recipient_normalized_email)
        return website, recipient

    async def start_transfer(
        self,
        website_id: UUID,
        sender_user_id: UUID,
        recipient_normalized_email: str,
        confirmation_version: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OwnershipTransfer:
        if confirmation_version != TRANSFER_CONFIRMATION_VERSION:
            raise problem(
                422,
                "transfer_confirmation_required",
                "Confirm the Website ownership transfer before continuing.",
            )
        previous = await self.session.scalar(
            select(OwnershipTransfer)
            .where(
                OwnershipTransfer.sender_user_id == sender_user_id,
                OwnershipTransfer.idempotency_key == idempotency_key,
            )
            .with_for_update()
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
        recipient = await self._recipient(sender_user_id, recipient_normalized_email)
        active = await self.session.scalar(
            select(OwnershipTransfer)
            .where(
                OwnershipTransfer.website_id == website.id,
                OwnershipTransfer.status.in_(ACTIVE_TRANSFER_STATES),
            )
            .with_for_update()
        )
        if active:
            raise problem(
                409,
                "transfer_in_progress",
                "This Website already has an ownership transfer in progress.",
            )
        current = await self._current_ownership(website.id, sender_user_id)
        now = datetime.now(UTC)
        transfer = OwnershipTransfer(
            website_id=website.id,
            sender_user_id=sender_user_id,
            recipient_user_id=recipient.id,
            status="VALIDATED",
            idempotency_key=idempotency_key,
            confirmation_version=confirmation_version,
            validated_at=now,
        )
        self.session.add(transfer)
        await self.session.flush()
        if website.status in OFFLINE_TRANSFER_STATES:
            await self._complete_locked(website, current, transfer, now)
            return transfer
        if website.status == "PUBLISHED" and website.active_deployment_id:
            transfer.status = "DEACTIVATING"
            website.status = "UNPUBLISHING"
            self.session.add(
                OutboxEvent(
                    aggregate_type="WEBSITE",
                    aggregate_id=website.id,
                    event_type="website.unpublish_requested",
                    payload={
                        "website_id": str(website.id),
                        "owner_user_id": str(sender_user_id),
                        "transfer_id": str(transfer.id),
                    },
                    correlation_id=correlation_id,
                )
            )
            return transfer
        raise problem(
            409,
            "website_transfer_not_ready",
            "Cancel pending publication or wait for the Website to become offline before transfer.",
        )

    async def transfer(
        self,
        website_id: UUID,
        sender_user_id: UUID,
        recipient_normalized_email: str,
        idempotency_key: str,
    ) -> OwnershipTransfer:
        """Compatibility entrypoint for domain callers; HTTP commands use explicit confirmation."""
        return await self.start_transfer(
            website_id,
            sender_user_id,
            recipient_normalized_email,
            TRANSFER_CONFIRMATION_VERSION,
            idempotency_key,
            "ownership-transfer",
        )

    async def complete_after_unpublish(self, transfer_id: UUID) -> OwnershipTransfer:
        transfer = await self.session.scalar(
            select(OwnershipTransfer).where(OwnershipTransfer.id == transfer_id).with_for_update()
        )
        if not transfer:
            raise problem(404, "ownership_transfer_not_found", "Ownership transfer not found.")
        if transfer.status == "COMPLETED":
            return transfer
        if transfer.status != "DEACTIVATING":
            raise problem(
                409,
                "transfer_completion_not_expected",
                "Ownership transfer is not awaiting route deactivation.",
            )
        website = await self.session.scalar(
            select(Website).where(Website.id == transfer.website_id).with_for_update()
        )
        if (
            not website
            or website.owner_user_id != transfer.sender_user_id
            or website.status != "UNPUBLISHED"
            or website.live_owner_user_id is not None
            or website.active_deployment_id is not None
        ):
            raise problem(
                409,
                "transfer_route_state_invalid",
                "Website routing must be fully inactive before ownership can change.",
            )
        current = await self._current_ownership(website.id, transfer.sender_user_id)
        await self._complete_locked(website, current, transfer, datetime.now(UTC))
        return transfer

    async def fail_after_unpublish(self, transfer_id: UUID, failure_code: str) -> None:
        transfer = await self.session.scalar(
            select(OwnershipTransfer).where(OwnershipTransfer.id == transfer_id).with_for_update()
        )
        if transfer and transfer.status == "DEACTIVATING":
            transfer.status = "FAILED"
            transfer.failure_code = failure_code

    async def get_for_owner(self, transfer_id: UUID, owner_user_id: UUID) -> OwnershipTransfer:
        transfer = await self.session.scalar(
            select(OwnershipTransfer)
            .join(Website, Website.id == OwnershipTransfer.website_id)
            .where(
                OwnershipTransfer.id == transfer_id,
                Website.owner_user_id == owner_user_id,
            )
        )
        if not transfer:
            raise problem(404, "ownership_transfer_not_found", "Ownership transfer not found.")
        return transfer

    async def _recipient(self, sender_user_id: UUID, normalized_email: str) -> User:
        recipient = await self.session.scalar(
            select(User).where(
                User.normalized_email == normalized_email,
                User.account_type == "USER",
                User.status == "ACTIVE",
            )
        )
        if not recipient:
            raise problem(404, "transfer_recipient_not_found", "Recipient User not found.")
        if recipient.id == sender_user_id:
            raise problem(409, "self_transfer_forbidden", "A Website cannot be transferred to you.")
        return recipient

    async def _current_ownership(self, website_id: UUID, owner_user_id: UUID) -> WebsiteOwnership:
        current = await self.session.scalar(
            select(WebsiteOwnership)
            .where(
                WebsiteOwnership.website_id == website_id,
                WebsiteOwnership.ended_at.is_(None),
            )
            .with_for_update()
        )
        if not current or current.owner_user_id != owner_user_id:
            raise problem(409, "ownership_state_invalid", "Website ownership needs review.")
        return current

    async def _complete_locked(
        self,
        website: Website,
        current: WebsiteOwnership,
        transfer: OwnershipTransfer,
        now: datetime,
    ) -> None:
        from zylora_api.db.chatbot_models import Chatbot, ChatbotKnowledgeIndex

        chatbot = await self.session.scalar(
            select(Chatbot).where(Chatbot.website_id == website.id).with_for_update()
        )
        if chatbot:
            indexes = list(
                (
                    await self.session.scalars(
                        select(ChatbotKnowledgeIndex)
                        .where(
                            ChatbotKnowledgeIndex.website_id == website.id,
                            ChatbotKnowledgeIndex.state.not_in(("DELETED",)),
                        )
                        .with_for_update()
                    )
                ).all()
            )
            for knowledge_index in indexes:
                knowledge_index.state = "DELETED"
                if knowledge_index.artifact_key:
                    self.session.add(
                        OutboxEvent(
                            aggregate_type="CHATBOT_KNOWLEDGE_INDEX",
                            aggregate_id=knowledge_index.id,
                            event_type="chatbot.cleanup_requested",
                            payload={"artifact_key": knowledge_index.artifact_key},
                            correlation_id=f"ownership-transfer:{transfer.id}",
                        )
                    )
            chatbot.active_index_id = None
            chatbot.state = "DISABLED"
            chatbot.version += 1
        current.ended_at = now
        current.transfer_id = transfer.id
        self.session.add(
            WebsiteOwnership(
                website_id=website.id,
                owner_user_id=transfer.recipient_user_id,
                started_at=now,
                transfer_id=transfer.id,
                acquisition_reason="TRANSFER",
            )
        )
        website.owner_user_id = transfer.recipient_user_id
        website.live_owner_user_id = None
        website.active_deployment_id = None
        website.status = "DRAFT"
        website.published_version_id = None
        website.publication_domain_type = None
        website.publish_request_idempotency_key = None
        transfer.status = "COMPLETED"
        transfer.completed_at = now
        transfer.failure_code = None
        await NotificationService(self.session).create(
            recipient_user_id=transfer.recipient_user_id,
            notification_type="TRANSFER_COMPLETED",
            resource_type="ownership_transfer",
            resource_id=transfer.id,
            dedupe_key=f"transfer-completed:{transfer.id}",
        )
