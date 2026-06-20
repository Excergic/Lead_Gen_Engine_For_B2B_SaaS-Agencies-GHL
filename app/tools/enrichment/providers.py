from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.tools.enrichment.models import EmailEnrichment, EnrichmentSource, ProfileEnrichment

logger = logging.getLogger(__name__)

PERPLEXITY_CHAT_URL = "https://api.perplexity.ai/chat/completions"

PROFILE_SYSTEM = """You extract B2B prospect data from web/LinkedIn URLs for outbound sales.
Return ONLY valid JSON with these keys (use null if unknown):
{
  "contact_name": "string",
  "job_title": "string",
  "company_name": "string",
  "company_domain": "string (no https)",
  "linkedin_url": "string",
  "phone": "string",
  "company_size": "string",
  "industry": "string",
  "recent_activity": "string (1 sentence on what they posted/signal)",
  "confidence": 0.0-1.0
}
Do not invent emails. Only extract what the source supports."""

EMAIL_SYSTEM = """You find the most likely work email for a B2B prospect.
Return ONLY valid JSON:
{
  "email": "string or null",
  "confidence": 0.0-1.0,
  "reason": "string"
}
Only return an email if you have high confidence from public sources. Do not guess random patterns."""


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _split_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[-1]


class PerplexityProfileEnricher:
    def __init__(self, api_key: str, timeout: float = 45.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def run(
        self,
        *,
        source_url: str,
        company_name: str | None = None,
        contact_name: str | None = None,
        signal: str | None = None,
    ) -> ProfileEnrichment:
        context = f"URL: {source_url}"
        if company_name:
            context += f"\nCompany hint: {company_name}"
        if contact_name:
            context += f"\nContact hint: {contact_name}"
        if signal:
            context += f"\nSignal/snippet: {signal[:400]}"

        data = self._chat(
            f"Extract prospect profile data from this source:\n{context}",
            PROFILE_SYSTEM,
        )
        return ProfileEnrichment(
            contact_name=data.get("contact_name") or contact_name,
            job_title=data.get("job_title"),
            company_name=data.get("company_name") or company_name,
            company_domain=_clean_domain(data.get("company_domain")),
            linkedin_url=data.get("linkedin_url") or _linkedin_from_url(source_url),
            phone=data.get("phone"),
            company_size=data.get("company_size"),
            industry=data.get("industry"),
            recent_activity=data.get("recent_activity") or signal,
            source=EnrichmentSource.PERPLEXITY_PROFILE,
            confidence=float(data.get("confidence") or 0.5),
            raw=data,
        )

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
            "temperature": 0.1,
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(PERPLEXITY_CHAT_URL, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json_content(content)


class HunterEmailProvider:
    BASE = "https://api.hunter.io/v2"

    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def find_email(
        self,
        *,
        domain: str,
        first_name: str | None = None,
        last_name: str | None = None,
        company_name: str | None = None,
    ) -> EmailEnrichment | None:
        if first_name and last_name and domain:
            result = self._email_finder(domain, first_name, last_name)
            if result:
                return result
        return self._domain_search(domain, company_name)

    def _email_finder(self, domain: str, first_name: str, last_name: str) -> EmailEnrichment | None:
        params = {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": self._api_key,
        }
        data = self._get(f"{self.BASE}/email-finder", params)
        if not data or data.get("data", {}).get("email") is None:
            return None
        d = data["data"]
        return EmailEnrichment(
            email=d["email"],
            email_verified=d.get("verification", {}).get("status") == "valid",
            source=EnrichmentSource.HUNTER,
            confidence=0.85 if d.get("score", 0) >= 70 else 0.6,
            raw=d,
        )

    def _domain_search(self, domain: str, company_name: str | None) -> EmailEnrichment | None:
        params = {"domain": domain, "api_key": self._api_key, "limit": 5}
        data = self._get(f"{self.BASE}/domain-search", params)
        emails = (data or {}).get("data", {}).get("emails") or []
        if not emails:
            return None
        best = max(emails, key=lambda e: e.get("confidence", 0))
        return EmailEnrichment(
            email=best.get("value"),
            email_verified=best.get("verification", {}).get("status") == "valid",
            source=EnrichmentSource.HUNTER,
            confidence=min(0.9, (best.get("confidence") or 50) / 100),
            raw=best,
        )

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("hunter_request_failed: %s", exc)
            return None


class EmailWaterfallTool:
    """Prospeo → Hunter → Perplexity (playbook order; skips missing API keys)."""

    name = "enrich_email"
    description = (
        "Find verified work email via provider waterfall (Hunter when configured, "
        "then Perplexity public-source lookup). Requires domain + name when possible."
    )

    def __init__(
        self,
        perplexity_api_key: str,
        hunter_api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._perplexity = PerplexityProfileEnricher(perplexity_api_key, timeout=timeout)
        self._hunter = HunterEmailProvider(hunter_api_key, timeout=timeout) if hunter_api_key else None

    def run(
        self,
        *,
        domain: str | None = None,
        contact_name: str | None = None,
        company_name: str | None = None,
        linkedin_url: str | None = None,
        source_url: str | None = None,
    ) -> EmailEnrichment:
        first, last = _split_name(contact_name)

        if self._hunter and domain:
            result = self._hunter.find_email(
                domain=domain,
                first_name=first,
                last_name=last,
                company_name=company_name,
            )
            if result and result.email:
                return result

        # Perplexity fallback — public-source email lookup
        context = (
            f"Company: {company_name or 'unknown'}\n"
            f"Domain: {domain or 'unknown'}\n"
            f"Contact: {contact_name or 'unknown'}\n"
            f"LinkedIn: {linkedin_url or source_url or 'unknown'}"
        )
        try:
            data = self._perplexity._chat(
                f"Find the work email for this B2B prospect if publicly available:\n{context}",
                EMAIL_SYSTEM,
            )
            email = data.get("email")
            if email and "@" in email:
                return EmailEnrichment(
                    email=email,
                    email_verified=False,
                    source=EnrichmentSource.PERPLEXITY_PROFILE,
                    confidence=float(data.get("confidence") or 0.4),
                    raw=data,
                )
        except Exception as exc:
            logger.warning("perplexity_email_lookup_failed: %s", exc)

        return EmailEnrichment(source=EnrichmentSource.NONE, confidence=0.0)


class ProfileEnrichTool:
    name = "enrich_profile"
    description = (
        "Extract contact name, job title, company, domain, phone, and recent activity "
        "from a discovered prospect URL (LinkedIn, X, Reddit, etc.)."
    )

    def __init__(self, api_key: str, timeout: float = 45.0) -> None:
        self._enricher = PerplexityProfileEnricher(api_key, timeout=timeout)

    def run(
        self,
        *,
        source_url: str,
        company_name: str | None = None,
        contact_name: str | None = None,
        signal: str | None = None,
    ) -> ProfileEnrichment:
        return self._enricher.run(
            source_url=source_url,
            company_name=company_name,
            contact_name=contact_name,
            signal=signal,
        )


def _clean_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    d = domain.lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0]
    return d or None


def _linkedin_from_url(url: str) -> str | None:
    if "linkedin.com" in url:
        return url.split("?")[0]
    return None


def enrich_profile_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "source_url": {"type": "string"},
            "company_name": {"type": "string"},
            "contact_name": {"type": "string"},
            "signal": {"type": "string"},
        },
        "required": ["source_url"],
    }


def enrich_email_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "contact_name": {"type": "string"},
            "company_name": {"type": "string"},
            "linkedin_url": {"type": "string"},
            "source_url": {"type": "string"},
        },
    }
