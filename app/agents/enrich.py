from __future__ import annotations

import logging
from typing import Any

from app.tools.enrichment.models import EnrichedLead, ProfileEnrichment
from app.tools.enrichment.providers import _linkedin_profile_from_source
from app.tools.executor import ToolExecutor
from app.tools.models import LeadCandidate, LeadStatus
from app.tools.personalize.models import ClientContext
from app.tools.policy import AgentRole

logger = logging.getLogger(__name__)


class EnrichAgent:
    """Stage 3 ENRICH — profile extract → email waterfall → ICP scoring → status enriched."""

    def __init__(self, executor: ToolExecutor, actor: AgentRole = AgentRole.ENRICH_AGENT) -> None:
        self.executor = executor
        self.actor = actor

    def enrich_lead(
        self, lead: LeadCandidate, client_context: ClientContext | None = None
    ) -> EnrichedLead:
        enriched = EnrichedLead.from_lead(lead)

        # Seed LinkedIn from discovery URL so Apollo can match before profile extract
        if not enriched.linkedin_url:
            enriched.linkedin_url = _linkedin_profile_from_source(lead.source_url)

        try:
            profile: ProfileEnrichment = self.executor.run(
                self.actor,
                "enrich_profile",
                source_url=lead.source_url,
                company_name=lead.company_name,
                contact_name=lead.contact_name,
                signal=lead.signal or lead.snippet,
            )
            enriched.apply_profile(profile)
        except Exception as exc:
            logger.warning("enrich_profile_failed url=%s err=%s", lead.source_url, exc)

        linkedin_for_email = enriched.linkedin_url or _linkedin_profile_from_source(lead.source_url)

        try:
            email_result = self.executor.run(
                self.actor,
                "enrich_email",
                domain=enriched.company_domain,
                contact_name=enriched.contact_name,
                company_name=enriched.company_name,
                linkedin_url=linkedin_for_email,
                source_url=lead.source_url,
            )
            enriched.apply_email(email_result)
        except Exception as exc:
            logger.warning("enrich_email_failed url=%s err=%s", lead.source_url, exc)

        # Score lead against client ICP
        try:
            score_result = self.executor.run(
                self.actor,
                "score_signal",
                contact_name=enriched.contact_name,
                job_title=enriched.job_title,
                company_name=enriched.company_name,
                company_size=enriched.company_size,
                industry=enriched.industry,
                recent_activity=enriched.recent_activity,
                source_url=lead.source_url,
                icp_description=None,
                offer_headline=client_context.offer_headline if client_context else None,
                pain_points=client_context.pain_points if client_context else None,
            )
            enriched.lead_score = score_result.get("score", 0)
            enriched.lead_score_reason = score_result.get("reason") or None
        except Exception as exc:
            logger.warning("score_signal_failed url=%s err=%s", lead.source_url, exc)

        enriched.finalize()
        return enriched

    def enrich_batch(
        self,
        leads: list[LeadCandidate],
        client_context: ClientContext | None = None,
    ) -> list[EnrichedLead]:
        results: list[EnrichedLead] = []
        for lead in leads:
            logger.info("enrich_start url=%s", lead.source_url[:80])
            enriched = self.enrich_lead(lead, client_context=client_context)
            logger.info(
                "enrich_done url=%s status=%s email=%s score=%d confidence=%.2f",
                lead.source_url[:80],
                enriched.status.value,
                bool(enriched.email),
                enriched.lead_score,
                enriched.enrichment_confidence,
            )
            results.append(enriched)
        return results

    def summary(self, enriched: list[EnrichedLead]) -> dict[str, Any]:
        total = len(enriched)
        with_email = sum(1 for l in enriched if l.email)
        with_linkedin = sum(1 for l in enriched if l.linkedin_url)
        status_enriched = sum(1 for l in enriched if l.status == LeadStatus.ENRICHED)
        return {
            "total": total,
            "enriched_status": status_enriched,
            "with_email": with_email,
            "with_linkedin": with_linkedin,
            "avg_confidence": round(
                sum(l.enrichment_confidence for l in enriched) / total, 2
            )
            if total
            else 0.0,
        }
