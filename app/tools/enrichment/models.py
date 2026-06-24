from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.tools.models import Channel, ICPId, LeadCandidate, LeadStatus


class EnrichmentSource(StrEnum):
    PERPLEXITY_PROFILE = "perplexity_profile"
    APOLLO = "apollo"
    HUNTER = "hunter"
    PROSPEO = "prospeo"
    MANUAL = "manual"
    NONE = "none"


class ProfileEnrichment(BaseModel):
    contact_name: str | None = None
    job_title: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    company_size: str | None = None
    industry: str | None = None
    recent_activity: str | None = None
    source: EnrichmentSource = EnrichmentSource.PERPLEXITY_PROFILE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw: dict[str, Any] = Field(default_factory=dict)


class EmailEnrichment(BaseModel):
    email: str | None = None
    email_verified: bool = False
    source: EnrichmentSource = EnrichmentSource.NONE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw: dict[str, Any] = Field(default_factory=dict)


class EnrichedLead(LeadCandidate):
    email: str | None = None
    email_verified: bool = False
    phone: str | None = None
    company_domain: str | None = None
    linkedin_url: str | None = None
    job_title: str | None = None
    industry: str | None = None
    company_size: str | None = None
    recent_activity: str | None = None
    profile_source: EnrichmentSource = EnrichmentSource.NONE
    email_source: EnrichmentSource = EnrichmentSource.NONE
    enrichment_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    enriched_at: datetime | None = None
    enrichment_raw: dict[str, Any] = Field(default_factory=dict)
    # True only when we have zero way to contact them (no email, phone, OR native profile)
    needs_human_review: bool = False
    # Best URL for outreach: channel-native profile link
    profile_link: str | None = None
    # ICP fit score (0–100) and 1-sentence reason, set by ScoreSignalTool
    lead_score: int = 0
    lead_score_reason: str | None = None

    @classmethod
    def from_lead(cls, lead: LeadCandidate) -> EnrichedLead:
        return cls(**lead.model_dump())

    def apply_profile(self, profile: ProfileEnrichment) -> None:
        if profile.contact_name:
            self.contact_name = profile.contact_name
        if profile.job_title:
            self.job_title = profile.job_title
            self.title = profile.job_title
        if profile.company_name:
            self.company_name = profile.company_name
        if profile.company_domain:
            self.company_domain = profile.company_domain
        if profile.linkedin_url:
            self.linkedin_url = profile.linkedin_url
        if profile.phone:
            self.phone = profile.phone
        if profile.industry:
            self.industry = profile.industry
        if profile.company_size:
            self.company_size = profile.company_size
        if profile.recent_activity:
            self.recent_activity = profile.recent_activity
        self.profile_source = profile.source
        self.enrichment_raw["profile"] = profile.raw
        self._bump_confidence(profile.confidence)

    def apply_email(self, email_result: EmailEnrichment) -> None:
        if email_result.email:
            self.email = email_result.email
        self.email_verified = email_result.email_verified
        self.email_source = email_result.source
        self.enrichment_raw["email"] = email_result.raw
        self._bump_confidence(email_result.confidence)

    def finalize(self) -> None:
        # Set the best profile link based on the lead's native channel.
        # This is the primary contact method — email is a bonus on top of it.
        self.profile_link = _native_profile_link(self.channel, self.source_url, self.linkedin_url)

        # Enriched if we have any signal about this person
        has_any_contact = bool(
            self.email or self.phone or self.profile_link or self.contact_name
        )
        if has_any_contact:
            self.status = LeadStatus.ENRICHED
            self.enriched_at = datetime.now(UTC)

        # Human review only when we have literally no way to reach them
        # (no email, no phone, AND no profile link to message via native channel)
        self.needs_human_review = not bool(self.email or self.phone or self.profile_link)

        self.enrichment_confidence = min(self.enrichment_confidence, 1.0)

    def _bump_confidence(self, delta: float) -> None:
        self.enrichment_confidence = min(1.0, self.enrichment_confidence + delta * 0.5)


# ---------------------------------------------------------------------------
# Channel-native profile URL helpers
# ---------------------------------------------------------------------------

def _native_profile_link(channel: Channel, source_url: str, linkedin_url: str | None) -> str | None:
    """Return the best profile URL for outreach on this lead's native channel."""
    if channel == Channel.LINKEDIN:
        return linkedin_url or _linkedin_profile_from_url(source_url) or source_url

    if channel == Channel.X:
        handle = _extract_x_handle(source_url)
        return f"https://x.com/{handle}" if handle else source_url

    if channel == Channel.REDDIT:
        username = _extract_reddit_username(source_url)
        return f"https://reddit.com/u/{username}" if username else source_url

    # Fallback for other channels (google_maps, web)
    return linkedin_url or source_url


def _linkedin_profile_from_url(url: str) -> str | None:
    clean = url.split("?")[0]
    if "linkedin.com/in/" in clean.lower():
        return clean
    m = re.search(r"linkedin\.com/posts/([a-zA-Z0-9_-]+)", clean, re.IGNORECASE)
    if m:
        handle = m.group(1).split("_")[0]
        return f"https://www.linkedin.com/in/{handle}" if handle else None
    return None


def _extract_x_handle(url: str) -> str | None:
    m = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)", url)
    return m.group(1) if m else None


def _extract_reddit_username(url: str) -> str | None:
    m = re.search(r"reddit\.com/u(?:ser)?/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None
