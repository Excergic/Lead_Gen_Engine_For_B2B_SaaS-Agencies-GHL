from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from supabase import Client

from app.tools.enrichment.models import EnrichedLead
from app.tools.models import Channel, LeadCandidate, LeadStatus

logger = logging.getLogger(__name__)

# Maps Channel → table name
_CHANNEL_TABLES: dict[str, str] = {
    Channel.LINKEDIN: "linkedin_leads",
    Channel.X: "x_leads",
    Channel.REDDIT: "reddit_leads",
}


class LeadsStore:
    """Load/update leads from JSONL or Supabase channel-specific tables."""

    def __init__(self, jsonl_path: Path | None = None, db: Client | None = None) -> None:
        self._jsonl_path = jsonl_path
        self._db = db

    def load_enriched(
        self,
        *,
        limit: int = 50,
        lead_ids: list[str] | None = None,
        require_email: bool = False,
    ) -> list[EnrichedLead]:
        leads = self._load_enriched_jsonl(limit=limit * 3 if lead_ids else limit)
        if not leads and self._db:
            leads = self._load_enriched_supabase(limit=limit * 3 if lead_ids else limit)

        if lead_ids:
            id_set = set(lead_ids)
            leads = [l for l in leads if l.id in id_set]

        if require_email:
            leads = [l for l in leads if l.email]

        return leads[:limit]

    def load_discovered(self, *, limit: int = 50) -> list[LeadCandidate]:
        if self._jsonl_path:
            leads = self._load_jsonl(limit=limit)
            if leads:
                return leads
        if self._db:
            return self._load_supabase(limit=limit)
        return []

    def save_enriched(self, leads: list[EnrichedLead]) -> int:
        if self._jsonl_path and self._jsonl_path.exists():
            return self._save_jsonl_enriched(leads)
        if self._db:
            return self._save_supabase_enriched(leads)
        return 0

    # ------------------------------------------------------------------
    # JSONL helpers (unchanged)
    # ------------------------------------------------------------------

    def _load_enriched_jsonl(self, *, limit: int) -> list[EnrichedLead]:
        if not self._jsonl_path or not self._jsonl_path.exists():
            return []
        leads: list[EnrichedLead] = []
        for line in self._jsonl_path.read_text().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("status") != LeadStatus.ENRICHED.value:
                continue
            leads.append(EnrichedLead.model_validate(data))
            if len(leads) >= limit:
                break
        return leads

    def _load_jsonl(self, *, limit: int) -> list[LeadCandidate]:
        if not self._jsonl_path or not self._jsonl_path.exists():
            return []
        leads: list[LeadCandidate] = []
        for line in self._jsonl_path.read_text().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("status") != LeadStatus.DISCOVERED.value:
                continue
            leads.append(LeadCandidate.model_validate(data))
            if len(leads) >= limit:
                break
        return leads

    def _save_jsonl_enriched(self, enriched: list[EnrichedLead]) -> int:
        if not self._jsonl_path or not self._jsonl_path.exists():
            return 0
        by_url = {l.source_url: l for l in enriched}
        lines = self._jsonl_path.read_text().splitlines()
        updated = 0
        out: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            data = json.loads(line)
            url = data.get("source_url")
            if url in by_url:
                out.append(by_url[url].model_dump_json())
                updated += 1
            else:
                out.append(line)
        self._jsonl_path.write_text("\n".join(out) + ("\n" if out else ""))
        return updated

    # ------------------------------------------------------------------
    # Supabase — channel-specific tables
    # ------------------------------------------------------------------

    def _load_enriched_supabase(self, *, limit: int) -> list[EnrichedLead]:
        """Load enriched leads from all three channel tables, sorted by lead_score desc."""
        leads: list[EnrichedLead] = []
        per_table = max(limit, 20)
        for channel, table in _CHANNEL_TABLES.items():
            try:
                rows = (
                    self._db.table(table)
                    .select("*")
                    .eq("status", LeadStatus.ENRICHED.value)
                    .order("lead_score", desc=True)
                    .limit(per_table)
                    .execute()
                )
                for row in rows.data:
                    leads.append(EnrichedLead.model_validate(_channel_row_to_enriched(row, channel)))
            except Exception as exc:
                logger.debug("load_enriched_supabase_failed table=%s err=%s", table, exc)
        # Sort all results by lead_score desc, then limit
        leads.sort(key=lambda l: l.lead_score, reverse=True)
        return leads[:limit]

    def _load_supabase(self, *, limit: int) -> list[LeadCandidate]:
        """Load discovered leads from all channel tables."""
        leads: list[LeadCandidate] = []
        per_table = max(limit, 20)
        for channel, table in _CHANNEL_TABLES.items():
            try:
                rows = (
                    self._db.table(table)
                    .select("*")
                    .eq("status", LeadStatus.DISCOVERED.value)
                    .order("discovered_at", desc=True)
                    .limit(per_table)
                    .execute()
                )
                for row in rows.data:
                    leads.append(LeadCandidate.model_validate(_channel_row_to_lead(row, channel)))
            except Exception as exc:
                logger.debug("load_discovered_supabase_failed table=%s err=%s", table, exc)
        leads.sort(key=lambda l: l.discovered_at, reverse=True)
        return leads[:limit]

    def _save_supabase_enriched(self, enriched: list[EnrichedLead]) -> int:
        saved = 0
        for lead in enriched:
            table = _CHANNEL_TABLES.get(lead.channel.value, "linkedin_leads")
            row = _enriched_to_row(lead)
            try:
                self._db.table(table).update(row).eq("id", lead.id).execute()
                saved += 1
            except Exception as exc:
                logger.warning("enriched_save_failed table=%s id=%s err=%s", table, lead.id, exc)
        return saved


