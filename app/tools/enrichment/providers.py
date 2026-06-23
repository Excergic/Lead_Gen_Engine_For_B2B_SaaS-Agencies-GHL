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
    """Parse JSON from LLM output (markdown fences, prose wrappers, trailing text)."""
    if not content or not content.strip():
        raise ValueError("empty LLM response")

    text = content.strip()

    # Fenced ```json ... ``` block
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    # Strip outer fences when model omits the json tag
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    # First JSON object only (fixes "Extra data: line N" when model adds prose after JSON)
    try:
        obj, _end = json.JSONDecoder().raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Last resort: substring from first { to last }
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        chunk = text[start : end + 1]
        obj, _end = json.JSONDecoder().raw_decode(chunk)
        if isinstance(obj, dict):
            return obj

    raise ValueError(f"no JSON object in LLM response ({len(content)} chars)")


def _linkedin_profile_from_source(url: str) -> str | None:
    """Normalize LinkedIn post/activity URLs to a profile URL for Apollo matching."""
    clean = url.split("?")[0]
    if "linkedin.com/in/" in clean.lower():
        return clean
    post = re.search(r"linkedin\.com/posts/([a-zA-Z0-9_-]+)", clean, re.IGNORECASE)
    if post:
        handle = post.group(1).split("_")[0]
        if handle:
            return f"https://www.linkedin.com/in/{handle}"
    return None


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
            linkedin_url=data.get("linkedin_url") or _linkedin_profile_from_source(source_url),
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
        if not content:
            raise ValueError("empty Perplexity message content")
        return _parse_json_content(content)


class ApolloEmailProvider:
    """Apollo.io People Match API — highest-quality B2B email lookup."""

    MATCH_URL = "https://api.apollo.io/v1/people/match"
    _forbidden_logged: bool = False  # class-level: log 403 guidance once per process

    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._disabled = False

    @classmethod
    def _log_forbidden_once(cls, detail: str) -> None:
        if cls._forbidden_logged:
            return
        cls._forbidden_logged = True
        logger.warning(
            "apollo_api_forbidden: %s — check APOLLO_API_KEY in .env (Settings → Integrations → "
            "API Keys). People enrichment needs a paid Apollo plan with API/credits enabled. "
            "Falling back to Hunter/Perplexity for email lookup.",
            detail,
        )

    def find_email(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        domain: str | None = None,
        linkedin_url: str | None = None,
        company_name: str | None = None,
    ) -> EmailEnrichment | None:
        if self._disabled:
            return None

        if linkedin_url:
            linkedin_url = _linkedin_profile_from_source(linkedin_url) or linkedin_url

        payload: dict[str, Any] = {"reveal_personal_emails": False}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if domain:
            payload["domain"] = domain
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url
        if company_name:
            payload["organization_name"] = company_name

        # Apollo needs linkedin_url OR (first + last + domain)
        has_name = bool(first_name and last_name and domain)
        if not (linkedin_url or has_name or (first_name and linkedin_url)):
            return None

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    self.MATCH_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "no-cache",
                        "X-Api-Key": self._api_key,
                    },
                    json=payload,
                )
                if resp.status_code == 404:
                    return None
                if resp.status_code in (401, 403):
                    self._disabled = True
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = resp.text[:200]
                    self._log_forbidden_once(str(detail))
                    return None
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.debug("apollo_request_failed: %s", exc)
            return None

        person = data.get("person") or {}
        email = person.get("email")
        if not email or "@" not in email:
            return None

        return EmailEnrichment(
            email=email,
            email_verified=person.get("email_status") == "verified",
            source=EnrichmentSource.APOLLO,
            confidence=0.9 if person.get("email_status") == "verified" else 0.75,
            raw=person,
        )


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
    """Apollo → Hunter → Perplexity waterfall (skips providers with no API key)."""

    name = "enrich_email"
    description = (
        "Find verified work email via provider waterfall: Apollo (best) → Hunter → "
        "Perplexity public-source lookup. Requires domain + name or LinkedIn URL."
    )

    def __init__(
        self,
        perplexity_api_key: str,
        hunter_api_key: str | None = None,
        apollo_api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._perplexity = PerplexityProfileEnricher(perplexity_api_key, timeout=timeout)
        self._apollo = ApolloEmailProvider(apollo_api_key, timeout=timeout) if apollo_api_key else None
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
        linkedin = linkedin_url
        if linkedin:
            linkedin = _linkedin_profile_from_source(linkedin) or linkedin
        elif source_url:
            linkedin = _linkedin_profile_from_source(source_url)

        # 1. Apollo — best quality B2B email data
        if self._apollo:
            result = self._apollo.find_email(
                first_name=first,
                last_name=last,
                domain=domain,
                linkedin_url=linkedin,
                company_name=company_name,
            )
            if result and result.email:
                return result

        # 2. Hunter — domain-based email finder
        if self._hunter and domain:
            result = self._hunter.find_email(
                domain=domain,
                first_name=first,
                last_name=last,
                company_name=company_name,
            )
            if result and result.email:
                return result

        # 3. Perplexity fallback — public-source email lookup
        context = (
            f"Company: {company_name or 'unknown'}\n"
            f"Domain: {domain or 'unknown'}\n"
            f"Contact: {contact_name or 'unknown'}\n"
            f"LinkedIn: {linkedin or source_url or 'unknown'}"
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
            logger.debug("perplexity_email_lookup_failed: %s", exc)

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
