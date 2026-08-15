from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdminMetric(Schema):
    key: str
    label: str
    value: int


class AdminOverviewResponse(Schema):
    generated_at: datetime
    metrics: list[AdminMetric]
    analytics_window_start: date
    page_views_last_30_days: int
    leads_last_30_days: int


class AdminFunnelStep(Schema):
    key: str
    label: str
    count: int
    conversion_percent: float | None


class AdminRetentionMetric(Schema):
    days: int
    eligible_accounts: int
    retained_accounts: int
    retention_percent: float


class AdminGrowthResponse(Schema):
    range_days: int | None
    funnel: list[AdminFunnelStep]
    active_value_sites_30d: int
    previous_active_value_sites_30d: int
    active_value_sites_change_percent: float | None
    retention: list[AdminRetentionMetric]
    published_with_first_lead: int
    published_with_zero_leads: int
    paid_with_first_lead: int
    paid_with_zero_leads: int
    subscription_state_counts: dict[str, int]


class AdminRecord(Schema):
    id: UUID | str
    label: str
    detail: str | None = None
    status: str | None = None
    occurred_at: datetime | date | None = None
    attributes: dict[str, str | int | bool | None] = Field(default_factory=dict)


class AdminOperationListResponse(Schema):
    section: Literal[
        "websites",
        "commerce",
        "leads-credits",
        "domains",
        "communications",
        "analytics",
        "audit",
        "configuration",
    ]
    items: list[AdminRecord]


class AdminUserSummary(Schema):
    id: UUID
    email: str
    status: str
    signup_methods: list[str]
    verified_at: datetime | None
    created_at: datetime
    website_count: int
    draft_count: int
    live_website_id: UUID | None
    live_website_name: str | None
    plan_code: str | None
    subscription_state: str | None


class AdminUserListResponse(Schema):
    items: list[AdminUserSummary]


class AdminUserDetail(AdminUserSummary):
    websites: list[AdminRecord]
    subscriptions: list[AdminRecord]
    payments: list[AdminRecord]
    credit_ledger: list[AdminRecord]
    leads: list[AdminRecord]
    domains: list[AdminRecord]
    audit_activity: list[AdminRecord]


class AdminHealthResponse(Schema):
    status: Literal["ready", "degraded", "not_ready"]
    checks: dict[str, str]
    observed_at: datetime
