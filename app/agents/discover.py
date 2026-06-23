from __future__ import annotations

import logging
from typing import Any

from app.tools.executor import ToolExecutor
from app.tools.icp import CHANNEL_DOMAINS, ICP_PROFILES
from app.tools.models import Channel, ICPProfile, LeadCandidate, SearchHit
from app.tools.policy import AgentRole

logger = logging.getLogger(__name__)

MAX_QUERIES_PER_ICP_CHANNEL = 2
# Perplexity hits requested per search call (total run cap is `max_results` in discover_all)
PER_QUERY_RESULTS = 10


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
        limit: int,
        seen_urls: set[str],
        channels: list[Channel] | None = None,
    ) -> list[LeadCandidate]:
        """Collect up to `limit` new leads for one ICP (deduped via shared seen_urls)."""
        channels = channels or icp.channels
        leads: list[LeadCandidate] = []

        for channel in channels:
            if len(leads) >= limit:
                break
            domains = CHANNEL_DOMAINS.get(channel)
            for query in self._queries_for(icp, channel):
                if len(leads) >= limit:
                    break
                per_query = min(PER_QUERY_RESULTS, limit - len(leads))
                try:
                    hits: list[SearchHit] = self.executor.run(
                        self.actor,
                        "perplexity_web_search",
                        query=query,
                        max_results=per_query,
                        domains=domains or None,
                        channel=channel,
                    )
                except Exception as exc:
                    logger.warning("discover_query_failed icp=%s channel=%s err=%s", icp.id, channel, exc)
                    continue

                for hit in hits:
                    if len(leads) >= limit:
                        break
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
        *,
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[LeadCandidate]:
        """
        Discover leads across ICPs until `max_results` total unique URLs are collected.

        `max_results` is the campaign-level cap (not per search query).
        """
        icps = icps or ICP_PROFILES
        all_leads: list[LeadCandidate] = []
        seen_urls: set[str] = set()

        for icp in icps:
            if len(all_leads) >= max_results:
                break
            remaining = max_results - len(all_leads)
            logger.info("discover_icp_start name=%s remaining=%s", icp.name, remaining)
            batch = self.discover_icp(icp, limit=remaining, seen_urls=seen_urls, **kwargs)
            logger.info("discover_icp_done name=%s count=%s", icp.name, len(batch))
            all_leads.extend(batch)

        return all_leads[:max_results]


def _guess_company(title: str) -> str | None:
    text = title.split("|")[0].split(" - ")[0].strip()
    return text[:120] if len(text) > 3 else None


def _guess_contact(title: str) -> str | None:
    if " - " in title:
        return title.split(" - ")[0].strip()[:80]
    return None
