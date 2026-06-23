"""Discover agent — total lead cap across queries/channels."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agents.discover import DiscoverAgent
from app.tools.icp import ICP_PROFILES
from app.tools.models import Channel, SearchHit
from app.tools.policy import AgentRole


def _hit(url: str, n: int) -> SearchHit:
    return SearchHit(
        title=f"Contact {n}",
        url=url,
        snippet=f"snippet {n}",
    )


def test_discover_all_respects_total_max_results():
    executor = MagicMock()
    call_count = 0

    def _fake_run(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        # Return 5 hits per query — without a cap we'd accumulate hundreds
        return [_hit(f"https://linkedin.com/in/user{call_count}-{i}", i) for i in range(5)]

    executor.run.side_effect = _fake_run

    agent = DiscoverAgent(executor, actor=AgentRole.DISCOVER_AGENT)
    icp = ICP_PROFILES[0]
    # Single ICP, single channel, single query for deterministic test
    icp = icp.model_copy(update={"channels": [Channel.LINKEDIN]})

    with patch.object(agent, "_queries_for", return_value=["q1", "q2", "q3"]):
        leads = agent.discover_all(icps=[icp], max_results=7)

    assert len(leads) == 7
    urls = [l.source_url for l in leads]
    assert len(urls) == len(set(urls))