# ------------------------------------------------------------------
# Row mapping helpers
# ------------------------------------------------------------------

def _channel_row_to_lead(row: dict[str, Any], channel: str) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "icp_id": row["icp_id"],
        "channel": channel,
        "company_name": row.get("company_name"),
        "contact_name": row.get("contact_name"),
        "title": row.get("title"),
        "signal": row.get("signal"),
        "source_url": row["source_url"],
        "snippet": row.get("snippet") or "",
        "status": row.get("status") or LeadStatus.DISCOVERED.value,
        "meeting_booked": row.get("meeting_booked") or False,
        "discovered_at": row.get("discovered_at"),
        "raw": row.get("raw") or {},
    }


def _channel_row_to_enriched(row: dict[str, Any], channel: str) -> dict[str, Any]:
    base = _channel_row_to_lead(row, channel)
    base.update(
        {
            "email": row.get("email"),
            "email_verified": row.get("email_verified") or False,
            "phone": row.get("phone"),
            "company_domain": row.get("company_domain"),
            "linkedin_url": row.get("linkedin_url") or row.get("linkedin_profile_url"),
            "job_title": row.get("job_title"),
            "industry": row.get("industry"),
            "company_size": row.get("company_size"),
            "recent_activity": row.get("recent_activity"),
            "profile_source": row.get("profile_source") or "none",
            "email_source": row.get("email_source") or "none",
            "enrichment_confidence": row.get("enrichment_confidence") or 0.0,
            "enriched_at": row.get("enriched_at"),
            "enrichment_raw": row.get("enrichment_raw") or {},
            "needs_human_review": row.get("needs_human_review") or False,
            "profile_link": row.get("profile_link"),
            "lead_score": row.get("lead_score") or 0,
            "lead_score_reason": row.get("lead_score_reason"),
        }
    )
    return base


def _enriched_to_row(lead: EnrichedLead) -> dict[str, Any]:
    return {
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
        "needs_human_review": lead.needs_human_review,
        "profile_link": lead.profile_link,
        "lead_score": lead.lead_score,
        "lead_score_reason": lead.lead_score_reason,
    }
