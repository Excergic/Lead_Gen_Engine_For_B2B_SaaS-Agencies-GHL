from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


class ICPId(StrEnum):
    SAAS_REVENUE = "saas_revenue"
    MARKETING_AGENCY = "marketing_agency"
    B2B_NO_AI = "b2b_no_ai"


class Channel(StrEnum):
    LINKEDIN = "linkedin"
    X = "x"
    REDDIT = "reddit"
    GOOGLE_MAPS = "google_maps"
    WEB = "web"


class LeadStatus(StrEnum):
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    CONTACTED = "contacted"
    REPLIED = "replied"
    MEETING_BOOKED = "meeting_booked"


class SignalCategory(StrEnum):
    FUNDING = "funding"           # raised money, series A/B/C, seed round
    HIRING = "hiring"             # hiring sales/marketing, posting AE/SDR roles
    LAYOFFS = "layoffs"           # laid off, downsizing — cost pressure signal
    PAIN_POINT = "pain_point"     # explicitly struggling, asking for help
    PRODUCT_LAUNCH = "product_launch"  # launched, shipped, announcing
    COMPETITOR = "competitor"     # mentioned competitor, switching from X
    ENGAGEMENT = "engagement"     # liked/commented on relevant content
    OTHER = "other"


class ICPProfile(BaseModel):
    id: ICPId
    name: str
    description: str
    search_queries: list[str] = Field(min_length=1)
    channels: list[Channel] = Field(default_factory=lambda: list(Channel))


class SearchHit(BaseModel):
    title: str
    url: HttpUrl | str
    snippet: str = ""
    date: str | None = None
    source: Channel | str = Channel.WEB


class LeadCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    icp_id: ICPId
    channel: Channel
    company_name: str | None = None
    contact_name: str | None = None
    title: str | None = None
    signal: str | None = None
    source_url: str
    snippet: str = ""
    status: LeadStatus = LeadStatus.DISCOVERED
    meeting_booked: bool = False
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = Field(default_factory=dict)
    # Signal intelligence
    signal_category: SignalCategory = SignalCategory.OTHER
    signal_freshness_hours: float | None = None  # hours since the signal was published
