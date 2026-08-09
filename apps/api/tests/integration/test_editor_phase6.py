from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from zylora_api.db.auth_models import User
from zylora_api.db.session import get_engine
from zylora_api.db.website_models import AiCreditAccount, AiOperation
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.editor.provider import (
    AiPlanningError,
    PlannerResult,
    PlanningContext,
)
from zylora_api.modules.editor.revisions import AiCreditService, RevisionService
from zylora_api.modules.editor.schemas import AiEditRequest, EditPlan, ManualEditRequest
from zylora_api.modules.editor.service import EditorService
from zylora_api.modules.templates.schemas import TemplateCreateRequest
from zylora_api.modules.templates.service import TemplateService
from zylora_api.modules.websites.service import WebsiteService, page_paths


def website_document(page_count: int = 5) -> dict[str, object]:
    pages: list[dict[str, object]] = []
    labels = ["Home", "About", "Services", "Resources", "Testimonials"]
    for index in range(page_count):
        page_id = f"page-{index}"
        label = labels[index] if index < len(labels) else f"Page {index}"
        pages.append(
            {
                "id": page_id,
                "slug": "home" if index == 0 else f"page-{index}",
                "label": label,
                "parent_page_id": None,
                "sort_order": index,
                "is_home": index == 0,
                "show_in_navigation": True,
                "status": "ACTIVE",
                "seo": {
                    "title": label,
                    "description": f"Useful information about {label}.",
                },
                "components": [
                    {
                        "id": f"hero-{index}",
                        "type": "HERO",
                        "props": {"heading": label, "body": f"Welcome to {label}."},
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    }
                ],
            }
        )
    return {
        "schema_version": "1.0.0",
        "registry_version": "1.0.0",
        "metadata": {
            "name": "Phase 6 Editor Template",
            "description": "A template for revision-safe AI editing tests.",
            "language": "en",
        },
        "theme": {
            "primary": "#5B5BD6",
            "accent": "#27C499",
            "surface": "#FFFFFF",
            "ink": "#171A2B",
            "heading_font": "MANROPE",
            "body_font": "INTER",
        },
        "assets": [],
        "pages": pages,
        "features": [],
        "requirements": [],
        "provenance": "CURATED",
    }


async def draft_fixture(session: AsyncSession, page_count: int = 5) -> tuple[User, User, object]:
    unique = uuid4().hex
    users = [
        User(
            account_type="USER",
            normalized_email=f"phase6-{unique}-{index}@example.com",
            display_email=f"phase6-{unique}-{index}@example.com",
            status="ACTIVE",
            verified_at=datetime.now(UTC),
        )
        for index in range(2)
    ]
    session.add_all(users)
    await session.flush()
    slug = f"phase6-{unique}"
    templates = TemplateService(session, AuthCrypto("phase6-editor-test-secret-long-enough"))
    template = await templates.create(
        TemplateCreateRequest(
            slug=slug,
            name="Phase 6 Editor",
            summary="Revision-safe editor fixture.",
            category_slug=f"{slug}-category",
            category_name="Editor",
            category_description="Editor integration fixtures.",
            tags=[f"{slug}-tag"],
            featured_order=100,
        ),
        users[0].id,
    )
    await templates.add_version(template.id, website_document(page_count), users[0].id)
    assert (await templates.validate(template.id, 1, users[0].id)).status == "VALIDATED"
    await templates.approve(template.id, 1)
    await templates.publish(template.id, 1)
    website = await WebsiteService(session).instantiate(slug, users[0].id)
    await session.flush()
    return users[0], users[1], website


@dataclass
class FakePlanner:
    plan_value: EditPlan | None = None
    error: AiPlanningError | None = None

    async def plan(
        self,
        request: AiEditRequest,
        context: PlanningContext,
        safety_identifier: str,
    ) -> PlannerResult:
        assert context.page_graph and safety_identifier
        if self.error:
            raise self.error
        assert self.plan_value is not None
        return PlannerResult(
            plan=self.plan_value,
            provider="TEST",
            model="deterministic-editor",
            usage={"input_tokens": 100, "output_tokens": 25},
            latency_ms=5,
        )


def ai_request(
    revision: int, prompt: str, scope: str = "WEBSITE", page_id: UUID | None = None
) -> AiEditRequest:
    return AiEditRequest(
        operation_id=uuid4(),
        base_revision=revision,
        prompt=prompt,
        scope=scope,
        selected_page_id=page_id,
    )


