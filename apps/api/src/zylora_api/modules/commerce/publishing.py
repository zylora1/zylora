from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website, WebsitePage
from zylora_api.modules.commerce.schemas import (
    EligibilityReasonResponse,
    PlanEligibilityResponse,
    PublishCommandResponse,
    PublishEvaluationResponse,
    UnpublishCommandResponse,
)
from zylora_api.modules.commerce.service import (
    CatalogService,
    SubscriptionService,
)
from zylora_api.modules.publishing.service import DeploymentService
from zylora_api.modules.templates.service import problem


@dataclass(frozen=True)
class WebsiteRequirements:
    page_count: int
    domain_type: str


def _plan_reasons(
    entitlements: dict[str, bool | int | str], requirements: WebsiteRequirements
) -> list[EligibilityReasonResponse]:
    reasons: list[EligibilityReasonResponse] = []
    if entitlements.get("can_publish") is not True:
        reasons.append(
            EligibilityReasonResponse(
                code="PUBLISHING_NOT_INCLUDED",
                detail="This plan cannot publish a Website.",
                current=True,
                allowed=False,
            )
        )
    max_pages = entitlements.get("max_pages")
    if isinstance(max_pages, int) and requirements.page_count > max_pages:
        reasons.append(
            EligibilityReasonResponse(
                code="PAGE_LIMIT_EXCEEDED",
                detail=(
                    f"This Website has {requirements.page_count} pages; this plan allows up to "
                    f"{max_pages}. Your Draft is unchanged."
                ),
                current=requirements.page_count,
                allowed=max_pages,
            )
        )
    if requirements.domain_type == "CUSTOM" and entitlements.get("custom_domain") is not True:
        reasons.append(
            EligibilityReasonResponse(
                code="CUSTOM_DOMAIN_NOT_INCLUDED",
                detail="This plan supports a Zylora subdomain, not a custom domain.",
                current="CUSTOM",
                allowed="ZYLORA_SUBDOMAIN",
            )
        )
    return reasons


class PublishEligibilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.catalogs = CatalogService(session)
        self.subscriptions = SubscriptionService(session)

    async def evaluate(
        self,
        website_id: UUID,
        owner_user_id: UUID,
        country_code: str,
        domain_type: str,
    ) -> PublishEvaluationResponse:
        website = await self.session.scalar(
            select(Website).where(
                Website.id == website_id,
                Website.owner_user_id == owner_user_id,
            )
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        return await self._evaluate(website, owner_user_id, country_code, domain_type)

    async def _evaluate(
        self,
        website: Website,
        owner_user_id: UUID,
        country_code: str,
        domain_type: str,
    ) -> PublishEvaluationResponse:
        if domain_type not in {"ZYLORA_SUBDOMAIN", "CUSTOM"}:
            raise problem(422, "invalid_domain_type", "Choose a supported domain type.")
        page_count = int(
            await self.session.scalar(
                select(func.count(WebsitePage.id)).where(
                    WebsitePage.website_id == website.id,
                    WebsitePage.status != "ARCHIVED",
                )
            )
            or 0
        )
        requirements = WebsiteRequirements(page_count, domain_type)
        bundles = await self.catalogs.current(country_code)
        effective = await self.subscriptions.effective(owner_user_id, country_code)
        another_live = await self.session.scalar(
            select(Website.id).where(
                Website.live_owner_user_id == owner_user_id,
                Website.id != website.id,
            )
        )
        current_reasons = _plan_reasons(effective.entitlements, requirements)
        plan_results: list[PlanEligibilityResponse] = []
        for bundle in bundles:
            reasons = _plan_reasons(bundle.entitlements, requirements)
            if another_live:
                reasons.append(
                    EligibilityReasonResponse(
                        code="ANOTHER_WEBSITE_LIVE",
                        detail="Unpublish your current live Website before publishing this one.",
                    )
                )
            plan_results.append(
                PlanEligibilityResponse(
                    plan=bundle.response(),
                    eligible=not reasons,
                    reasons=reasons,
                    is_current_plan=bundle.plan.code == effective.bundle.plan.code,
                )
            )
        current_eligible = not current_reasons and not another_live
        eligible_codes = [item.plan.code for item in plan_results if item.eligible]
        if another_live or not eligible_codes:
            status = "INELIGIBLE"
        elif current_eligible:
            status = "ELIGIBLE"
        else:
            status = "UPGRADE_REQUIRED"
        return PublishEvaluationResponse(
            website_id=website.id,
            page_count=page_count,
            domain_type=domain_type,
            current_plan_code=effective.bundle.plan.code,
            reuse_existing_subscription=current_eligible,
            can_request_publish=current_eligible,
            status=status,
            recommended_plan_code=eligible_codes[0] if eligible_codes else None,
            plans=plan_results,
        )


class PublishService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.eligibility = PublishEligibilityService(session)

    async def request_publish(
        self,
        website_id: UUID,
        owner_user_id: UUID,
        country_code: str,
        domain_type: str,
        idempotency_key: str,
        correlation_id: str,
        hostname: str | None = None,
    ) -> PublishCommandResponse:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:owner, 0))"),
            {"owner": str(owner_user_id)},
        )
        website = await self.session.scalar(
            select(Website)
            .where(Website.id == website_id, Website.owner_user_id == owner_user_id)
            .with_for_update()
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        if (
            website.status == "PUBLISHING"
            and website.publish_request_idempotency_key == idempotency_key
        ):
            effective = await SubscriptionService(self.session).effective(
                owner_user_id, country_code
            )
            return PublishCommandResponse(
                website_id=website.id,
                status="PUBLISHING",
                plan_code=effective.bundle.plan.code,
                reused_existing_subscription=True,
                message="Publication is already reserved and awaiting deployment.",
            )
        if website.status not in {"DRAFT", "UNPUBLISHED", "FAILED"}:
            raise problem(409, "invalid_website_state", "This Website cannot be published now.")
        evaluation = await self.eligibility._evaluate(
            website, owner_user_id, country_code, domain_type
        )
        if not evaluation.can_request_publish:
            if evaluation.status == "UPGRADE_REQUIRED":
                raise problem(
                    409,
                    "upgrade_required",
                    "Your current plan does not meet this Website's publishing requirements.",
                )
            raise problem(
                409,
                "publish_ineligible",
                "This Website is not currently eligible to publish.",
            )
        deployment = await DeploymentService(self.session).queue_publish(
            website,
            domain_type,
            hostname,
            idempotency_key,
            correlation_id,
        )
        return PublishCommandResponse(
            website_id=website.id,
            deployment_id=deployment.id,
            domain_id=deployment.domain_id,
            status="PUBLISHING",
            plan_code=evaluation.current_plan_code,
            reused_existing_subscription=True,
            message="Eligibility is reserved. Deployment and health verification run next.",
        )

    async def request_unpublish(
        self, website_id: UUID, owner_user_id: UUID, correlation_id: str
    ) -> UnpublishCommandResponse:
        website = await self.session.scalar(
            select(Website)
            .where(Website.id == website_id, Website.owner_user_id == owner_user_id)
            .with_for_update()
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        if website.status == "PUBLISHING":
            await DeploymentService(self.session).cancel_pending_publish(website, correlation_id)
            website.status = "DRAFT"
            website.live_owner_user_id = None
            website.published_version_id = None
            website.publication_domain_type = None
            website.publish_request_idempotency_key = None
            return UnpublishCommandResponse(
                website_id=website.id,
                status="DRAFT",
                message="The pending publication was cancelled safely.",
            )
        if website.status != "PUBLISHED":
            raise problem(409, "website_not_live", "This Website is not live.")
        website.status = "UNPUBLISHING"
        self.session.add(
            OutboxEvent(
                aggregate_type="WEBSITE",
                aggregate_id=website.id,
                event_type="website.unpublish_requested",
                payload={"website_id": str(website.id), "owner_user_id": str(owner_user_id)},
                correlation_id=correlation_id,
            )
        )
        return UnpublishCommandResponse(
            website_id=website.id,
            status="UNPUBLISHING",
            message="Public routing is being disabled. The live slot releases after confirmation.",
        )

    async def complete_unpublish(self, website_id: UUID) -> Website:
        website = await self.session.scalar(
            select(Website).where(Website.id == website_id).with_for_update()
        )
        if not website or website.status != "UNPUBLISHING":
            raise problem(409, "invalid_website_state", "Unpublish confirmation is not expected.")
        website.status = "UNPUBLISHED"
        website.live_owner_user_id = None
        website.publication_domain_type = None
        website.publish_request_idempotency_key = None
        return website
