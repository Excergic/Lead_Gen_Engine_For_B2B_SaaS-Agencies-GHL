from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.tools.enrichment.models import EnrichedLead


class SignalType(StrEnum):
    REVENUE_UP = "revenue_up"
    REVENUE_DOWN = "revenue_down"
    NEW_FEATURE = "new_feature"
    NEW_WORKFLOW = "new_workflow"
    HIRING = "hiring"
    FUNDING = "funding"
    PRODUCT_LAUNCH = "product_launch"
    OUTBOUND_STRUGGLE = "outbound_struggle"
    AI_GAP = "ai_gap"
    OTHER = "other"


class RevenueTrend(StrEnum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    UNKNOWN = "unknown"


class ProspectSignals(BaseModel):
    contact_name: str | None = None
    company_name: str | None = None
    revenue_trend: RevenueTrend = RevenueTrend.UNKNOWN
    revenue_notes: str | None = None
    new_features: list[str] = Field(default_factory=list)
    new_workflows: list[str] = Field(default_factory=list)
    hiring_signals: list[str] = Field(default_factory=list)
    funding_signals: list[str] = Field(default_factory=list)
    product_launches: list[str] = Field(default_factory=list)
    recent_posts_summary: str | None = None
    pain_indicators: list[str] = Field(default_factory=list)
    strongest_signal: str | None = None
    strongest_signal_type: SignalType = SignalType.OTHER
    hook_angle: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ClientContext(BaseModel):
    """Offer + messaging rules for personalization."""

    offer_headline: str = "Qualified meetings on your calendar — fully automated"
    offer_description: str = (
        "We find prospects, personalize outreach, and book meetings while you focus on closing."
    )
    value_proposition: str = "Wake up to calendar invites from qualified prospects."
    calendar_url: str | None = None
    messaging_dos: list[str] = Field(
        default_factory=lambda: [
            "Reference one specific recent signal",
            "Lead with their pain, not your product",
            "Keep under 120 words",
        ]
    )
    messaging_donts: list[str] = Field(
        default_factory=lambda: [
            "Never say revolutionize or game-changer",
            "No generic AI opener",
            "No fake familiarity",
        ]
    )
    pain_points: list[str] = Field(
        default_factory=lambda: [
            "Inbound leads sit too long before follow-up",
            "Outbound reply rates plateaued",
            "Founder is the closer with no time to prospect",
        ]
    )


class OutreachDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    lead_id: str
    contact_name: str | None = None
    company_name: str | None = None
    email: str | None = None
    subject: str
    body: str
    hook: str
    signal_used: str
    signal_type: SignalType
    signals: ProspectSignals
    status: str = "pending_review"  # pending_review | approved | rejected | sent
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None
    sent_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class OutreachMessage(BaseModel):
    subject: str
    body: str
    hook: str
    signal_used: str
    signal_type: SignalType
    raw: dict[str, Any] = Field(default_factory=dict)
