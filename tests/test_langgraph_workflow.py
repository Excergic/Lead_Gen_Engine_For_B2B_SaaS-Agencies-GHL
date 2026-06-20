"""
Tests for LangGraph pipeline orchestration.

All external I/O (Perplexity, Hunter, etc.) is mocked so these tests run
offline.  The assertions verify:
  1. Graph builds and compiles without error
  2. Each node is called with the correct arguments
  3. State accumulates correctly across stages
  4. Config flags (run_discover / run_enrich / run_personalize) skip stages
  5. PipelineRunner protocol is satisfied
  6. Errors in one node don't crash the graph — they land in state["errors"]
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.engine.base import PipelineConfig, PipelineResult, PipelineRunner
from app.engine.langgraph_workflow import (
    LangGraphPipelineRunner,
    LeadGenState,
    build_lead_gen_graph,
)
from app.tools.enrichment.models import EnrichedLead, EnrichmentSource
from app.tools.models import Channel, ICPId, LeadCandidate, LeadStatus
from app.tools.personalize.models import (
    ClientContext,
    OutreachDraft,
    ProspectSignals,
    SignalType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_lead(n: int = 1) -> LeadCandidate:
    return LeadCandidate(
        id=str(uuid.uuid4()),
        icp_id=ICPId.SAAS_REVENUE,
        channel=Channel.LINKEDIN,
        company_name=f"Acme Corp {n}",
        contact_name=f"Alice {n}",
        source_url=f"https://example.com/lead/{n}",
        signal="Growing SaaS company",
    )


def _make_enriched(lead: LeadCandidate) -> EnrichedLead:
    enriched = EnrichedLead.from_lead(lead)
    enriched.email = f"alice{lead.company_name}@example.com"
    enriched.linkedin_url = "https://linkedin.com/in/alice"
    enriched.profile_source = EnrichmentSource.PERPLEXITY_PROFILE
    enriched.finalize()
    return enriched


def _make_draft(enriched: EnrichedLead) -> OutreachDraft:
    return OutreachDraft(
        lead_id=enriched.id,
        contact_name=enriched.contact_name,
        company_name=enriched.company_name,
        email=enriched.email,
        subject="Quick question about your outbound",
        body="Hi Alice, noticed you just launched …",
        hook="recent product launch",
        signal_used="Product launch post on LinkedIn",
        signal_type=SignalType.PRODUCT_LAUNCH,
        signals=ProspectSignals(strongest_signal="product launch", confidence=0.8),
    )


@pytest.fixture()
def mock_discover_agent():
    agent = MagicMock()
    leads = [_make_lead(i) for i in range(3)]
    agent.discover_all.return_value = leads
    return agent


@pytest.fixture()
def mock_enrich_agent():
    agent = MagicMock()

    def _enrich_batch(leads):
        return [_make_enriched(l) for l in leads]

    agent.enrich_batch.side_effect = _enrich_batch
    return agent


@pytest.fixture()
def mock_personalize_agent():
    agent = MagicMock()

    def _personalize_batch(enriched, client):
        return [_make_draft(e) for e in enriched]

    agent.personalize_batch.side_effect = _personalize_batch
    return agent


# ---------------------------------------------------------------------------
# 1. Graph compiles
# ---------------------------------------------------------------------------

def test_graph_compiles(mock_discover_agent, mock_enrich_agent, mock_personalize_agent):
    graph = build_lead_gen_graph(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    assert graph is not None


# ---------------------------------------------------------------------------
# 2. Full pipeline run (discover + enrich + personalize)
# ---------------------------------------------------------------------------

def test_full_pipeline_run(mock_discover_agent, mock_enrich_agent, mock_personalize_agent):
    runner = LangGraphPipelineRunner(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    cfg = PipelineConfig(
        max_results=3,
        run_discover=True,
        run_enrich=True,
        run_personalize=True,
    )
    result = runner.run(cfg)

    assert isinstance(result, PipelineResult)
    assert len(result.leads) == 3
    assert len(result.enriched) == 3
    assert len(result.drafts) == 3
    assert result.errors == []

    mock_discover_agent.discover_all.assert_called_once_with(icps=None, max_results=3)
    mock_enrich_agent.enrich_batch.assert_called_once()
    mock_personalize_agent.personalize_batch.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Discover-only run
# ---------------------------------------------------------------------------

def test_discover_only(mock_discover_agent, mock_enrich_agent, mock_personalize_agent):
    runner = LangGraphPipelineRunner(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    cfg = PipelineConfig(run_discover=True, run_enrich=False, run_personalize=False)
    result = runner.run(cfg)

    assert len(result.leads) == 3
    assert result.enriched == []
    assert result.drafts == []

    mock_discover_agent.discover_all.assert_called_once()
    mock_enrich_agent.enrich_batch.assert_not_called()
    mock_personalize_agent.personalize_batch.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Enrich-only (seed_leads provided, skip discover)
# ---------------------------------------------------------------------------

def test_enrich_only_with_seed_leads(mock_discover_agent, mock_enrich_agent, mock_personalize_agent):
    seeds = [_make_lead(10), _make_lead(11)]
    runner = LangGraphPipelineRunner(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    cfg = PipelineConfig(
        run_discover=False,
        run_enrich=True,
        run_personalize=False,
        seed_leads=seeds,
        enrich_limit=10,
    )
    result = runner.run(cfg)

    assert result.leads == []          # discover was skipped
    assert len(result.enriched) == 2
    mock_discover_agent.discover_all.assert_not_called()
    mock_enrich_agent.enrich_batch.assert_called_once_with(seeds)


# ---------------------------------------------------------------------------
# 5. Personalize-only (seed_enriched provided)
# ---------------------------------------------------------------------------

def test_personalize_only_with_seed_enriched(
    mock_discover_agent, mock_enrich_agent, mock_personalize_agent
):
    seed_lead = _make_lead(20)
    seed_enriched = [_make_enriched(seed_lead)]
    runner = LangGraphPipelineRunner(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    cfg = PipelineConfig(
        run_discover=False,
        run_enrich=False,
        run_personalize=True,
        seed_enriched=seed_enriched,
        personalize_limit=5,
    )
    result = runner.run(cfg)

    assert result.leads == []
    assert result.enriched == []
    assert len(result.drafts) == 1
    mock_discover_agent.discover_all.assert_not_called()
    mock_enrich_agent.enrich_batch.assert_not_called()
    mock_personalize_agent.personalize_batch.assert_called_once()


# ---------------------------------------------------------------------------
# 6. Errors in a node are captured, not raised
# ---------------------------------------------------------------------------

def test_discover_error_captured(mock_enrich_agent, mock_personalize_agent):
    bad_discover = MagicMock()
    bad_discover.discover_all.side_effect = RuntimeError("Perplexity timeout")

    runner = LangGraphPipelineRunner(bad_discover, mock_enrich_agent, mock_personalize_agent)
    cfg = PipelineConfig(run_discover=True, run_enrich=True, run_personalize=False)
    result = runner.run(cfg)

    assert any("discover" in e for e in result.errors)
    # Enrich still runs but has nothing to process
    assert result.enriched == []


# ---------------------------------------------------------------------------
# 7. PipelineRunner Protocol is satisfied
# ---------------------------------------------------------------------------

def test_protocol_satisfied(mock_discover_agent, mock_enrich_agent, mock_personalize_agent):
    runner = LangGraphPipelineRunner(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    assert isinstance(runner, PipelineRunner)


# ---------------------------------------------------------------------------
# 8. enrich_limit is respected
# ---------------------------------------------------------------------------

def test_enrich_limit(mock_enrich_agent, mock_personalize_agent):
    discover = MagicMock()
    discover.discover_all.return_value = [_make_lead(i) for i in range(10)]

    runner = LangGraphPipelineRunner(discover, mock_enrich_agent, mock_personalize_agent)
    cfg = PipelineConfig(
        run_discover=True,
        run_enrich=True,
        run_personalize=False,
        enrich_limit=4,
    )
    result = runner.run(cfg)

    called_with = mock_enrich_agent.enrich_batch.call_args[0][0]
    assert len(called_with) == 4


# ---------------------------------------------------------------------------
# 9. metadata contains stage flags
# ---------------------------------------------------------------------------

def test_metadata_contains_stages(mock_discover_agent, mock_enrich_agent, mock_personalize_agent):
    runner = LangGraphPipelineRunner(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    cfg = PipelineConfig(run_discover=True, run_enrich=True, run_personalize=False)
    result = runner.run(cfg)

    assert result.metadata["stages_requested"]["discover"] is True
    assert result.metadata["stages_requested"]["enrich"] is True
    assert result.metadata["stages_requested"]["personalize"] is False


# ---------------------------------------------------------------------------
# 10. Custom ClientContext is passed to personalize
# ---------------------------------------------------------------------------

def test_custom_client_context(mock_discover_agent, mock_enrich_agent, mock_personalize_agent):
    seed_lead = _make_lead(99)
    seed_enriched = [_make_enriched(seed_lead)]
    custom_ctx = ClientContext(offer_headline="My Custom Offer")

    runner = LangGraphPipelineRunner(
        mock_discover_agent, mock_enrich_agent, mock_personalize_agent
    )
    cfg = PipelineConfig(
        run_discover=False,
        run_enrich=False,
        run_personalize=True,
        seed_enriched=seed_enriched,
        client_context=custom_ctx,
    )
    runner.run(cfg)

    _, kwargs_or_args = mock_personalize_agent.personalize_batch.call_args
    passed_client = mock_personalize_agent.personalize_batch.call_args[0][1]
    assert passed_client.offer_headline == "My Custom Offer"
