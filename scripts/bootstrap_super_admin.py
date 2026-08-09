from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.core.config import get_settings
from zylora_api.db.auth_models import AuthIdentity, SuperAdminProfile, User
from zylora_api.db.session import get_engine
from zylora_api.modules.audit.service import AuditService
from zylora_api.modules.auth.security import AuthCrypto


async def bootstrap() -> None:
    email = os.environ.get("ZYLORA_BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("ZYLORA_BOOTSTRAP_ADMIN_PASSWORD")
    display_name = os.environ.get("ZYLORA_BOOTSTRAP_ADMIN_NAME", "Zylora Super Admin")
    if not email or not password:
        raise RuntimeError(
            "ZYLORA_BOOTSTRAP_ADMIN_EMAIL and ZYLORA_BOOTSTRAP_ADMIN_PASSWORD are required"
        )
    settings = get_settings()
    crypto = AuthCrypto(settings.auth_secret)
    normalized, display = crypto.normalize_email(email)
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session, session.begin():
        count = await session.scalar(
            select(func.count(User.id)).where(User.account_type == "SUPER_ADMIN")
        )
        if count:
            raise RuntimeError("a Super Admin already exists; bootstrap is single-use")
        if await session.scalar(select(User.id).where(User.normalized_email == normalized)):
            raise RuntimeError("the bootstrap email already belongs to another account")
        now = datetime.now(UTC)
        user = User(
            account_type="SUPER_ADMIN",
            normalized_email=normalized,
            display_email=display,
            password_hash=crypto.hash_password(password, admin=True),
            status="ACTIVE",
            verified_at=now,
        )
        session.add(user)
        await session.flush()
        session.add_all(
            [
                AuthIdentity(
                    user_id=user.id,
                    provider="PASSWORD",
                    provider_subject=normalized,
                ),
                SuperAdminProfile(user_id=user.id, display_name=display_name),
            ]
        )
        AuditService(session, crypto).record(
            "admin.bootstrap_completed",
            correlation_id="bootstrap-super-admin",
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            reason="INITIAL_PLATFORM_BOOTSTRAP",
        )
    print("Super Admin bootstrap completed.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(bootstrap(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(bootstrap())
