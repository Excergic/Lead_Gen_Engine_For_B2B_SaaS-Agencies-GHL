from __future__ import annotations

import logging
from typing import Any

import httpx

from app.tools.enrichment.providers import PERPLEXITY_CHAT_URL, _parse_json_content

logger = logging.getLogger(__name__)

SCORE_SYSTEM = """You score a B2B sales lead for fit against a client's Ideal Customer Profile (ICP).
Return ONLY valid JSON:
{
  "score": <integer 0-100>,
  "reason": "<1 sentence explaining the score>"
}
Scoring guide: 80-100 = excellent fit, 60-79 = good fit, 40-59 = moderate fit, 0-39 = poor fit.
Base score on: job title relevance, company size/industry match, and any recent activity signals.
Fresh signals (< 24h old) indicate the prospect is actively in the market right now — weight them heavily."""


class ScoreSignalTool:
    name = "score_signal"
    description = (
        "Score a lead from 0–100 based on how well they match the client's ICP and offer. "
        "Returns an integer score and a 1-sentence justification."
    )

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def run(
        self,
        *,
        contact_name: str | None = None,
        job_title: str | None = None,
        company_name: str | None = None,
        company_size: str | None = None,
        industry: str | None = None,
        recent_activity: str | None = None,
        source_url: str | None = None,
        icp_description: str | None = None,
        offer_headline: str | None = None,
        pain_points: list[str] | None = None,
        signal_category: str | None = None,
        signal_freshness_hours: float | None = None,
    ) -> dict[str, Any]:
        # Build freshness label for the prompt
        freshness_label: str | None = None
        if signal_freshness_hours is not None:
            if signal_freshness_hours < 24:
                freshness_label = f"HOT — signal is only {signal_freshness_hours:.0f}h old (within 24h)"
            elif signal_freshness_hours < 72:
                freshness_label = f"WARM — signal is {signal_freshness_hours:.0f}h old"
            else:
                freshness_label = f"Signal age: {signal_freshness_hours / 24:.0f} days old"

        lead_lines = [
            f"Contact: {contact_name}" if contact_name else None,
            f"Title: {job_title}" if job_title else None,
            f"Company: {company_name}" if company_name else None,
            f"Company size: {company_size}" if company_size else None,
            f"Industry: {industry}" if industry else None,
            f"Signal type: {signal_category}" if signal_category else None,
            f"Signal freshness: {freshness_label}" if freshness_label else None,
            f"Recent activity: {recent_activity[:300]}" if recent_activity else None,
            f"Profile: {source_url}" if source_url else None,
        ]
        client_lines = [
            f"ICP: {icp_description}" if icp_description else None,
            f"Offer: {offer_headline}" if offer_headline else None,
            f"Pain points: {', '.join(pain_points)}" if pain_points else None,
        ]

        lead_ctx = "\n".join(x for x in lead_lines if x)
        client_ctx = "\n".join(x for x in client_lines if x) or "B2B SaaS / agency outbound"

        prompt = f"Score this B2B lead:\n\nLEAD:\n{lead_ctx}\n\nCLIENT TARGET:\n{client_ctx}"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": SCORE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(PERPLEXITY_CHAT_URL, headers=headers, json=payload)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
            data = _parse_json_content(content)
            base_score = max(0, min(100, int(data.get("score") or 0)))
            # Apply freshness bonus on top of LLM score (capped at 100)
            bonus = 0
            if signal_freshness_hours is not None:
                if signal_freshness_hours < 24:
                    bonus = 15
                elif signal_freshness_hours < 72:
                    bonus = 8
            final_score = min(100, base_score + bonus)
            return {
                "score": final_score,
                "reason": str(data.get("reason") or ""),
            }
        except Exception as exc:
            logger.debug("score_signal_failed: %s", exc)
            return {"score": 0, "reason": ""}


def score_signal_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "contact_name": {"type": "string"},
            "job_title": {"type": "string"},
            "company_name": {"type": "string"},
            "company_size": {"type": "string"},
            "industry": {"type": "string"},
            "recent_activity": {"type": "string"},
            "source_url": {"type": "string"},
            "icp_description": {"type": "string"},
            "offer_headline": {"type": "string"},
            "pain_points": {"type": "array", "items": {"type": "string"}},
        },
    }
