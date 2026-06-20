from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.tools.enrichment.providers import _parse_json_content
from app.tools.personalize.defaults import normalize_outreach_text
from app.tools.personalize.models import (
    ClientContext,
    OutreachMessage,
    ProspectSignals,
    RevenueTrend,
    SignalType,
)

logger = logging.getLogger(__name__)

PERPLEXITY_CHAT_URL = "https://api.perplexity.ai/chat/completions"

SIGNALS_SYSTEM = """You research B2B prospects for hyper-personalized cold outreach.
Search recent public activity (LinkedIn posts, news, product pages, job posts).
Return ONLY valid JSON:
{
  "contact_name": "string|null",
  "company_name": "string|null",
  "revenue_trend": "up|down|stable|unknown",
  "revenue_notes": "string — e.g. scaled to $113k MRR, revenue declining, etc.",
  "new_features": ["recent product/feature launches"],
  "new_workflows": ["new processes, tools, or workflows they adopted"],
  "hiring_signals": ["SDR hire, head of sales, etc."],
  "funding_signals": ["Series A, raised $X"],
  "product_launches": ["launches in last 90 days"],
  "recent_posts_summary": "2-3 sentences on what they posted recently",
  "pain_indicators": ["outbound struggles, manual processes, no AI, etc."],
  "strongest_signal": "THE one hook-worthy fact — be specific",
  "strongest_signal_type": "revenue_up|revenue_down|new_feature|new_workflow|hiring|funding|product_launch|outbound_struggle|ai_gap|other",
  "hook_angle": "1 sentence on how to open the email referencing the signal",
  "confidence": 0.0-1.0,
  "sources": ["url1", "url2"]
}
Pick the strongest RECENT signal (last 90 days preferred). Do not invent facts."""

OUTREACH_SYSTEM = """You write cold outbound emails for B2B lead gen. Rules:
- Under 120 words in body
- First line MUST reference the specific signal provided — never generic
- Connect their pain to the offer naturally
- One clear CTA with the exact calendar_url provided — embed the full URL in the email
- Sign off with the exact sender_name provided (e.g. "Best,\\nDhaivat NJ") — NEVER use [Your Name] or placeholders
- Sound human, direct, peer-level — not salesy
- Follow messaging dos and avoid messaging donts
Return ONLY valid JSON:
{
  "subject": "string — specific, not clickbait",
  "body": "string — full email with greeting, CTA with calendar_url, and sign-off with sender_name",
  "hook": "string — the opening line only",
  "signal_used": "string — which signal you referenced",
  "signal_type": "same enum as input"
}"""


