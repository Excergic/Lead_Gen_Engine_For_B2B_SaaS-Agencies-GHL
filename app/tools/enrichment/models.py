from __future__ import annotations

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
    # True when no direct contact (email/phone) found — human should use profile_link
    needs_human_review: bool = False
    # Best profile URL for human outreach (LinkedIn profile > source URL)
    profile_link: str | None = None

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
        # Pick the best profile link for human follow-up
        self.profile_link = self.linkedin_url or self.source_url

        # Actionable = has a direct contact method (email or phone)
        has_direct_contact = bool(self.email or self.phone)
        has_any_contact = bool(self.email or self.phone or self.linkedin_url or self.contact_name)

        if has_any_contact:
            self.status = LeadStatus.ENRICHED
            self.enriched_at = datetime.now(UTC)

        # Flag for human review when no direct contact found
        self.needs_human_review = not has_direct_contact

        self.enrichment_confidence = min(self.enrichment_confidence, 1.0)

    def _bump_confidence(self, delta: float) -> None:
        self.enrichment_confidence = min(1.0, self.enrichment_confidence + delta * 0.5)
