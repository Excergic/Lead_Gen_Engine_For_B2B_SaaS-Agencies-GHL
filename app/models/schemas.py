from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class ClientStatus(StrEnum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    CHURNED = "churned"


class ICPTemplate(StrEnum):
    SAAS_FOUNDERS = "saas_founders"
    OUTBOUND_AGENCIES = "outbound_agencies"
    GHL_SAASPRENEURS = "ghl_saaspreneurs"
    CUSTOM = "custom"


class TimestampedModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    contact_email: EmailStr | None = None


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    contact_email: EmailStr | None = None
    status: ClientStatus | None = None


class ClientResponse(TimestampedModel):
    name: str
    company_name: str | None
    contact_email: str | None
    status: ClientStatus


# ---------------------------------------------------------------------------
# Stage 1 definition
# ---------------------------------------------------------------------------
class DefinitionUpsert(BaseModel):
    offer_headline: str | None = Field(default=None, max_length=500)
    offer_description: str | None = Field(default=None, max_length=5000)
    value_proposition: str | None = Field(default=None, max_length=2000)
    calendar_url: HttpUrl | None = None
    messaging_dos: list[str] = Field(default_factory=list, max_length=50)
    messaging_donts: list[str] = Field(default_factory=list, max_length=50)
    pain_points: list[str] = Field(default_factory=list, max_length=30)


class DefinitionResponse(TimestampedModel):
    client_id: UUID
    version: int
    is_active: bool
    offer_headline: str | None
    offer_description: str | None
    value_proposition: str | None
    calendar_url: str | None
    messaging_dos: list[str]
    messaging_donts: list[str]
    pain_points: list[str]
    stage1_complete: bool
    completed_at: datetime | None


# ---------------------------------------------------------------------------
# ICP profiles
# ---------------------------------------------------------------------------
class ICPProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icp_template: ICPTemplate = ICPTemplate.CUSTOM
    is_primary: bool = False
    titles: list[str] = Field(default_factory=list, max_length=30)
    company_size_min: int | None = Field(default=None, ge=1)
    company_size_max: int | None = Field(default=None, ge=1)
    arr_min: int | None = Field(default=None, ge=0)
    arr_max: int | None = Field(default=None, ge=0)
    industries: list[str] = Field(default_factory=list, max_length=30)
    geographies: list[str] = Field(default_factory=list, max_length=30)
    funding_stages: list[str] = Field(default_factory=list, max_length=20)
    extra_filters: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)


class ICPProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    icp_template: ICPTemplate | None = None
    is_primary: bool | None = None
    titles: list[str] | None = Field(default=None, max_length=30)
    company_size_min: int | None = Field(default=None, ge=1)
    company_size_max: int | None = Field(default=None, ge=1)
    arr_min: int | None = Field(default=None, ge=0)
    arr_max: int | None = Field(default=None, ge=0)
    industries: list[str] | None = Field(default=None, max_length=30)
    geographies: list[str] | None = Field(default=None, max_length=30)
    funding_stages: list[str] | None = Field(default=None, max_length=20)
    extra_filters: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ICPProfileResponse(TimestampedModel):
    client_id: UUID
    definition_id: UUID | None
    name: str
    icp_template: ICPTemplate
    is_primary: bool
    titles: list[str]
    company_size_min: int | None
    company_size_max: int | None
    arr_min: int | None
    arr_max: int | None
    industries: list[str]
    geographies: list[str]
    funding_stages: list[str]
    extra_filters: dict[str, Any]
    notes: str | None


# ---------------------------------------------------------------------------
# Case studies
# ---------------------------------------------------------------------------
class CaseStudyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    subject_name: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=200)
    challenge: str | None = Field(default=None, max_length=3000)
    solution: str | None = Field(default=None, max_length=3000)
    result: str | None = Field(default=None, max_length=3000)
    metrics: dict[str, Any] = Field(default_factory=dict)
    is_featured: bool = False
    sort_order: int = 0


class CaseStudyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    subject_name: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=200)
    challenge: str | None = Field(default=None, max_length=3000)
    solution: str | None = Field(default=None, max_length=3000)
    result: str | None = Field(default=None, max_length=3000)
    metrics: dict[str, Any] | None = None
    is_featured: bool | None = None
    sort_order: int | None = None


class CaseStudyResponse(TimestampedModel):
    client_id: UUID
    definition_id: UUID | None
    title: str
    subject_name: str | None
    industry: str | None
    challenge: str | None
    solution: str | None
    result: str | None
    metrics: dict[str, Any]
    is_featured: bool
    sort_order: int


# ---------------------------------------------------------------------------
# Stage 1 aggregate
# ---------------------------------------------------------------------------
class Stage1Checklist(BaseModel):
    has_definition: bool
    has_calendar_url: bool
    has_offer: bool
    has_pain_points: bool
    has_primary_icp: bool
    has_case_study: bool
    ready: bool
    missing: list[str]


class Stage1BundleResponse(BaseModel):
    client: ClientResponse
    definition: DefinitionResponse | None
    icp_profiles: list[ICPProfileResponse]
    case_studies: list[CaseStudyResponse]
    checklist: Stage1Checklist


