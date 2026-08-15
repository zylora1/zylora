from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicPageViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,160}$")
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,160}$")
    visitor_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,160}$")
    page_path: str = Field(min_length=1, max_length=1024, pattern=r"^/")


class PublicWebsiteEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,160}$")
    event_type: str = Field(pattern=r"^LEAD_FORM_OPENED$")
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,160}$")
    page_path: str = Field(min_length=1, max_length=1024, pattern=r"^/")


class PublicPageViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    duplicate: bool


class AnalyticsPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    page_views: int
    sessions: int
    visitors: int
    leads: int
    lead_form_opens: int
    lead_form_submissions: int
    form_leads: int
    chatbot_leads: int
    chatbot_conversations: int
    chatbot_messages: int
    conversions: int


class AnalyticsDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website_id: UUID | None
    timezone: str
    period_days: int
    has_published_website: bool
    has_meaningful_data: bool
    page_views: int
    sessions: int
    visitors: int
    leads: int
    lead_form_opens: int
    lead_form_submissions: int
    form_leads: int
    chatbot_leads: int
    chatbot_conversations: int
    chatbot_messages: int
    conversions: int
    lead_conversion_rate: float
    published_at: datetime | None
    first_visitor_at: datetime | None
    first_lead_at: datetime | None
    time_to_first_lead_seconds: int | None
    previous_page_views: int
    previous_leads: int
    page_view_change_percent: float | None
    lead_change_percent: float | None
    zero_lead_recommendations: list[str]
    points: list[AnalyticsPointResponse]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    type: str
    title: str
    body: str
    href: str
    state: str
    read_at: datetime | None
    created_at: datetime


class NotificationPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notifications: list[NotificationResponse]
    unread_count: int
    next_cursor: datetime | None
