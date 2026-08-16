from __future__ import annotations

import pytest
from sqlalchemy import select
from zylora_api.db.lead_models import Lead
from zylora_api.modules.pro_leads.schemas import ProLeadCreateRequest
from zylora_api.modules.pro_leads.service import ProLeadService


@pytest.mark.asyncio
async def test_pro_lead_and_website_lead_isolation(
    async_session, sample_user, sample_template_version
):
    # 1. Create a ProLead (Zylora Pro enquiry)
    service = ProLeadService(async_session, None)
    pro_req = ProLeadCreateRequest(
        name="Pro Prospect",
        email="prospect@example.com",
        website_type="Enterprise SaaS Platform",
        preferred_contact_time="Morning",
    )
    pro_lead = await service.submit_pro_enquiry(
        pro_req, client_ip="127.0.0.1", correlation_id="iso1"
    )

    # 2. Query WebsiteLead table -> ProLead must NOT be in WebsiteLead
    website_leads = (await async_session.scalars(select(Lead))).all()
    assert not any(str(lead.id) == str(pro_lead.id) for lead in website_leads)

    # 3. Query ProLead table -> must contain ProLead
    pro_leads = await service.list_pro_leads()
    assert any(p.reference_id == pro_lead.reference_id for p in pro_leads)
