from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from supabase import Client

from app.engine.factory import LeadGenEngine
from app.services.leads_store import LeadsStore
from app.services.outreach_hitl import OutreachHitlService

logger = logging.getLogger(__name__)


class PersonalizeService:
    def __init__(
        self,
        engine: LeadGenEngine,
        hitl: OutreachHitlService,
        leads_jsonl_path: Path,
        db: Client | None = None,
    ) -> None:
        self._engine = engine
        self._hitl = hitl
        self._leads = LeadsStore(jsonl_path=leads_jsonl_path, db=db)

    def run(
        self,
        *,
        limit: int = 5,
        client_id: UUID | None = None,
        lead_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        leads = self._leads.load_enriched(limit=limit, lead_ids=lead_ids)
        if not leads:
            return {
                "processed": 0,
                "queued": 0,
                "drafts": [],
                "message": "No enriched leads ready for personalization",
            }

        client_ctx = self._hitl.load_client_context(client_id)
        drafts = self._engine.personalize.personalize_batch(leads, client_ctx)

        from app.services.outreach_hitl import _draft_view

        return {
            "processed": len(leads),
            "queued": len(drafts),
            "client_context": client_ctx.offer_headline,
            "drafts": [_draft_view(d) for d in drafts],
            "hitl_note": "Drafts queued for human review. Approve before sending.",
        }