# ---------------------------------------------------------------------------
# Campaigns & dashboard
# ---------------------------------------------------------------------------
class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icp_profile_id: UUID | None = None
    status: CampaignStatus = CampaignStatus.DRAFT


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    icp_profile_id: UUID | None = None
    status: CampaignStatus | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class CampaignMetricsUpdate(BaseModel):
    prospects_discovered: int | None = Field(default=None, ge=0)
    prospects_enriched: int | None = Field(default=None, ge=0)
    prospects_contacted: int | None = Field(default=None, ge=0)
    emails_sent: int | None = Field(default=None, ge=0)
    emails_opened: int | None = Field(default=None, ge=0)
    emails_replied: int | None = Field(default=None, ge=0)
    linkedin_sent: int | None = Field(default=None, ge=0)
    linkedin_replied: int | None = Field(default=None, ge=0)
    positive_replies: int | None = Field(default=None, ge=0)
    meetings_booked: int | None = Field(default=None, ge=0)
    meetings_held: int | None = Field(default=None, ge=0)
    bounces: int | None = Field(default=None, ge=0)
    unsubscribes: int | None = Field(default=None, ge=0)


class CampaignResponse(TimestampedModel):
    client_id: UUID
    icp_profile_id: UUID | None
    name: str
    status: CampaignStatus
    prospects_discovered: int
    prospects_enriched: int
    prospects_contacted: int
    emails_sent: int
    emails_opened: int
    emails_replied: int
    linkedin_sent: int
    linkedin_replied: int
    positive_replies: int
    meetings_booked: int
    meetings_held: int
    bounces: int
    unsubscribes: int
    started_at: datetime | None
    ended_at: datetime | None


class CampaignRates(BaseModel):
    email_open_rate_pct: float
    email_reply_rate_pct: float
    meeting_conversion_rate_pct: float
    positive_reply_rate_pct: float


class CampaignSummary(CampaignResponse):
    rates: CampaignRates


class DailyMetricsUpsert(BaseModel):
    metric_date: date
    prospects_added: int = Field(default=0, ge=0)
    emails_sent: int = Field(default=0, ge=0)
    emails_opened: int = Field(default=0, ge=0)
    emails_replied: int = Field(default=0, ge=0)
    linkedin_sent: int = Field(default=0, ge=0)
    linkedin_replied: int = Field(default=0, ge=0)
    positive_replies: int = Field(default=0, ge=0)
    meetings_booked: int = Field(default=0, ge=0)
    meetings_held: int = Field(default=0, ge=0)


class DailyMetricsResponse(TimestampedModel):
    campaign_id: UUID
    metric_date: datetime
    prospects_added: int
    emails_sent: int
    emails_opened: int
    emails_replied: int
    linkedin_sent: int
    linkedin_replied: int
    positive_replies: int
    meetings_booked: int
    meetings_held: int


class ClientDashboardTotals(BaseModel):
    active_campaigns: int
    total_emails_sent: int
    total_emails_replied: int
    total_positive_replies: int
    total_meetings_booked: int
    total_meetings_held: int
    email_reply_rate_pct: float
    meeting_conversion_rate_pct: float


class ClientDashboardResponse(BaseModel):
    client_id: UUID
    totals: ClientDashboardTotals
    campaigns: list[CampaignSummary]
    daily_trend: list[DailyMetricsResponse]


# ---------------------------------------------------------------------------
# Discover (Stage 2)
# ---------------------------------------------------------------------------
class DiscoverRunRequest(BaseModel):
    max_results: int = Field(default=5, ge=1, le=20)
    icp_ids: list[str] | None = None
    persist: bool = True


class DiscoverRunResponse(BaseModel):
    discovered: int
    saved_new: int
    tools_used: list[str]
    leads: list[dict[str, Any]]


class EnrichRunRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    persist: bool = True


class EnrichSummary(BaseModel):
    total: int
    enriched_status: int
    with_email: int
    with_linkedin: int
    avg_confidence: float


class EnrichRunResponse(BaseModel):
    processed: int
    saved: int
    summary: EnrichSummary
    leads: list[dict[str, Any]]
    message: str | None = None


# ---------------------------------------------------------------------------
# Stage 5 — Personalize + HITL outreach
# ---------------------------------------------------------------------------
class PersonalizeRunRequest(BaseModel):
    limit: int = Field(default=3, ge=1, le=10)
    client_id: UUID | None = None
    lead_ids: list[str] | None = None


class PersonalizeRunResponse(BaseModel):
    processed: int
    queued: int
    client_context: str
    drafts: list[dict[str, Any]]
    hitl_note: str
    message: str | None = None


class OutreachRejectRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)
    reviewed_by: str = Field(default="operator", max_length=100)


class OutreachApproveRequest(BaseModel):
    reviewed_by: str = Field(default="operator", max_length=100)


class OutreachDraftResponse(BaseModel):
    id: str
    lead_id: str
    contact_name: str | None
    company_name: str | None
    email: str | None
    status: str
    subject: str
    hook: str
    body: str
    signal_used: str
    signal_type: str
    research: dict[str, Any]
    created_at: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None
    sent_at: str | None = None


class OutreachSendResponse(BaseModel):
    draft: dict[str, Any]
    send_result: dict[str, Any]


# ---------------------------------------------------------------------------
# Campaign running (Stage 2–5 pipeline triggered per campaign)
# ---------------------------------------------------------------------------
class CampaignRunRequest(BaseModel):
    max_results: int = Field(default=5, ge=1, le=20)
    enrich_limit: int = Field(default=10, ge=1, le=50)
    personalize_limit: int = Field(default=3, ge=1, le=10)
    run_discover: bool = True
    run_enrich: bool = True
    run_personalize: bool = True


class CampaignRunResponse(BaseModel):
    run_id: str
    campaign_id: UUID
    campaign_status: CampaignStatus
    leads_discovered: int
    leads_enriched: int
    drafts_queued: int
    errors: list[str]
    message: str
