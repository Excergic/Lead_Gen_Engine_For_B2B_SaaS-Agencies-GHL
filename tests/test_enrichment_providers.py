"""Enrichment provider helpers — JSON parsing and LinkedIn URL normalization."""
from __future__ import annotations

import pytest

from app.tools.enrichment.providers import _linkedin_profile_from_source, _parse_json_content


def test_parse_json_with_trailing_prose():
    raw = """{"contact_name": "Jane", "confidence": 0.8}
Here is additional commentary from the model."""
    data = _parse_json_content(raw)
    assert data["contact_name"] == "Jane"


def test_parse_json_in_markdown_fence():
    raw = """```json
{"email": "a@b.com", "confidence": 0.9}
```"""
    data = _parse_json_content(raw)
    assert data["email"] == "a@b.com"


def test_parse_json_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        _parse_json_content("   ")


def test_linkedin_post_url_to_profile():
    url = "https://www.linkedin.com/posts/basuakash_b2bsaas-b2bsales-activity-7363515328426905602-R78N"
    assert _linkedin_profile_from_source(url) == "https://www.linkedin.com/in/basuakash"


def test_linkedin_in_url_unchanged():
    url = "https://www.linkedin.com/in/jane-doe?trk=foo"
    assert _linkedin_profile_from_source(url) == "https://www.linkedin.com/in/jane-doe"
