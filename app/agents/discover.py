from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.tools.executor import ToolExecutor
from app.tools.icp import CHANNEL_DOMAINS, ICP_PROFILES
from app.tools.models import Channel, ICPProfile, LeadCandidate, SearchHit, SignalCategory
from app.tools.policy import AgentRole

logger = logging.getLogger(__name__)

MAX_QUERIES_PER_ICP_CHANNEL = 2
# Perplexity hits requested per search call (total run cap is `max_results` in discover_all)
PER_QUERY_RESULTS = 10

# ---------------------------------------------------------------------------
# Signal classification — keyword-based, no extra API call
# ---------------------------------------------------------------------------

_SIGNAL_KEYWORDS: list[tuple[SignalCategory, list[str]]] = [
    (SignalCategory.FUNDING, [
        "series a", "series b", "series c", "seed round", "raised $", "raised funding",
        "funding round", "investment round", "venture capital", "valuation", "term sheet",
    ]),
    (SignalCategory.LAYOFFS, [
        "layoffs", "laid off", "downsizing", "reducing headcount", "workforce reduction",
        "rif ", "cost cutting", "restructuring", "let go",
    ]),
    (SignalCategory.HIRING, [
        "hiring", "we're hiring", "head of sales", "vp of sales", "vp of marketing",
        "sdr", "account executive", "job opening", "open role", "looking for a",
    ]),
    (SignalCategory.PRODUCT_LAUNCH, [
        "launched", "just launched", "announcing", "new product", "just shipped",
        "released", "beta launch", "product launch", "going live",
    ]),
    (SignalCategory.COMPETITOR, [
        "competitor", "alternative to", " vs ", "switching from", "moved from",
        "replacing", "better than", "left hubspot", "left salesforce",
    ]),
    (SignalCategory.PAIN_POINT, [
        "struggling", "need help", "looking for help", "can't find", "problem with",
        "challenge", "frustrated", "bottleneck", "manual process", "no automation",
        "hard to", "difficult to", "can't scale",
    ]),
    (SignalCategory.ENGAGEMENT, [
        "commented on", "liked", "shared a post", "replied to", "reposted",
        "engaged with", "reacted to",
    ]),
]


def _classify_signal(text: str) -> SignalCategory:
    """Classify a signal snippet into a category using keyword matching."""
    text_lower = text.lower()
    for category, keywords in _SIGNAL_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return category
    return SignalCategory.OTHER


def _signal_freshness_hours(date_str: str | None) -> float | None:
    """Convert a search result date string to hours since now. Returns None if unparseable."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - dt
        hours = delta.total_seconds() / 3600
        return round(max(0.0, hours), 1)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# URL normalization — strip query params + convert LinkedIn post → profile
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """Normalize a URL for deduplication. Strips query params and converts
    LinkedIn post URLs to profile URLs so the same person is never double-counted."""
    url = url.strip().split("?")[0].split("#")[0].rstrip("/")
    # LinkedIn post → profile
    m = re.search(r"linkedin\.com/posts/([a-zA-Z0-9_-]+)", url, re.IGNORECASE)
    if m:
        handle = m.group(1).split("_")[0]
        if handle:
            return f"https://www.linkedin.com/in/{handle}"
    return url.lower()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

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
                    norm = _normalize_url(str(hit.url))
                    if norm in seen_urls:
                        continue
                    seen_urls.add(norm)
                    leads.append(
                        LeadCandidate(
                            icp_id=icp.id,
                            channel=channel,
                            company_name=_guess_company(hit.title),
                            contact_name=_guess_contact(hit.title),
                            signal=hit.snippet[:300] if hit.snippet else hit.title,
                            source_url=str(hit.url),
                            snippet=hit.snippet,
                            raw=hit.model_dump(),
                            signal_category=_classify_signal(hit.snippet or hit.title),
                            signal_freshness_hours=_signal_freshness_hours(hit.date),
                        )
                    )
        return leads

    def discover_all(
        self,
        icps: list[ICPProfile] | None = None,
        *,
        max_results: int = 20,
        seen_urls: set[str] | None = None,
        **kwargs: Any,
    ) -> list[LeadCandidate]:
        """
        Discover leads across ICPs until `max_results` total unique URLs are collected.

        `seen_urls` can be pre-seeded with URLs already in the DB so cross-run
        duplicates are skipped before they enter the pipeline.
        """
        icps = icps or ICP_PROFILES
        all_leads: list[LeadCandidate] = []
        # Copy so we don't mutate the caller's set; add normalized versions
        dedup: set[str] = {_normalize_url(u) for u in seen_urls} if seen_urls else set()

        for icp in icps:
            if len(all_leads) >= max_results:
                break
            remaining = max_results - len(all_leads)
            logger.info("discover_icp_start name=%s remaining=%s", icp.name, remaining)
            batch = self.discover_icp(icp, limit=remaining, seen_urls=dedup, **kwargs)
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