@pytest.mark.integration
async def test_manual_and_ai_edits_share_revisions_scope_and_restore() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, _other, website = await draft_fixture(session)
        pages = await WebsiteService(session).pages(website.id)
        about = next(page for page in pages if page.name == "About")
        result = await EditorService(session).manual_edit(
            website.id,
            owner.id,
            ManualEditRequest(
                operation_id=uuid4(),
                base_revision=website.revision,
                scope="PAGE",
                selected_page_id=about.id,
                summary="Rewrite About heading and add a premium section",
                operations=[
                    {
                        "kind": "SET_COMPONENT_PROP",
                        "page_id": about.id,
                        "component_id": "hero-1",
                        "property": "heading",
                        "value": "A more human studio",
                    },
                    {
                        "kind": "INSERT_COMPONENT",
                        "page_id": about.id,
                        "component_type": "SECTION",
                        "position": 1,
                        "heading": "How we work",
                        "body": "Focused, transparent, and built for measurable outcomes.",
                        "items": [],
                    },
                ],
            ),
        )
        assert result.version.revision == 2 and result.version.source == "MANUAL"
        assert (
            result.version.document["pages"][1]["components"][0]["props"]["heading"]
            == "A more human studio"
        )

        services = next(page for page in pages if page.name == "Services")
        with pytest.raises(AuthProblem) as scope_error:
            await EditorService(session).manual_edit(
                website.id,
                owner.id,
                ManualEditRequest(
                    operation_id=uuid4(),
                    base_revision=website.revision,
                    scope="PAGE",
                    selected_page_id=about.id,
                    summary="Wrong-page edit",
                    operations=[
                        {
                            "kind": "SET_COMPONENT_PROP",
                            "page_id": services.id,
                            "component_id": "hero-2",
                            "property": "heading",
                            "value": "Should not apply",
                        }
                    ],
                ),
            )
        assert scope_error.value.code == "ai_scope_violation"

        first = (await RevisionService(session).history(website.id))[-1]
        restored = await EditorService(session).restore(
            website.id, owner.id, first.id, uuid4(), website.revision
        )
        assert restored.version.source == "RESTORE" and restored.version.revision == 3
        restored_about = next(
            page for page in await WebsiteService(session).pages(website.id) if page.name == "About"
        )
        assert restored_about.content["components"][0]["props"]["heading"] == "About"
        await session.rollback()


