from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from zylora_api.db.website_models import Website
from zylora_api.modules.auth.errors import AuthProblem as ApiProblem
from zylora_api.modules.websites.service import WebsiteService

UTC = UTC


@pytest.mark.integration
@pytest.mark.asyncio
async def test_draft_cap_and_warnings(async_session, sample_user, sample_template_version):
    service = WebsiteService(async_session)

    # 1. Create 7 drafts -> normal status
    for i in range(7):
        w = Website(
            owner_user_id=sample_user.id,
            source_template_version_id=sample_template_version.id,
            site_origin="TEMPLATE",
            display_name=f"Draft {i + 1}",
            status="DRAFT",
            theme={},
        )
        async_session.add(w)
    await async_session.flush()

    total, warning, _ = await service.get_draft_status(sample_user.id)
    assert total == 7
    assert warning is None

    # 2. Add 8th draft -> warning at 8
    w8 = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Draft 8",
        status="DRAFT",
        theme={},
    )
    async_session.add(w8)
    await async_session.flush()

    total, warning, _ = await service.get_draft_status(sample_user.id)
    assert total == 8
    assert "8 of your 10 draft slots" in warning

    # 3. Add 9th and 10th drafts
    w9 = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Draft 9",
        status="DRAFT",
        theme={},
    )
    w10 = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Draft 10",
        status="DRAFT",
        theme={},
    )
    async_session.add_all([w9, w10])
    await async_session.flush()

    total, warning, _ = await service.get_draft_status(sample_user.id)
    assert total == 10
    assert "10-draft limit" in warning

    # 4. Attempt 11th draft via instantiate -> 409 draft_limit_reached
    with pytest.raises(ApiProblem) as exc_info:
        await service.instantiate("agency-starter", sample_user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.title == "draft_limit_reached"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oldest_untouched_draft_suggestion(
    async_session, sample_user, sample_template_version
):
    service = WebsiteService(async_session)
    now = datetime.now(UTC)

    # Draft A: created 10 days ago, updated yesterday
    draft_a = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Draft A (Recent Edit)",
        status="DRAFT",
        theme={},
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(days=1),
    )
    # Draft B: created 5 days ago, updated 30 days ago (oldest updated_at)
    draft_b = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Draft B (Oldest Untouched)",
        status="DRAFT",
        theme={},
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(days=30),
    )
    async_session.add_all([draft_a, draft_b])
    await async_session.flush()

    suggested = await service.suggest_draft_for_removal(sample_user.id)
    assert suggested is not None
    assert suggested.id == draft_b.id
    assert suggested.display_name == "Draft B (Oldest Untouched)"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_draft_deletion_safety(async_session, sample_user, sample_template_version):
    service = WebsiteService(async_session)

    # Draft
    draft = Website(
        owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Draft To Delete",
        status="DRAFT",
        theme={},
    )
    # Live Website
    live_site = Website(
        owner_user_id=sample_user.id,
        live_owner_user_id=sample_user.id,
        source_template_version_id=sample_template_version.id,
        site_origin="TEMPLATE",
        display_name="Live Website",
        status="PUBLISHED",
        theme={},
    )
    async_session.add_all([draft, live_site])
    await async_session.flush()

    # 1. Soft delete draft -> sets status = ARCHIVED
    archived = await service.delete_website(draft.id, sample_user.id)
    assert archived.status == "ARCHIVED"

    # 2. Delete live website -> must be rejected
    with pytest.raises(ApiProblem) as exc_info:
        await service.delete_website(live_site.id, sample_user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.title == "live_website_delete_forbidden"
