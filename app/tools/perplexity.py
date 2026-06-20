from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.tools.models import Channel, SearchHit

logger = logging.getLogger(__name__)

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"


class PerplexityWebSearchTool:
    """Perplexity Search API — ranked web results for lead discovery."""

    name = "perplexity_web_search"
    description = (
        "Search the live web for ICP prospects. Filter by domain for LinkedIn, X, "
        "Reddit, or Google Maps. Returns title, url, snippet, date."
    )

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def run(
        self,
        *,
        query: str,
        max_results: int = 10,
        domains: list[str] | None = None,
        channel: Channel = Channel.WEB,
    ) -> list[SearchHit]:
        payload: dict[str, Any] = {"query": query, "max_results": max_results}
        if domains:
            payload["search_domain_filter"] = domains

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(PERPLEXITY_SEARCH_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        hits: list[SearchHit] = []
        for item in data.get("results", []):
            hits.append(
                SearchHit(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    date=item.get("date") or item.get("last_updated"),
                    source=channel,
                )
            )
        return hits


def perplexity_tool_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "default": 10},
            "domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Allowlist domains e.g. linkedin.com",
            },
            "channel": {
                "type": "string",
                "enum": [c.value for c in Channel],
            },
        },
        "required": ["query"],
    }


def run_with_retry(
    handler: Any,
    *,
    max_retries: int,
    **kwargs: Any,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return handler(**kwargs)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code in {429, 500, 502, 503, 504} and attempt < max_retries:
                wait = 2**attempt
                logger.warning("perplexity_retry attempt=%s wait=%ss", attempt + 1, wait)
                time.sleep(wait)
                continue
            raise
        except httpx.TimeoutException as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(2**attempt)
                continue
            raise
    raise last_exc  # type: ignore[misc]
