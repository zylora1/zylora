from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from zylora_api.modules.admin.operations import AdminOperationsService


class Rows:
    def __init__(self, values: object) -> None:
        self.values = values

    def all(self) -> object:
        return self.values

    def one(self) -> object:
        return self.values


class FakeSession:
    def __init__(
        self,
        *,
        scalar_values: list[object] | None = None,
        scalar_rows: list[list[object]] | None = None,
        execute_rows: list[object] | None = None,
        get_values: list[object] | None = None,
    ) -> None:
        self.scalar_values = scalar_values or []
        self.scalar_rows = scalar_rows or []
        self.execute_rows = execute_rows or []
        self.get_values = get_values or []

    async def scalar(self, _: object) -> object:
        return self.scalar_values.pop(0)

    async def scalars(self, _: object) -> Rows:
        return Rows(self.scalar_rows.pop(0))

    async def execute(self, _: object) -> Rows:
        return Rows(self.execute_rows.pop(0))

    async def get(self, _: object, __: object) -> object:
        return self.get_values.pop(0) if self.get_values else None


def fixtures() -> dict[str, object]:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    owner_id, website_id = uuid4(), uuid4()
    owner = SimpleNamespace(
        id=owner_id,
        account_type="USER",
        display_email="owner@example.com",
        status="ACTIVE",
        verified_at=now,
        created_at=now,
    )
    website = SimpleNamespace(
        id=website_id,
        display_name="Northstar",
        revision=4,
        status="PUBLISHED",
        updated_at=now,
        live_owner_user_id=owner_id,
    )
    subscription = SimpleNamespace(
        id=uuid4(),
        plan_code_snapshot="GROWTH",
        amount_minor=999,
        currency="INR",
        interval="MONTHLY",
        state="ACTIVE",
        updated_at=now,
        cancel_at_period_end=False,
    )
    payment = SimpleNamespace(
        id=uuid4(),
        purpose="SUBSCRIPTION",
        expected_amount_minor=999,
        expected_currency="INR",
        state="CAPTURED",
        created_at=now,
        trusted_at=now,
    )
    invoice = SimpleNamespace(
        id=uuid4(), number="ZYL-1", total_minor=999, currency="INR", state="PAID", issued_at=now
    )
    lead_credit_account = SimpleNamespace(id=uuid4(), balance=4, updated_at=now)
    ai_credit_account = SimpleNamespace(user_id=owner_id, balance=99, allowance=100, updated_at=now)
    lead_ledger = SimpleNamespace(
        id=uuid4(),
        entry_type="LEAD_CAPTURE",
        reason="VALID_LEAD_CAPTURED",
        created_at=now,
        delta=-1,
        resulting_balance=4,
    )
    ai_ledger = SimpleNamespace(
        id=uuid4(),
        entry_type="AI_EDIT",
        reason="AI_OPERATION",
        created_at=now,
        delta=-1,
        resulting_balance=99,
    )
    lead = SimpleNamespace(
        id=uuid4(),
        name="A visitor",
        source="FORM",
        page_path="/contact",
        status="NEW",
        captured_at=now,
        whatsapp_notification_queued=True,
    )
    domain = SimpleNamespace(
        id=uuid4(),
        display_hostname="northstar.zylora.test",
        type="ZYLORA_SUBDOMAIN",
        state="ACTIVE",
        updated_at=now,
        tls_status="ACTIVE",
        is_active=True,
    )
    audit = SimpleNamespace(
        id=uuid4(),
        event_type="website.published",
        target_type="website",
        target_id=str(website_id),
        reason="PUBLISH",
        correlation_id="correlation-1",
        occurred_at=now,
    )
    plan = SimpleNamespace(code="GROWTH", slot=3, most_popular=True, visible=True)
    price = SimpleNamespace(
        id=uuid4(),
        amount_minor=999,
        currency="INR",
        interval="MONTHLY",
        active=True,
        created_at=now,
    )
    entitlement = SimpleNamespace(
        id=uuid4(),
        capability_key="max_pages",
        value_type="INTEGER",
        value_bool=None,
        value_int=20,
        value_text=None,
    )
    email = SimpleNamespace(
        id=uuid4(),
        kind="WEBSITE_PUBLISHED",
        state="SENT",
        updated_at=now,
        attempts=1,
        last_error_code=None,
    )
    rollup = SimpleNamespace(
        id=uuid4(),
        bucket_date=date(2026, 8, 10),
        timezone="UTC",
        page_views=4,
        sessions=3,
        visitors=2,
        leads=1,
        conversions=1,
    )
    export_price = SimpleNamespace(
        id=uuid4(), currency="INR", amount_minor=49900, version=2, active=True, effective_at=now
    )
    return locals()


