from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_engine
from zylora_api.db.template_models import Template, TemplateVersion
from zylora_api.modules.auth.http import get_crypto
from zylora_api.modules.templates.fixtures import CURATED_CATALOG
from zylora_api.modules.templates.scaling import (
    SCALE_MILESTONES,
    assert_scale_quality,
    build_scaled_catalogue,
)
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.templates.validation import document_checksum

BATCH_SIZE = 50


async def seed(*, refresh_existing: bool = False) -> None:
    """Seed the reviewed catalogue through the canonical Template lifecycle in bounded batches."""
    for milestone in SCALE_MILESTONES:
        assert_scale_quality(build_scaled_catalogue(milestone))
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        admin = await session.scalar(
            select(User).where(User.account_type == "SUPER_ADMIN", User.status == "ACTIVE")
        )
        if admin is None:
            raise SystemExit("Bootstrap and verify the Super Admin before seeding Templates.")
        slugs = [str(item["slug"]) for item in CURATED_CATALOG]
        existing = {
            template.slug: template
            for template in (
                await session.scalars(select(Template).where(Template.slug.in_(slugs)))
            ).all()
        }
        service = TemplateService(session, get_crypto())
        seeded = 0
        refreshed = 0
        for item in CURATED_CATALOG:
            existing_template = existing.get(item["slug"])
            if existing_template is not None and not refresh_existing:
                continue
            if existing_template is not None:
                current = await session.scalar(
                    select(TemplateVersion).where(
                        TemplateVersion.id == existing_template.current_published_version_id
                    )
                )
                if current is not None and current.checksum == document_checksum(item["document"]):
                    continue
                version = await service.add_version(
                    existing_template.id,
                    cast(dict[str, Any], item["document"]),
                    admin.id,
                )
                validated = await service.validate(existing_template.id, version.version, admin.id)
                if validated.status != "VALIDATED":
                    raise RuntimeError(f"Generated Template {item['slug']} did not validate.")
                await service.approve(existing_template.id, version.version)
                await service.publish(existing_template.id, version.version)
                refreshed += 1
                if refreshed % BATCH_SIZE == 0:
                    await session.commit()
                    print(f"Refreshed {refreshed} validated Templates.")
                continue
            payload = TemplateCreateRequest.model_validate(
                {
                    key: value
                    for key, value in item.items()
                    if key
                    in {
                        "slug",
                        "name",
                        "summary",
                        "category_slug",
                        "category_name",
                        "category_description",
                        "tags",
                        "featured_order",
                    }
                }
            )
            template = await service.create(payload, admin.id)
            version = await service.add_version(
                template.id, cast(dict[str, Any], item["document"]), admin.id
            )
            validated = await service.validate(template.id, version.version, admin.id)
            if validated.status != "VALIDATED":
                raise RuntimeError(f"Generated Template {item['slug']} did not validate.")
            await service.approve(template.id, version.version)
            await service.publish(template.id, version.version)
            seeded += 1
            if seeded % BATCH_SIZE == 0:
                await session.commit()
                print(f"Seeded {seeded} validated Templates.")
        await session.commit()
        print(
            f"Template catalogue seed complete: {seeded} new Templates; "
            f"{len(existing)} already present; {refreshed} refreshed."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Publish a new validated version when an existing release Template document changed.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(seed(refresh_existing=args.refresh_existing))
    else:
        asyncio.run(seed(refresh_existing=args.refresh_existing))
