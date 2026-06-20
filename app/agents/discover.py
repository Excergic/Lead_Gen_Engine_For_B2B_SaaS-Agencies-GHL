from __future__ import annotations

import logging
from typing import Any

from app.tools.executor import ToolExecutor
from app.tools.icp import CHANNEL_DOMAINS, ICP_PROFILES
from app.tools.models import Channel, ICPProfile, LeadCandidate, SearchHit
from app.tools.policy import AgentRole

logger = logging.getLogger(__name__)

MAX_QUERIES_PER_ICP_CHANNEL = 2


class DiscoverAgent:
    """Stage 2 DISCOVER — ICP × channel → gated perplexity_web_search tool calls."""

    def __init__(self, executor: ToolExecutor, actor: AgentRole = AgentRole.DISCOVER_AGENT) -> None:
        self.executor = executor
        self.actor = actor

    def _queries_for(self, icp: ICPProfile, channel: Channel) -> list[str]:
        domain_hint = CHANNEL_DOMAINS.get(channel, [])
        queries: list[str] = []
        for q in icp.search_queries:
            if any(d.replace("/maps", "") in q for d in domain_hint):
                queries.append(q)
            elif channel == Channel.WEB:
                queries.append(q)
            else:
                base = q.split(" site:")[0]
                if domain_hint:
                    queries.append(f"{base} site:{domain_hint[0]}")
        return queries[:MAX_QUERIES_PER_ICP_CHANNEL]

    def discover_icp(
        self,
        icp: ICPProfile,
        *,
        max_results: int = 5,
        channels: list[Channel] | None = None,
    ) -> list[LeadCandidate]:
        channels = channels or icp.channels
        leads: list[LeadCandidate] = []
        seen_urls: set[str] = set()

        for channel in channels:
            domains = CHANNEL_DOMAINS.get(channel)
            for query in self._queries_for(icp, channel):
                try:
                    hits: list[SearchHit] = self.executor.run(
                        self.actor,
                        "perplexity_web_search",
                        query=query,
                        max_results=max_results,
                        domains=domains or None,
                        channel=channel,
                    )
                except Exception as exc:
                    logger.warning("discover_query_failed icp=%s channel=%s err=%s", icp.id, channel, exc)
                    continue

                for hit in hits:
                    url = str(hit.url)
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    leads.append(
                        LeadCandidate(
                            icp_id=icp.id,
                            channel=channel,
                            company_name=_guess_company(hit.title),
                            contact_name=_guess_contact(hit.title),
                            signal=hit.snippet[:300] if hit.snippet else hit.title,
                            source_url=url,
                            snippet=hit.snippet,
                            raw=hit.model_dump(),
                        )
                    )
        return leads

    def discover_all(
        self,
        icps: list[ICPProfile] | None = None,
        **kwargs: Any,
    ) -> list[LeadCandidate]:
        icps = icps or ICP_PROFILES
        all_leads: list[LeadCandidate] = []
        for icp in icps:
            logger.info("discover_icp_start name=%s", icp.name)
            batch = self.discover_icp(icp, **kwargs)
            logger.info("discover_icp_done name=%s count=%s", icp.name, len(batch))
            all_leads.extend(batch)
        return all_leads


def _guess_company(title: str) -> str | None:
    text = title.split("|")[0].split(" - ")[0].strip()
    return text[:120] if len(text) > 3 else None


def _guess_contact(title: str) -> str | None:
    if " - " in title:
        return title.split(" - ")[0].strip()[:80]
    return None
