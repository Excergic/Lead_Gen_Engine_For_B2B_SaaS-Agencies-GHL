from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from supabase import Client

from app.engine.factory import LeadGenEngine, build_lead_gen_engine
from app.tools.models import ICPId, LeadCandidate

logger = logging.getLogger(__name__)


class DiscoverService:
    def __init__(
        self,
        engine: LeadGenEngine,
        db: Client | None = None,
        leads_jsonl_path: Path | None = None,
    ) -> None:
        self._engine = engine
        self._db = db
        self._leads_jsonl_path = leads_jsonl_path or Path("data/discovered_leads.jsonl")

    def run(
        self,
        *,
        max_results: int = 5,
        icp_ids: list[ICPId] | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        icps = None
        if icp_ids:
            from app.tools.icp import ICP_PROFILES

            icps = [p for p in ICP_PROFILES if p.id in icp_ids]

        leads = self._engine.discover.discover_all(icps=icps, max_results=max_results)
        saved = self.save_leads(leads) if persist else 0

        return {
            "discovered": len(leads),
            "saved_new": saved,
            "tools_used": self._engine.tooling.registry.list_tools(),
            "leads": [l.model_dump() for l in leads[:50]],
        }

    def save_leads(self, leads: list[LeadCandidate]) -> int:
        if self._db:
            return self._save_supabase(leads)
        return self._save_jsonl(leads)

    def _save_supabase(self, leads: list[LeadCandidate]) -> int:
        from app.tools.models import Channel

        _table_map = {
            Channel.LINKEDIN: "linkedin_leads",
            Channel.X: "x_leads",
            Channel.REDDIT: "reddit_leads",
        }
        saved = 0
        for lead in leads:
            table = _table_map.get(lead.channel, "linkedin_leads")
            row = {
                "id": lead.id,
                "icp_id": lead.icp_id.value,
                "company_name": lead.company_name,
                "contact_name": lead.contact_name,
                "title": lead.title,
                "signal": lead.signal,
                "source_url": lead.source_url,
                "snippet": lead.snippet,
                "status": lead.status.value,
                "meeting_booked": lead.meeting_booked,
                "raw": lead.raw,
                "discovered_at": lead.discovered_at.isoformat(),
            }
            try:
                self._db.table(table).upsert(row, on_conflict="campaign_id,source_url").execute()
                saved += 1
            except Exception as exc:
                try:
                    self._db.table(table).upsert(row, on_conflict="source_url").execute()
                    saved += 1
                except Exception as exc2:
                    logger.warning(
                        "lead_save_failed table=%s url=%s err=%s",
                        table,
                        lead.source_url,
                        exc2,
                    )
        return saved

    def _save_jsonl(self, leads: list[LeadCandidate]) -> int:
        leads_path = self._leads_jsonl_path
        seen = _load_seen_urls(leads_path)
        leads_path.parent.mkdir(parents=True, exist_ok=True)
        saved = 0
        with leads_path.open("a") as f:
            for lead in leads:
                if lead.source_url in seen:
                    continue
                seen.add(lead.source_url)
                f.write(lead.model_dump_json() + "\n")
                saved += 1
        return saved


def _load_seen_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    seen: set[str] = set()
    for line in path.read_text().splitlines():
        if line.strip():
            seen.add(json.loads(line)["source_url"])
    return seen


def build_discover_service(
    *,
    perplexity_api_key: str,
    audit_jsonl_path: Path,
    leads_jsonl_path: Path | None = None,
    hunter_api_key: str | None = None,
    db: Client | None = None,
) -> DiscoverService:
    engine = build_lead_gen_engine(
        perplexity_api_key=perplexity_api_key,
        hunter_api_key=hunter_api_key,
        audit_jsonl_path=audit_jsonl_path,
        db=db,
    )
    return DiscoverService(engine, db=db, leads_jsonl_path=leads_jsonl_path)
