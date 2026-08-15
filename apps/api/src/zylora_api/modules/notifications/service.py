from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.lead_models import Notification
from zylora_api.modules.templates.service import problem


@dataclass(frozen=True)
class NotificationPresentation:
    title: str
    body: str
    deep_link: str


class NotificationService:
    """Durable in-app notification lifecycle with server-owned presentation links."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        recipient_user_id: UUID,
        notification_type: str,
        resource_type: str,
        resource_id: UUID,
        dedupe_key: str,
        data: dict[str, Any] | None = None,
    ) -> Notification:
        if not 1 <= len(dedupe_key) <= 200:
            raise problem(422, "notification_dedupe_invalid", "Notification key is invalid.")
        presentation = self._presentation(notification_type, data or {})
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
            {"value": f"notification:{recipient_user_id}:{dedupe_key}"},
        )
        existing = await self.session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.dedupe_key == dedupe_key,
            )
        )
        if existing:
            return existing
        notification = Notification(
            recipient_user_id=recipient_user_id,
            type=notification_type,
            resource_type=resource_type,
            resource_id=resource_id,
            data=data or {},
            title=presentation.title,
            body=presentation.body,
            deep_link=presentation.deep_link,
            dedupe_key=dedupe_key,
            state="UNREAD",
        )
        self.session.add(notification)
        return notification

    async def page_for_user(
        self,
        *,
        recipient_user_id: UUID,
        limit: int,
        before: datetime | None = None,
    ) -> tuple[list[Notification], int, datetime | None]:
        if not 1 <= limit <= 100:
            raise problem(422, "notification_limit_invalid", "Notification limit is invalid.")
        statement = select(Notification).where(Notification.recipient_user_id == recipient_user_id)
        if before:
            statement = statement.where(Notification.created_at < before)
        records = list(
            (
                await self.session.scalars(
                    statement.order_by(Notification.created_at.desc()).limit(limit + 1)
                )
            ).all()
        )
        next_cursor = records[-1].created_at if len(records) > limit else None
        records = records[:limit]
        unread_count = int(
            await self.session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.recipient_user_id == recipient_user_id,
                    Notification.state == "UNREAD",
                )
            )
            or 0
        )
        return records, unread_count, next_cursor

    async def mark_read(self, notification_id: UUID, recipient_user_id: UUID) -> Notification:
        notification = await self.session.scalar(
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.recipient_user_id == recipient_user_id,
            )
            .with_for_update()
        )
        if not notification:
            raise problem(404, "notification_not_found", "Notification not found.")
        if notification.state == "UNREAD":
            notification.state = "READ"
            notification.read_at = datetime.now(UTC)
        return notification

    @staticmethod
    def _presentation(notification_type: str, data: dict[str, Any]) -> NotificationPresentation:
        source = str(data.get("source") or "Website")
        presentations = {
            "LEAD_CAPTURED": NotificationPresentation(
                "New lead captured",
                f"A {source.casefold()} enquiry is ready to review.",
                "/app/leads",
            ),
            "WEBSITE_PUBLISHED": NotificationPresentation(
                "Website published",
                "Your Website is live and ready for real visitor activity.",
                "/app/websites",
            ),
            "WEBSITE_PUBLISH_FAILED": NotificationPresentation(
                "Publishing needs attention",
                "Your Website was not published. Review the safe status and try again when ready.",
                "/app/websites",
            ),
            "TRANSFER_COMPLETED": NotificationPresentation(
                "Ownership transfer completed",
                "This Website is now available in its new owner's private workspace.",
                "/app/websites",
            ),
            "EXPORT_READY": NotificationPresentation(
                "Website export is ready",
                "Your private Website ZIP is ready to download before it expires.",
                "/app/websites",
            ),
            "BILLING_STATE": NotificationPresentation(
                "Billing update",
                "Your verified billing state has changed.",
                "/app/billing",
            ),
            "DOMAIN_STATE": NotificationPresentation(
                "Domain update",
                "Your domain or TLS state has changed.",
                "/app/domains",
            ),
            "ZERO_LEAD_CHECKPOINT": NotificationPresentation(
                "Improve your enquiry results",
                "Your Website is live but has not received an enquiry yet. "
                "Review practical next steps.",
                "/app/analytics",
            ),
        }
        presentation = presentations.get(notification_type)
        if not presentation:
            raise problem(422, "notification_type_invalid", "Notification type is invalid.")
        return presentation