class ResearchProspectSignalsTool:
    name = "research_prospect_signals"
    description = (
        "Deep research on a prospect's recent activity: revenue trends, new features, "
        "workflows, hiring, funding, posts. Returns the strongest hook signal."
    )

    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def run(
        self,
        *,
        contact_name: str | None = None,
        company_name: str | None = None,
        linkedin_url: str | None = None,
        source_url: str | None = None,
        industry: str | None = None,
        icp_id: str | None = None,
    ) -> ProspectSignals:
        target = linkedin_url or source_url or company_name or contact_name
        prompt = (
            f"Research recent activity (last 90 days) for this B2B prospect:\n"
            f"Contact: {contact_name or 'unknown'}\n"
            f"Company: {company_name or 'unknown'}\n"
            f"Industry: {industry or 'unknown'}\n"
            f"ICP segment: {icp_id or 'unknown'}\n"
            f"Primary URL: {target}\n\n"
            f"Find: revenue up/down, new features, workflows they added, hiring, "
            f"funding, recent LinkedIn/social posts, outbound or AI gaps."
        )
        data = self._chat(prompt, SIGNALS_SYSTEM)
        return _to_signals(data)

    def _chat(self, user_prompt: str, system: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(PERPLEXITY_CHAT_URL, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json_content(content)


class WriteOutreachTool:
    name = "write_outreach"
    description = (
        "Write a personalized cold email using the strongest prospect signal "
        "and client offer/messaging rules. Does NOT send — draft only."
    )

    def __init__(self, api_key: str, timeout: float = 45.0) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._researcher = ResearchProspectSignalsTool(api_key, timeout=timeout)

    def run(
        self,
        *,
        signals: ProspectSignals | dict[str, Any],
        client: ClientContext | dict[str, Any],
        contact_name: str | None = None,
    ) -> OutreachMessage:
        sig = signals if isinstance(signals, ProspectSignals) else ProspectSignals.model_validate(signals)
        ctx = client if isinstance(client, ClientContext) else ClientContext.model_validate(client)
        name = contact_name or sig.contact_name or "there"

        user_prompt = json.dumps(
            {
                "prospect_name": name,
                "company": sig.company_name,
                "strongest_signal": sig.strongest_signal,
                "strongest_signal_type": sig.strongest_signal_type.value,
                "hook_angle": sig.hook_angle,
                "recent_activity": sig.recent_posts_summary,
                "pain_indicators": sig.pain_indicators,
                "offer_headline": ctx.offer_headline,
                "offer_description": ctx.offer_description,
                "value_proposition": ctx.value_proposition,
                "pain_points": ctx.pain_points,
                "messaging_dos": ctx.messaging_dos,
                "messaging_donts": ctx.messaging_donts,
                "calendar_url": ctx.calendar_url,
                "sender_name": ctx.sender_name,
            },
            indent=2,
        )

        data = self._researcher._chat(
            f"Write a cold email for this prospect:\n{user_prompt}",
            OUTREACH_SYSTEM,
        )
        signal_type = data.get("signal_type", sig.strongest_signal_type.value)
        try:
            st = SignalType(signal_type)
        except ValueError:
            st = sig.strongest_signal_type

        body = normalize_outreach_text(data.get("body", ""), ctx)
        hook = normalize_outreach_text(data.get("hook", ""), ctx)

        return OutreachMessage(
            subject=data.get("subject", "Quick question"),
            body=body,
            hook=hook,
            signal_used=data.get("signal_used") or sig.strongest_signal or "",
            signal_type=st,
            raw=data,
        )


def _to_signals(data: dict[str, Any]) -> ProspectSignals:
    trend = data.get("revenue_trend", "unknown")
    try:
        revenue_trend = RevenueTrend(trend)
    except ValueError:
        revenue_trend = RevenueTrend.UNKNOWN

    sig_type = data.get("strongest_signal_type", "other")
    try:
        strongest_signal_type = SignalType(sig_type)
    except ValueError:
        strongest_signal_type = SignalType.OTHER

    return ProspectSignals(
        contact_name=data.get("contact_name"),
        company_name=data.get("company_name"),
        revenue_trend=revenue_trend,
        revenue_notes=data.get("revenue_notes"),
        new_features=data.get("new_features") or [],
        new_workflows=data.get("new_workflows") or [],
        hiring_signals=data.get("hiring_signals") or [],
        funding_signals=data.get("funding_signals") or [],
        product_launches=data.get("product_launches") or [],
        recent_posts_summary=data.get("recent_posts_summary"),
        pain_indicators=data.get("pain_indicators") or [],
        strongest_signal=data.get("strongest_signal"),
        strongest_signal_type=strongest_signal_type,
        hook_angle=data.get("hook_angle"),
        confidence=float(data.get("confidence") or 0.5),
        sources=data.get("sources") or [],
        raw=data,
    )


def research_signals_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "contact_name": {"type": "string"},
            "company_name": {"type": "string"},
            "linkedin_url": {"type": "string"},
            "source_url": {"type": "string"},
            "industry": {"type": "string"},
            "icp_id": {"type": "string"},
        },
    }


def write_outreach_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "signals": {"type": "object"},
            "client": {"type": "object"},
            "contact_name": {"type": "string"},
        },
        "required": ["signals", "client"],
    }
