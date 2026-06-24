"""
CampaignRunnerService — ties a campaign record to the LangGraph pipeline.

Flow:
  1. Load campaign + validate it can be run (draft / paused)
  2. Load client's ICP profile from DB → map icp_template → ICPId(s)
  3. Load client context from client_definitions (offer, messaging rules)
  4. Transition campaign → active (set started_at if first run)
  5. Run the LangGraph pipeline (discover → enrich → personalize)
  6. Persist results scoped to campaign_id
  7. Update campaign funnel metrics + today's daily metrics
  8. Write a campaign_runs audit row
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from supabase import Client

from app.engine.base import PipelineConfig, PipelineResult
from app.engine.factory import LeadGenEngine
from app.models.schemas import CampaignRunRequest, CampaignRunResponse, CampaignStatus, ICPTemplate
from app.services.stage1 import DefinitionService
from app.tools.enrichment.models import EnrichedLead
from app.tools.icp import ICP_PROFILES
from app.tools.models import Channel, ICPId, LeadCandidate
from app.tools.personalize.defaults import merge_client_context
from app.tools.personalize.models import ClientContext, OutreachDraft

logger = logging.getLogger(__name__)

# Map the client-facing ICP template names to hardcoded ICPId values used by
# the discover agent.  CUSTOM falls back to running all ICPs.
_TEMPLATE_TO_ICP_IDS: dict[str, list[ICPId]] = {
    ICPTemplate.SAAS_FOUNDERS: [ICPId.SAAS_REVENUE],
    ICPTemplate.OUTBOUND_AGENCIES: [ICPId.MARKETING_AGENCY],
    ICPTemplate.GHL_SAASPRENEURS: [ICPId.SAAS_REVENUE],
    ICPTemplate.CUSTOM: [],  # empty → all ICPs
}


class CampaignNotFound(Exception):
    pass


class CampaignNotRunnable(Exception):
    pass


class CampaignRunnerService:
    """Orchestrates the full pipeline (discover→enrich→personalize) for one campaign."""

    def __init__(self, engine: LeadGenEngine, db: Client) -> None:
        self._engine = engine
        self._db = db
        self._definitions = DefinitionService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        client_id: UUID,
        campaign_id: UUID,
        *,
        request: CampaignRunRequest,
    ) -> CampaignRunResponse:
        campaign = self._load_campaign(client_id, campaign_id)
        self._validate_runnable(campaign)

        icp_ids = self._resolve_icp_ids(campaign)
        client_ctx = self._load_client_context(client_id)

        run_id = str(uuid.uuid4())
        self._start_campaign(campaign_id, campaign)
        self._insert_run_row(run_id, campaign_id, request)

        cap = request.max_results
        config = PipelineConfig(
            max_results=cap,
            icp_ids=[i.value for i in icp_ids] if icp_ids else None,
            enrich_limit=cap,
            personalize_limit=cap if request.run_personalize else 0,
            client_context=client_ctx,
            run_discover=request.run_discover,
            run_enrich=request.run_enrich,
            run_personalize=request.run_personalize,
        )

        logger.info(
            "campaign_run_start campaign_id=%s run_id=%s icps=%s",
            campaign_id,
            run_id,
            [i.value for i in icp_ids] if icp_ids else "all",
        )
        result = self._engine.workflow.run(config)
        logger.info(
            "campaign_run_done campaign_id=%s leads=%d enriched=%d drafts=%d errors=%d",
            campaign_id,
            len(result.leads),
            len(result.enriched),
            len(result.drafts),
            len(result.errors),
        )

        self._persist_leads(result.leads, campaign_id)
        self._persist_enriched(result.enriched, campaign_id)
        self._persist_drafts(result.drafts, campaign_id)
        self._update_metrics(campaign_id, result)
        self._upsert_daily_metrics(campaign_id, result)
        self._finish_run_row(run_id, result)
        self._pause_campaign_after_run(campaign_id)

        msg = (
            f"Discovered {len(result.leads)}, enriched {len(result.enriched)}, "
            f"queued {len(result.drafts)} drafts for HITL review."
        )
        if result.errors:
            msg += f" {len(result.errors)} non-fatal error(s) recorded."

        return CampaignRunResponse(
            run_id=run_id,
            campaign_id=campaign_id,
            campaign_status=CampaignStatus.PAUSED,
            leads_discovered=len(result.leads),
            leads_enriched=len(result.enriched),
            drafts_queued=len(result.drafts),
            errors=result.errors,
            message=msg,
        )

    # ------------------------------------------------------------------
    # Campaign state helpers
    # ------------------------------------------------------------------

    def _load_campaign(self, client_id: UUID, campaign_id: UUID) -> dict[str, Any]:
        row = (
            self._db.table("campaigns")
            .select("*")
            .eq("id", str(campaign_id))
            .eq("client_id", str(client_id))
            .maybe_single()
            .execute()
        )
        if not row.data:
            raise CampaignNotFound(f"Campaign '{campaign_id}' not found for client '{client_id}'")
        return row.data

    def _validate_runnable(self, campaign: dict[str, Any]) -> None:
        status = campaign.get("status")
        if status == CampaignStatus.COMPLETED:
            raise CampaignNotRunnable("Campaign is completed and cannot be re-run.")
        if status == CampaignStatus.ACTIVE:
            raise CampaignNotRunnable(
                "Campaign is already running. Wait for it to finish or pause it first."
            )

    def _start_campaign(self, campaign_id: UUID, campaign: dict[str, Any]) -> None:
        updates: dict[str, Any] = {"status": CampaignStatus.ACTIVE.value}
        if not campaign.get("started_at"):
            updates["started_at"] = datetime.now(UTC).isoformat()
        self._db.table("campaigns").update(updates).eq("id", str(campaign_id)).execute()

    def _pause_campaign_after_run(self, campaign_id: UUID) -> None:
        """Return to paused so the operator can re-run locally without manual reset."""
        try:
            self._db.table("campaigns").update(
                {"status": CampaignStatus.PAUSED.value}
            ).eq("id", str(campaign_id)).execute()
        except Exception as exc:
            logger.warning("campaign_pause_after_run_failed err=%s", exc)

    # ------------------------------------------------------------------
    # ICP resolution
    # ------------------------------------------------------------------

    def _resolve_icp_ids(self, campaign: dict[str, Any]) -> list[ICPId]:
        """Map the campaign's DB ICP profile template to agent ICPIds."""
        icp_profile_id = campaign.get("icp_profile_id")
        if not icp_profile_id:
            return []  # empty → use all ICPs

        row = (
            self._db.table("icp_profiles")
            .select("icp_template")
            .eq("id", str(icp_profile_id))
            .maybe_single()
            .execute()
        )
        if not row.data:
            logger.warning("icp_profile_not_found id=%s, using all ICPs", icp_profile_id)
            return []

        template = row.data.get("icp_template", ICPTemplate.CUSTOM)
        ids = _TEMPLATE_TO_ICP_IDS.get(template, [])
        logger.info("campaign_icp_resolved template=%s → icp_ids=%s", template, ids)
        return ids

    # ------------------------------------------------------------------
    # Client context
    # ------------------------------------------------------------------

    def _load_client_context(self, client_id: UUID) -> ClientContext:
        definition = self._definitions.get_active(client_id)
        return merge_client_context(definition)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Channel → table routing
    # ------------------------------------------------------------------

    @staticmethod
    def _table_for(channel: Channel) -> str:
        return {
            Channel.LINKEDIN: "linkedin_leads",
            Channel.X: "x_leads",
            Channel.REDDIT: "reddit_leads",
        }.get(channel, "linkedin_leads")

    @staticmethod
    def _channel_extra(lead: LeadCandidate) -> dict:
        """Channel-specific columns derived from source_url / raw data."""
        url = lead.source_url
        if lead.channel == Channel.LINKEDIN:
            return {
                "linkedin_profile_url": url.split("?")[0],
                "linkedin_post_url": url if "/posts/" in url or "/feed/" in url else None,
                "headline": lead.signal,
            }
        if lead.channel == Channel.X:
            handle = _extract_x_handle(url)
            return {
                "x_handle": handle,
                "tweet_url": url if "/status/" in url else None,
                "x_profile_url": f"https://x.com/{handle}" if handle else None,
                "x_bio": lead.signal,
            }
        if lead.channel == Channel.REDDIT:
            return {
                "reddit_username": _extract_reddit_username(url, lead.raw),
                "subreddit": _extract_subreddit(url),
                "post_url": url,
                "post_title": lead.title,
            }
        return {}

    def _persist_leads(self, leads: list[LeadCandidate], campaign_id: UUID) -> None:
        for lead in leads:
            table = self._table_for(lead.channel)
            row: dict = {
                "id": lead.id,
                "icp_id": lead.icp_id.value,
                "contact_name": lead.contact_name,
                "title": lead.title,
                "company_name": lead.company_name,
                "signal": lead.signal,
                "source_url": lead.source_url,
                "snippet": lead.snippet,
                "status": lead.status.value,
                "meeting_booked": lead.meeting_booked,
                "raw": lead.raw,
                "discovered_at": lead.discovered_at.isoformat(),
                "campaign_id": str(campaign_id),
            }
            row.update(self._channel_extra(lead))
            try:
                self._db.table(table).upsert(row, on_conflict="source_url").execute()
            except Exception as exc:
                logger.warning("lead_save_failed table=%s url=%s err=%s", table, lead.source_url, exc)

    def _persist_enriched(self, enriched: list[EnrichedLead], campaign_id: UUID) -> None:
        for lead in enriched:
            table = self._table_for(lead.channel)
            updates: dict = {
                "contact_name": lead.contact_name,
                "company_name": lead.company_name,
                "title": lead.job_title or lead.title,
                "job_title": lead.job_title,
                "email": lead.email,
                "email_verified": lead.email_verified,
                "phone": lead.phone,
                "company_domain": lead.company_domain,
                "industry": lead.industry,
                "company_size": lead.company_size,
                "recent_activity": lead.recent_activity,
                "profile_source": lead.profile_source.value,
                "email_source": lead.email_source.value,
                "enrichment_confidence": lead.enrichment_confidence,
                "enriched_at": lead.enriched_at.isoformat() if lead.enriched_at else None,
                "enrichment_raw": lead.enrichment_raw,
                "status": lead.status.value,
                "campaign_id": str(campaign_id),
                "needs_human_review": lead.needs_human_review,
                "profile_link": lead.profile_link,
                "lead_score": lead.lead_score,
                "lead_score_reason": lead.lead_score_reason,
            }
            # linkedin_url lives in linkedin_leads too, but x/reddit use it as a separate column
            if lead.channel != Channel.LINKEDIN and lead.linkedin_url:
                updates["linkedin_url"] = lead.linkedin_url
            elif lead.channel == Channel.LINKEDIN and lead.linkedin_url:
                updates["linkedin_profile_url"] = lead.linkedin_url
            try:
                self._db.table(table).update(updates).eq("id", lead.id).execute()
            except Exception as exc:
                logger.warning("enriched_save_failed table=%s id=%s err=%s", table, lead.id, exc)

    def _persist_drafts(self, drafts: list[OutreachDraft], campaign_id: UUID) -> None:
        for draft in drafts:
            row = {
                "id": draft.id,
                "lead_id": draft.lead_id,
                "lead_channel": draft.lead_channel,
                "contact_name": draft.contact_name,
                "company_name": draft.company_name,
                "email": draft.email,
                "subject": draft.subject,
                "body": draft.body,
                "hook": draft.hook,
                "signal_used": draft.signal_used,
                "signal_type": draft.signal_type.value,
                "signals": draft.signals.model_dump(),
                "status": draft.status,
                "created_at": draft.created_at.isoformat(),
                "raw": draft.raw,
                "campaign_id": str(campaign_id),
            }
            try:
                self._db.table("outreach_drafts").upsert(row, on_conflict="id").execute()
            except Exception as exc:
                logger.warning("draft_save_failed id=%s err=%s", draft.id, exc)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _update_metrics(self, campaign_id: UUID, result: PipelineResult) -> None:
        inc: dict[str, Any] = {}
        if result.leads:
            inc["prospects_discovered"] = len(result.leads)
        if result.enriched:
            inc["prospects_enriched"] = len(result.enriched)
        if result.drafts:
            inc["prospects_contacted"] = len(result.drafts)
        if not inc:
            return
        try:
            # Fetch current values and add increments
            row = (
                self._db.table("campaigns")
                .select(", ".join(inc.keys()))
                .eq("id", str(campaign_id))
                .single()
                .execute()
            )
            updates = {
                k: (row.data.get(k) or 0) + v for k, v in inc.items()
            }
            self._db.table("campaigns").update(updates).eq("id", str(campaign_id)).execute()
        except Exception as exc:
            logger.warning("campaign_metrics_update_failed err=%s", exc)

    def _upsert_daily_metrics(self, campaign_id: UUID, result: PipelineResult) -> None:
        today = date.today().isoformat()
        data = {
            "campaign_id": str(campaign_id),
            "metric_date": today,
            "prospects_added": len(result.leads),
        }
        try:
            existing = (
                self._db.table("campaign_daily_metrics")
                .select("id, prospects_added")
                .eq("campaign_id", str(campaign_id))
                .eq("metric_date", today)
                .maybe_single()
                .execute()
            )
            if existing.data:
                updated = {
                    "prospects_added": (existing.data.get("prospects_added") or 0) + len(result.leads)
                }
                self._db.table("campaign_daily_metrics").update(updated).eq(
                    "id", existing.data["id"]
                ).execute()
            else:
                self._db.table("campaign_daily_metrics").insert(data).execute()
        except Exception as exc:
            logger.warning("daily_metrics_upsert_failed err=%s", exc)

    # ------------------------------------------------------------------
    # campaign_runs audit
    # ------------------------------------------------------------------

    def _insert_run_row(
        self, run_id: str, campaign_id: UUID, request: CampaignRunRequest
    ) -> None:
        try:
            self._db.table("campaign_runs").insert(
                {
                    "id": run_id,
                    "campaign_id": str(campaign_id),
                    "status": "running",
                    "ran_discover": request.run_discover,
                    "ran_enrich": request.run_enrich,
                    "ran_personalize": request.run_personalize,
                }
            ).execute()
        except Exception as exc:
            logger.warning("campaign_run_insert_failed err=%s", exc)

    def _finish_run_row(self, run_id: str, result: PipelineResult) -> None:
        try:
            self._db.table("campaign_runs").update(
                {
                    "status": "completed",
                    "leads_discovered": len(result.leads),
                    "leads_enriched": len(result.enriched),
                    "drafts_queued": len(result.drafts),
                    "errors": result.errors,
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", run_id).execute()
        except Exception as exc:
            logger.warning("campaign_run_finish_failed err=%s", exc)


# ---------------------------------------------------------------------------
# URL extraction helpers
# ---------------------------------------------------------------------------

import re as _re


def _extract_x_handle(url: str) -> str | None:
    """Extract @handle from https://x.com/handle/... or https://twitter.com/handle/..."""
    m = _re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)", url)
    return m.group(1) if m else None


def _extract_subreddit(url: str) -> str | None:
    """Extract subreddit name from a reddit.com URL."""
    m = _re.search(r"reddit\.com/r/([A-Za-z0-9_]+)", url)
    return m.group(1) if m else None


def _extract_reddit_username(url: str, raw: dict) -> str | None:
    """Extract reddit username from URL or raw dict (author field)."""
    if raw.get("author"):
        return str(raw["author"])
    m = _re.search(r"reddit\.com/u(?:ser)?/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None
