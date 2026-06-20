from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from supabase import Client

from app.tools.enrichment.models import EnrichedLead
from app.tools.models import LeadCandidate, LeadStatus

logger = logging.getLogger(__name__)


class LeadsStore:
    """Load/update leads from JSONL or Supabase."""

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

    def _load_enriched_supabase(self, *, limit: int) -> list[EnrichedLead]:
        rows = (
            self._db.table("discovered_leads")
            .select("*")
            .eq("status", LeadStatus.ENRICHED.value)
            .order("enriched_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [EnrichedLead.model_validate(_supabase_to_enriched(row)) for row in rows.data]

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

    def _load_supabase(self, *, limit: int) -> list[LeadCandidate]:
        rows = (
            self._db.table("discovered_leads")
            .select("*")
            .eq("status", LeadStatus.DISCOVERED.value)
            .order("discovered_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [LeadCandidate.model_validate(_supabase_to_lead(row)) for row in rows.data]

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

    def _save_supabase_enriched(self, enriched: list[EnrichedLead]) -> int:
        saved = 0
        for lead in enriched:
            row = _enriched_to_row(lead)
            try:
                self._db.table("discovered_leads").update(row).eq("id", lead.id).execute()
                saved += 1
            except Exception as exc:
                logger.warning("enriched_save_failed id=%s err=%s", lead.id, exc)
        return saved


def _supabase_to_enriched(row: dict[str, Any]) -> dict[str, Any]:
    base = _supabase_to_lead(row)
    base.update(
        {
            "email": row.get("email"),
            "email_verified": row.get("email_verified") or False,
            "phone": row.get("phone"),
            "company_domain": row.get("company_domain"),
            "linkedin_url": row.get("linkedin_url"),
            "job_title": row.get("job_title"),
            "industry": row.get("industry"),
            "company_size": row.get("company_size"),
            "recent_activity": row.get("recent_activity"),
            "profile_source": row.get("profile_source") or "none",
            "email_source": row.get("email_source") or "none",
            "enrichment_confidence": row.get("enrichment_confidence") or 0.0,
            "enriched_at": row.get("enriched_at"),
            "enrichment_raw": row.get("enrichment_raw") or {},
        }
    )
    return base


def _supabase_to_lead(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "icp_id": row["icp_id"],
        "channel": row["channel"],
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
        "linkedin_url": lead.linkedin_url,
        "industry": lead.industry,
        "company_size": lead.company_size,
        "recent_activity": lead.recent_activity,
        "profile_source": lead.profile_source.value,
        "email_source": lead.email_source.value,
        "enrichment_confidence": lead.enrichment_confidence,
        "enriched_at": lead.enriched_at.isoformat() if lead.enriched_at else None,
        "enrichment_raw": lead.enrichment_raw,
        "status": lead.status.value,
    }