@pytest.mark.integration
async def test_ai_page_graph_validation_rollback_metering_and_authorization() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, other, website = await draft_fixture(session)
        await session.commit()
        pages = await WebsiteService(session).pages(website.id)
        services = next(page for page in pages if page.name == "Services")
        about = next(page for page in pages if page.name == "About")
        testimonials = next(page for page in pages if page.name == "Testimonials")
        editor = EditorService(session)

        add_plan = EditPlan(
            summary="Add Dental Implants under Services",
            operations=[
                {
                    "kind": "ADD_PAGE",
                    "name": "Dental Implants",
                    "slug": "dental-implants",
                    "parent_page_id": services.id,
                    "show_in_navigation": True,
                    "heading": "Dental implants",
                    "body": "Restore comfort and confidence with a durable treatment plan.",
                    "section_type": "STANDARD",
                    "items": [],
                }
            ],
        )
        added = await editor.ai_edit(
            website.id,
            owner.id,
            ai_request(website.revision, "Add a Dental Implants page under Services."),
            FakePlanner(add_plan),
            "safe-owner",
        )
        await session.commit()
        assert added.credits_used == 8
        pages = await WebsiteService(session).pages(website.id)
        dental = next(page for page in pages if page.name == "Dental Implants")
        assert page_paths(pages)[dental.id] == "/page-2/dental-implants"
        assert dental.parent_page_id == services.id and dental.show_in_navigation
        account = await AiCreditService(session).account(owner.id)
        assert account.balance == 7 and account.allowance == 15

        move_plan = EditPlan(
            summary="Move Testimonials under About",
            operations=[
                {
                    "kind": "MOVE_PAGE",
                    "page_id": testimonials.id,
                    "parent_page_id": about.id,
                    "position": 0,
                }
            ],
        )
        moved = await editor.ai_edit(
            website.id,
            owner.id,
            ai_request(added.version.revision, "Move Testimonials under About."),
            FakePlanner(move_plan),
            "safe-owner",
        )
        await session.commit()
        assert moved.credits_used == 2
        pages = await WebsiteService(session).pages(website.id)
        assert page_paths(pages)[testimonials.id] == "/page-1/page-4"

        owner_id = owner.id
        other_id = other.id
        website_id = website.id
        services_id = services.id
        dental_id = dental.id
        about_id = about.id
        revision_before_failure = website.revision
        balance_before_failure = (await AiCreditService(session).account(owner.id)).balance
        invalid_request = ai_request(website.revision, "Add an invalid page")
        with pytest.raises(AuthProblem) as invalid:
            await editor.ai_edit(
                website.id,
                owner.id,
                invalid_request,
                FakePlanner(
                    EditPlan(
                        summary="Invalid slug attempt",
                        operations=[
                            {
                                "kind": "ADD_PAGE",
                                "name": "Bad route",
                                "slug": "Bad Slug",
                                "show_in_navigation": False,
                                "heading": "Bad route",
                                "body": "This must be rejected before apply.",
                            }
                        ],
                    )
                ),
                "safe-owner",
            )
        assert invalid.value.code == "invalid_page_slug"
        await session.refresh(website)
        assert website.revision == revision_before_failure
        assert (await AiCreditService(session).account(owner_id)).balance == balance_before_failure
        failed = await session.get(AiOperation, invalid_request.operation_id)
        assert failed is not None and failed.status == "FAILED" and failed.cost_credits == 0

        cycle_request = ai_request(revision_before_failure, "Nest Services under its child")
        with pytest.raises(AuthProblem) as cycle:
            await editor.ai_edit(
                website_id,
                owner_id,
                cycle_request,
                FakePlanner(
                    EditPlan(
                        summary="Cycle attempt",
                        operations=[
                            {
                                "kind": "MOVE_PAGE",
                                "page_id": services_id,
                                "parent_page_id": dental_id,
                                "position": 0,
                            }
                        ],
                    )
                ),
                "safe-owner",
            )
        assert cycle.value.code == "page_hierarchy_cycle"

        provider_request = ai_request(revision_before_failure, "Rewrite this heading")
        with pytest.raises(AuthProblem) as provider_failure:
            await editor.ai_edit(
                website_id,
                owner_id,
                provider_request,
                FakePlanner(error=AiPlanningError("provider_down", "Provider unavailable.")),
                "safe-owner",
            )
        assert provider_failure.value.code == "provider_down"

        account = await session.get(AiCreditAccount, owner_id)
        assert account is not None
        account.balance = 0
        await session.commit()
        insufficient_request = ai_request(revision_before_failure, "Rewrite the About heading")
        with pytest.raises(AuthProblem) as insufficient:
            await editor.ai_edit(
                website_id,
                owner_id,
                insufficient_request,
                FakePlanner(
                    EditPlan(
                        summary="Rewrite heading",
                        operations=[
                            {
                                "kind": "SET_COMPONENT_PROP",
                                "page_id": about_id,
                                "component_id": "hero-1",
                                "property": "heading",
                                "value": "A heading without credits",
                            }
                        ],
                    )
                ),
                "safe-owner",
            )
        assert insufficient.value.code == "ai_credits_insufficient"
        assert (await AiCreditService(session).account(owner_id)).balance == 0

        unauthorized_request = ai_request(revision_before_failure, "Change another user's site")
        with pytest.raises(AuthProblem) as unauthorized:
            await editor.ai_edit(
                website_id,
                other_id,
                unauthorized_request,
                FakePlanner(add_plan),
                "safe-other",
            )
        assert unauthorized.value.code == "website_not_found"


@pytest.mark.integration
async def test_ai_page_graph_handles_one_hundred_page_draft_without_plan_gate() -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        owner, _other, website = await draft_fixture(session, page_count=100)
        await session.commit()
        pages = await WebsiteService(session).pages(website.id)
        parent = next(page for page in pages if page.source_template_page_id == "page-99")
        result = await EditorService(session).ai_edit(
            website.id,
            owner.id,
            ai_request(website.revision, "Add a child beneath the final directory page."),
            FakePlanner(
                EditPlan(
                    summary="Add final directory child",
                    operations=[
                        {
                            "kind": "ADD_PAGE",
                            "name": "Final directory child",
                            "slug": "final-child",
                            "parent_page_id": parent.id,
                            "show_in_navigation": False,
                            "heading": "Final directory child",
                            "body": "A safely nested page in a large Draft Website.",
                        }
                    ],
                )
            ),
            "safe-large-owner",
        )
        await session.commit()
        pages = await WebsiteService(session).pages(website.id)
        child = next(page for page in pages if page.name == "Final directory child")
        assert len(pages) == 101
        assert page_paths(pages)[child.id] == "/page-99/final-child"
        assert result.version.revision == 2 and website.status == "DRAFT"
