from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.auth_models import User
from zylora_api.db.template_models import TemplateVersion
from zylora_api.db.website_models import (
    AiCreditAccount,
    AiCreditLedger,
    Website,
    WebsitePage,
    WebsiteVersion,
)
from zylora_api.modules.commerce.service import SubscriptionService
from zylora_api.modules.templates.document import COMPONENT_REGISTRY
from zylora_api.modules.templates.service import problem
from zylora_api.modules.templates.validation import validate_document


def _fallback_components(page: WebsitePage) -> list[dict[str, Any]]:
    return [
        {
            "id": f"hero-{page.id.hex[:12]}",
            "type": "HERO",
            "props": {"heading": page.name, "body": "Add your page content."},
            "children": [],
            "responsive": {},
            "interactions": [],
        }
    ]


def _requirements(pages: list[dict[str, Any]]) -> list[str]:
    result: set[str] = set()

    def visit(component: dict[str, Any]) -> None:
        entry = COMPONENT_REGISTRY.get(str(component.get("type", "")))
        if entry and entry.required_feature:
            result.add(entry.required_feature)
        for child in component.get("children", []):
            if isinstance(child, dict):
                visit(child)

    for page in pages:
        for component in page["components"]:
            if isinstance(component, dict):
                visit(component)
    return sorted(result)


def serialize_page_state(pages: list[WebsitePage]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(page.id),
            "source_template_page_id": page.source_template_page_id,
            "parent_page_id": str(page.parent_page_id) if page.parent_page_id else None,
            "name": page.name,
            "slug": page.slug,
            "sort_order": page.sort_order,
            "is_home": page.is_home,
            "show_in_navigation": page.show_in_navigation,
            "status": page.status,
            "content": deepcopy(page.content),
            "seo": deepcopy(page.seo),
        }
        for page in sorted(pages, key=lambda item: (item.sort_order, str(item.id)))
    ]


class RevisionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_document(
        self, website: Website, pages: list[WebsitePage]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        source = await self.session.get(TemplateVersion, website.source_template_version_id)
        if not source:
            raise problem(409, "source_template_missing", "The source Template version is missing.")
        source_document = source.document
        document_pages: list[dict[str, Any]] = []
        for page in sorted(
            pages,
            key=lambda item: (0 if item.is_home else 1, item.sort_order, str(item.id)),
        ):
            components = deepcopy(page.content.get("components") or _fallback_components(page))
            title = str(page.seo.get("title") or page.name).strip()[:60]
            description = str(
                page.seo.get("description") or f"Information about {page.name}"
            ).strip()[:160]
            document_pages.append(
                {
                    "id": f"p{page.id.hex}",
                    "slug": "home" if page.is_home else page.slug,
                    "label": page.name[:80],
                    "parent_page_id": (
                        f"p{page.parent_page_id.hex}" if page.parent_page_id else None
                    ),
                    "sort_order": page.sort_order,
                    "is_home": page.is_home,
                    "show_in_navigation": page.show_in_navigation,
                    "status": "ACTIVE" if page.status == "DRAFT" else "HIDDEN",
                    "seo": {"title": title, "description": description},
                    "components": components,
                }
            )
        document: dict[str, Any] = {
            "schema_version": source_document.get("schema_version", "1.0.0"),
            "registry_version": source_document.get("registry_version", "1.0.0"),
            "metadata": deepcopy(source_document["metadata"]),
            "theme": deepcopy(website.theme),
            "assets": deepcopy(source_document.get("assets", [])),
            "pages": document_pages,
            "features": deepcopy(source_document.get("features", [])),
            "requirements": _requirements(document_pages),
            "provenance": source_document.get("provenance", "CURATED"),
        }
        validation = validate_document(document)
        if not validation.valid:
            first = validation.errors[0] if validation.errors else {"code": "unknown"}
            raise problem(
                422,
                "website_document_invalid",
                f"The edit violates the Website document contract ({first['code']}).",
            )
        return document, validation.summary()

    async def capture(
        self,
        website: Website,
        pages: list[WebsitePage],
        *,
        source: str,
        actor_user_id: UUID,
        summary: str,
        operation_id: UUID | None = None,
        ai_operation_id: UUID | None = None,
        parent_version_id: UUID | None = None,
        document_override: dict[str, Any] | None = None,
        page_state_override: list[dict[str, Any]] | None = None,
    ) -> WebsiteVersion:
        if document_override is None:
            document, validation = await self.build_document(website, pages)
        else:
            document = deepcopy(document_override)
            result = validate_document(document)
            if not result.valid:
                raise problem(
                    422,
                    "website_document_invalid",
                    "The restored Website version no longer passes validation.",
                )
            validation = result.summary()
        revision = website.revision + 1
        version = WebsiteVersion(
            id=uuid4(),
            website_id=website.id,
            revision=revision,
            parent_version_id=parent_version_id or website.current_version_id,
            schema_version=str(document["schema_version"]),
            document=document,
            page_state=page_state_override or serialize_page_state(pages),
            checksum=str(validation["checksum"]),
            source=source,
            actor_user_id=actor_user_id,
            operation_id=operation_id,
            ai_operation_id=ai_operation_id,
            edit_summary=summary.strip()[:240],
            validation_status="VALID",
            validation_results=validation,
        )
        self.session.add(version)
        await self.session.flush([version])
        website.revision = revision
        website.current_version_id = version.id
        website.updated_at = datetime.now(UTC)
        await self.session.flush([website])
        return version

    async def current(self, website: Website) -> WebsiteVersion:
        if not website.current_version_id:
            raise problem(
                409,
                "website_revision_missing",
                "This Website has no current valid revision.",
            )
        version = await self.session.get(WebsiteVersion, website.current_version_id)
        if not version or version.website_id != website.id:
            raise problem(409, "website_revision_missing", "The current revision is unavailable.")
        return version

    async def history(self, website_id: UUID, limit: int = 50) -> list[WebsiteVersion]:
        return list(
            (
                await self.session.scalars(
                    select(WebsiteVersion)
                    .where(WebsiteVersion.website_id == website_id)
                    .order_by(WebsiteVersion.revision.desc())
                    .limit(limit)
                )
            ).all()
        )


class AiCreditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def account(self, user_id: UUID, *, lock: bool = False) -> AiCreditAccount:
        user = await self.session.get(User, user_id)
        if not user:
            raise problem(409, "ai_credit_account_missing", "AI credits are unavailable.")
        effective = await SubscriptionService(self.session).effective(
            user_id, user.billing_country_code
        )
        allowance = int(effective.entitlements["ai_monthly_credits"])
        created_user_id = await self.session.scalar(
            insert(AiCreditAccount)
            .values(
                user_id=user_id,
                balance=allowance,
                allowance=allowance,
                period_start=effective.period_start,
                period_end=effective.period_end,
            )
            .on_conflict_do_nothing(index_elements=[AiCreditAccount.user_id])
            .returning(AiCreditAccount.user_id)
        )
        if created_user_id is not None:
            self.session.add(
                AiCreditLedger(
                    user_id=user_id,
                    operation_id=uuid4(),
                    delta=allowance,
                    entry_type="MONTHLY_GRANT",
                    resulting_balance=allowance,
                    reason=f"{effective.bundle.plan.code} monthly AI allowance",
                )
            )
        statement = select(AiCreditAccount).where(AiCreditAccount.user_id == user_id)
        if lock:
            statement = statement.with_for_update()
        account = await self.session.scalar(statement)
        if not account:
            raise problem(409, "ai_credit_account_missing", "AI credits are unavailable.")
        period_changed = (
            account.period_start != effective.period_start
            or account.period_end != effective.period_end
        )
        allowance_changed = account.allowance != allowance
        if period_changed or allowance_changed:
            previous = account.balance
            if period_changed:
                account.balance = allowance
            else:
                used = max(0, account.allowance - account.balance)
                account.balance = max(0, allowance - used)
            account.allowance = allowance
            account.period_start = effective.period_start
            account.period_end = effective.period_end
            account.version += 1
            self.session.add(
                AiCreditLedger(
                    user_id=user_id,
                    operation_id=uuid4(),
                    delta=account.balance - previous,
                    entry_type="MONTHLY_GRANT",
                    resulting_balance=account.balance,
                    reason=f"{effective.bundle.plan.code} AI allowance synchronized",
                )
            )
        return account

    async def debit(self, user_id: UUID, operation_id: UUID, cost: int) -> AiCreditAccount:
        account = await self.account(user_id, lock=True)
        if cost <= 0:
            return account
        if account.balance < cost:
            raise problem(
                409,
                "ai_credits_insufficient",
                f"This change needs {cost} AI credits; {account.balance} remain.",
            )
        account.balance -= cost
        account.version += 1
        self.session.add(
            AiCreditLedger(
                user_id=user_id,
                operation_id=operation_id,
                delta=-cost,
                entry_type="AI_EDIT",
                resulting_balance=account.balance,
                reason="Validated AI Website edit",
            )
        )
        return account
