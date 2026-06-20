"""Default outreach identity + placeholder cleanup."""

from __future__ import annotations

import re

from app.config import Settings, get_settings
from app.tools.personalize.models import ClientContext


def default_client_context(settings: Settings | None = None) -> ClientContext:
    s = settings or get_settings()
    return ClientContext(
        offer_headline=s.outreach_offer_headline,
        offer_description=s.outreach_offer_description,
        value_proposition=s.outreach_value_proposition,
        calendar_url=s.outreach_calendar_url,
        sender_name=s.outreach_sender_name,
    )


def merge_client_context(
    definition,
    settings: Settings | None = None,
) -> ClientContext:
    """Layer Stage 1 definition over operator defaults."""
    base = default_client_context(settings)
    if not definition:
        return base
    return ClientContext(
        offer_headline=definition.offer_headline or base.offer_headline,
        offer_description=definition.offer_description or base.offer_description,
        value_proposition=definition.value_proposition or base.value_proposition,
        calendar_url=str(definition.calendar_url) if definition.calendar_url else base.calendar_url,
        sender_name=base.sender_name,
        messaging_dos=definition.messaging_dos or base.messaging_dos,
        messaging_donts=definition.messaging_donts or base.messaging_donts,
        pain_points=definition.pain_points or base.pain_points,
    )


_PLACEHOLDER_NAME = re.compile(
    r"\[(?:your name|insert your name|name)\]",
    re.IGNORECASE,
)
_PLACEHOLDER_CALENDAR = re.compile(
    r"\[(?:insert calendar url|calendar url|calendly link|booking link|calendar link)\]",
    re.IGNORECASE,
)


def normalize_outreach_text(text: str, ctx: ClientContext) -> str:
    """Replace LLM bracket placeholders with configured sender + Calendly link."""
    if not text:
        return text
    out = _PLACEHOLDER_NAME.sub(ctx.sender_name, text)
    if ctx.calendar_url:
        out = _PLACEHOLDER_CALENDAR.sub(ctx.calendar_url, out)
        # Bare "Book a call here:" with no link on the next segment
        if ctx.calendar_url not in out and "calendly.com" not in out.lower():
            out = re.sub(
                r"(book a (?:quick )?call(?: here)?[:.]?\s*)$",
                rf"\1{ctx.calendar_url}",
                out,
                flags=re.IGNORECASE | re.MULTILINE,
            )
    return out.strip()
