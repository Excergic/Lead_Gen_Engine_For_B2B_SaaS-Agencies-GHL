from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from supabase import Client

from app.engine.factory import LeadGenEngine
from app.services.leads_store import LeadsStore

logger = logging.getLogger(__name__)


class EnrichService:
    def __init__(
        self,
        engine: LeadGenEngine,
        leads_jsonl_path: Path,
        db: Client | None = None,
    ) -> None:
        self._engine = engine
        self._store = LeadsStore(jsonl_path=leads_jsonl_path, db=db)

    def run(self, *, limit: int = 10, persist: bool = True) -> dict[str, Any]:
        pending = self._store.load_discovered(limit=limit)
        if not pending:
            return {
                "processed": 0,
                "saved": 0,
                "summary": {
                    "total": 0,
                    "enriched_status": 0,
                    "with_email": 0,
                    "with_linkedin": 0,
                    "avg_confidence": 0.0,
                },
                "leads": [],
                "message": "No discovered leads to enrich",
            }

        enriched = self._engine.enrich.enrich_batch(pending)
        saved = self._store.save_enriched(enriched) if persist else 0
        summary = self._engine.enrich.summary(enriched)

        return {
            "processed": len(enriched),
            "saved": saved,
            "summary": summary,
            "leads": [_public_lead_view(l) for l in enriched],
        }


def _public_lead_view(lead) -> dict[str, Any]:
    d = lead.model_dump()
    return {
        "id": d["id"],
        "icp_id": d["icp_id"],
        "channel": d["channel"],
        "company_name": d.get("company_name"),
        "contact_name": d.get("contact_name"),
        "job_title": d.get("job_title"),
        "email": d.get("email"),
        "email_verified": d.get("email_verified"),
        "phone": d.get("phone"),
        "company_domain": d.get("company_domain"),
        "linkedin_url": d.get("linkedin_url"),
        "industry": d.get("industry"),
        "recent_activity": (d.get("recent_activity") or "")[:200],
        "status": d["status"],
        "enrichment_confidence": d.get("enrichment_confidence"),
        "profile_source": d.get("profile_source"),
        "email_source": d.get("email_source"),
        "source_url": d["source_url"],
        "profile_link": d.get("profile_link") or d["source_url"],
        "needs_human_review": d.get("needs_human_review", False),
        "meeting_booked": d["meeting_booked"],
    }
