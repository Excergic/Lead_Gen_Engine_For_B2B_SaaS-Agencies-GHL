"""
Abstract pipeline orchestration interface.

Swap the concrete runner (LangGraph, CrewAI, plain Python, …) without
touching agents, tools, or services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.tools.enrichment.models import EnrichedLead
from app.tools.models import LeadCandidate
from app.tools.personalize.models import ClientContext, OutreachDraft


@dataclass
class PipelineConfig:
    """Inputs for one pipeline run."""

    # Discover — total unique leads to collect per run
    max_results: int = 20
    icp_ids: list[str] | None = None
    # Enrich / personalize default to same cap so each lead flows through all stages
    enrich_limit: int = 20
    personalize_limit: int = 20
    client_context: ClientContext | None = None
    # Stages to run (all True by default for a full run)
    run_discover: bool = True
    run_enrich: bool = True
    run_personalize: bool = False
    # Pre-loaded leads (skip discover if provided)
    seed_leads: list[LeadCandidate] | None = None
    # Pre-loaded enriched leads (skip discover+enrich if provided)
    seed_enriched: list[EnrichedLead] | None = None

    def pipeline_cap(self) -> int:
        """Max leads to process per stage in a full campaign run."""
        return self.max_results


@dataclass
class PipelineResult:
    """Outputs produced by a pipeline run."""

    leads: list[LeadCandidate] = field(default_factory=list)
    enriched: list[EnrichedLead] = field(default_factory=list)
    drafts: list[OutreachDraft] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PipelineRunner(Protocol):
    """
    Framework-agnostic contract every workflow backend must satisfy.

    Implementations: LangGraphPipelineRunner, …
    """

    def run(self, config: PipelineConfig) -> PipelineResult:
        """Execute the pipeline and return results."""
        ...
