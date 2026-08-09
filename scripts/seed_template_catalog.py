from __future__ import annotations

import asyncio
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_engine
from zylora_api.db.template_models import Template
from zylora_api.modules.auth.http import get_crypto
from zylora_api.modules.templates.fixtures import CURATED_CATALOG
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService


async def seed() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        admin = await session.scalar(
            select(User).where(User.account_type == "SUPER_ADMIN", User.status == "ACTIVE")
        )
        if admin is None:
            raise SystemExit("Bootstrap and verify the Super Admin before seeding Templates.")
        service = TemplateService(session, get_crypto())
        for item in CURATED_CATALOG:
            existing = await session.scalar(select(Template).where(Template.slug == item["slug"]))
            if existing:
                continue
            payload = TemplateCreateRequest.model_validate(
                {key: value for key, value in item.items() if key != "document"}
            )
            template = await service.create(payload, admin.id)
            version = await service.add_version(
                template.id, cast(dict[str, Any], item["document"]), admin.id
            )
            await service.validate(template.id, version.version, admin.id)
            await service.approve(template.id, version.version)
            await service.publish(template.id, version.version)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