@pytest.mark.asyncio
async def test_admin_operations_projects_user_detail_with_all_required_state() -> None:
    data = fixtures()
    session = FakeSession(
        scalar_values=[data["owner"], 1, 1, data["website"], data["subscription"]],
        scalar_rows=[
            ["PASSWORD", "GOOGLE"],
            [data["website"]],
            [data["subscription"]],
            [data["payment"]],
            [data["invoice"]],
            [data["lead_ledger"]],
            [data["ai_ledger"]],
            [data["lead"]],
            [data["domain"]],
            [data["audit"]],
        ],
        get_values=[data["lead_credit_account"], data["ai_credit_account"]],
    )

    detail = await AdminOperationsService(session).user_detail(data["owner"].id)

    assert detail is not None
    assert detail.signup_methods == ["PASSWORD", "GOOGLE"]
    assert detail.live_website_name == "Northstar"
    assert {item.label for item in detail.payments} == {"SUBSCRIPTION", "Invoice · ZYL-1"}
    assert {item.label for item in detail.credit_ledger} >= {
        "Lead credit account",
        "AI credit account",
    }
    assert detail.leads[0].detail == "FORM on /contact"
    assert detail.domains[0].attributes["tls"] == "ACTIVE"
    assert detail.audit_activity[0].attributes["correlation_id"] == "correlation-1"


@pytest.mark.asyncio
async def test_admin_operations_projects_overview_users_and_every_operational_section() -> None:
    data = fixtures()
    overview = await AdminOperationsService(
        FakeSession(scalar_values=[2, 3, 1, 1, 4, 1, 2, 8, 1], execute_rows=[(12, 2)])
    ).overview()
    assert overview.page_views_last_30_days == 12 and overview.metrics[0].value == 2

    users = await AdminOperationsService(
        FakeSession(
            scalar_values=[1, 1, data["website"], data["subscription"]],
            scalar_rows=[[data["owner"]], ["PASSWORD"]],
        )
    ).users("owner", 25)
    assert users.items[0].plan_code == "GROWTH"

    website_records = await AdminOperationsService(
        FakeSession(execute_rows=[[(data["website"], data["owner"])]])
    ).section("websites", 25)
    assert website_records.items[0].attributes["live"] is True

    commerce_records = await AdminOperationsService(
        FakeSession(
            execute_rows=[
                [(data["plan"], data["price"])],
                [(data["subscription"], data["owner"])],
                [(data["payment"], data["owner"])],
                [(data["entitlement"], data["plan"])],
                [(data["invoice"], data["owner"])],
            ]
        )
    ).section("commerce", 25)
    assert {item.label for item in commerce_records.items} >= {
        "Plan price · GROWTH",
        "Invoice · ZYL-1",
    }

    lead_credit_records = await AdminOperationsService(
        FakeSession(
            execute_rows=[
                [(data["lead"], data["website"], data["owner"])],
                [(data["lead_ledger"], data["owner"])],
                [(data["ai_credit_account"], data["owner"])],
            ]
        )
    ).section("leads-credits", 25)
    assert {item.label for item in lead_credit_records.items} >= {
        "Lead · FORM",
        "AI credit account",
    }

    domain_records = await AdminOperationsService(
        FakeSession(execute_rows=[[(data["domain"], data["website"], data["owner"])]])
    ).section("domains", 25)
    assert domain_records.items[0].status == "ACTIVE"

    communication_records = await AdminOperationsService(
        FakeSession(execute_rows=[[(data["email"], data["owner"].display_email)]])
    ).section("communications", 25)
    assert communication_records.items[0].label == "WEBSITE_PUBLISHED"

    analytics_records = await AdminOperationsService(
        FakeSession(execute_rows=[[(data["rollup"], data["website"])]])
    ).section("analytics", 25)
    assert analytics_records.items[0].attributes["page_views"] == 4

    audit_records = await AdminOperationsService(
        FakeSession(execute_rows=[[(data["audit"], data["owner"].display_email)]])
    ).section("audit", 25)
    assert audit_records.items[0].detail == "owner@example.com"

    configuration_records = await AdminOperationsService(
        FakeSession(
            get_values=[SimpleNamespace(value={"policy": "REJECT_NEW"})],
            scalar_rows=[[data["export_price"]]],
        )
    ).section("configuration", 25)
    assert configuration_records.items[0].status == "REJECT_NEW"
