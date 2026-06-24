"""
LangGraph implementation of PipelineRunner.

Graph: START → [discover] → [enrich] → [personalize] → END

Each node is a thin wrapper around the existing agent classes (DiscoverAgent,
EnrichAgent, PersonalizeAgent).  Stages are conditionally included via the
PipelineConfig flags so the same graph handles partial runs.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agents.discover import DiscoverAgent
from app.agents.enrich import EnrichAgent
from app.agents.personalize import PersonalizeAgent
from app.engine.base import PipelineConfig, PipelineResult, PipelineRunner
from app.tools.enrichment.models import EnrichedLead
from app.tools.models import ICPId, LeadCandidate
from app.tools.personalize.models import ClientContext, OutreachDraft

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangGraph shared state (TypedDict — append-only lists via operator.add)
# ---------------------------------------------------------------------------

def _concat(a: list, b: list) -> list:  # noqa: ANN001
    return a + b


class LeadGenState(TypedDict):
    config: PipelineConfig
    leads: Annotated[list[LeadCandidate], _concat]
    enriched: Annotated[list[EnrichedLead], _concat]
    drafts: Annotated[list[OutreachDraft], _concat]
    errors: Annotated[list[str], _concat]


# ---------------------------------------------------------------------------
# Node builders — each returns a callable that accepts & returns state dicts
# ---------------------------------------------------------------------------

def _make_discover_node(agent: DiscoverAgent):  # noqa: ANN001
    def discover_node(state: LeadGenState) -> dict[str, Any]:
        cfg: PipelineConfig = state["config"]
        if not cfg.run_discover:
            logger.info("langgraph:discover skipped (run_discover=False)")
            return {}

        icps = None
        if cfg.icp_ids:
            from app.tools.icp import ICP_PROFILES
            icps = [p for p in ICP_PROFILES if p.id in {ICPId(i) for i in cfg.icp_ids}]

        from app.tools.models import Channel as _Channel
        channels = [_Channel(c) for c in cfg.channels] if cfg.channels else None
        seen_urls: set[str] = set(cfg.seed_seen_urls) if cfg.seed_seen_urls else set()

        try:
            leads = agent.discover_all(
                icps=icps,
                max_results=cfg.max_results,
                channels=channels,
                seen_urls=seen_urls,
            )
            logger.info("langgraph:discover found=%d", len(leads))
            return {"leads": leads}
        except Exception as exc:
            logger.error("langgraph:discover error=%s", exc)
            return {"errors": [f"discover: {exc}"]}

    return discover_node


def _make_enrich_node(agent: EnrichAgent):  # noqa: ANN001
    def enrich_node(state: LeadGenState) -> dict[str, Any]:
        cfg: PipelineConfig = state["config"]
        if not cfg.run_enrich:
            logger.info("langgraph:enrich skipped (run_enrich=False)")
            return {}

        candidates = state.get("leads", [])
        if cfg.seed_leads:
            candidates = cfg.seed_leads + candidates

        cap = min(cfg.enrich_limit, cfg.pipeline_cap(), len(candidates))
        batch = candidates[:cap]
        if not batch:
            logger.info("langgraph:enrich no leads to process")
            return {}

        try:
            enriched = agent.enrich_batch(batch, client_context=cfg.client_context)
            logger.info("langgraph:enrich processed=%d", len(enriched))
            return {"enriched": enriched}
        except Exception as exc:
            logger.error("langgraph:enrich error=%s", exc)
            return {"errors": [f"enrich: {exc}"]}

    return enrich_node


def _make_personalize_node(agent: PersonalizeAgent):  # noqa: ANN001
    def personalize_node(state: LeadGenState) -> dict[str, Any]:
        cfg: PipelineConfig = state["config"]
        if not cfg.run_personalize:
            logger.info("langgraph:personalize skipped (run_personalize=False)")
            return {}

        enriched_leads = state.get("enriched", [])
        if cfg.seed_enriched:
            enriched_leads = cfg.seed_enriched + enriched_leads

        cap = min(cfg.personalize_limit, cfg.pipeline_cap(), len(enriched_leads))
        batch = enriched_leads[:cap]
        if not batch:
            logger.info("langgraph:personalize no enriched leads")
            return {}

        from app.tools.personalize.defaults import default_client_context

        client = cfg.client_context or default_client_context()
        try:
            drafts = agent.personalize_batch(batch, client)
            logger.info("langgraph:personalize queued=%d", len(drafts))
            return {"drafts": drafts}
        except Exception as exc:
            logger.error("langgraph:personalize error=%s", exc)
            return {"errors": [f"personalize: {exc}"]}

    return personalize_node


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_lead_gen_graph(
    discover: DiscoverAgent,
    enrich: EnrichAgent,
    personalize: PersonalizeAgent,
):
    """Compile a reusable LangGraph StateGraph."""
    builder = StateGraph(LeadGenState)

    builder.add_node("discover", _make_discover_node(discover))
    builder.add_node("enrich", _make_enrich_node(enrich))
    builder.add_node("personalize", _make_personalize_node(personalize))

    builder.add_edge(START, "discover")
    builder.add_edge("discover", "enrich")
    builder.add_edge("enrich", "personalize")
    builder.add_edge("personalize", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Concrete PipelineRunner backed by LangGraph
# ---------------------------------------------------------------------------

class LangGraphPipelineRunner:
    """
    Implements PipelineRunner via a compiled LangGraph StateGraph.

    Swap this for any other runner without touching agents or services.
    """

    def __init__(
        self,
        discover: DiscoverAgent,
        enrich: EnrichAgent,
        personalize: PersonalizeAgent,
    ) -> None:
        self._graph = build_lead_gen_graph(discover, enrich, personalize)

    def run(self, config: PipelineConfig) -> PipelineResult:
        initial: LeadGenState = {
            "config": config,
            "leads": [],
            "enriched": [],
            "drafts": [],
            "errors": [],
        }
        final = self._graph.invoke(initial)
        return PipelineResult(
            leads=final.get("leads", []),
            enriched=final.get("enriched", []),
            drafts=final.get("drafts", []),
            errors=final.get("errors", []),
            metadata={
                "stages_requested": {
                    "discover": config.run_discover,
                    "enrich": config.run_enrich,
                    "personalize": config.run_personalize,
                }
            },
        )
