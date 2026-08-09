from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import AuditLog
from zylora_api.modules.auth.security import AuthCrypto


class AuditService:
    def __init__(self, session: AsyncSession, crypto: AuthCrypto) -> None:
        self._session = session
        self._crypto = crypto

    def record(
        self,
        event_type: str,
        *,
        correlation_id: str,
        actor_user_id: UUID | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                event_type=event_type,
                actor_user_id=actor_user_id,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                correlation_id=correlation_id,
                ip_digest=(
                    self._crypto.digest(ip_address, purpose="audit-ip") if ip_address else None
                ),
                metadata_json=metadata or {},
            )
        )
