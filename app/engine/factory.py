from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agents.discover import DiscoverAgent
from app.agents.enrich import EnrichAgent
from app.agents.personalize import PersonalizeAgent
from app.engine.base import PipelineRunner
from app.engine.langgraph_workflow import LangGraphPipelineRunner
from app.services.outreach_queue import OutreachQueueStore
from app.tools.email.smtp_sender import SmtpEmailSender
from app.tools.factory import ToolingBundle, build_tooling


@dataclass
class LeadGenEngine:
    tooling: ToolingBundle
    discover: DiscoverAgent
    enrich: EnrichAgent
    personalize: PersonalizeAgent
    queue: OutreachQueueStore
    workflow: PipelineRunner  # swap backend without touching agents/services


def build_lead_gen_engine(
    *,
    perplexity_api_key: str,
    hunter_api_key: str | None = None,
    audit_jsonl_path: Path | None = None,
    outreach_queue_jsonl: Path | None = None,
    db: Any | None = None,
    email_dry_run: bool = True,
    smtp: SmtpEmailSender | None = None,
) -> LeadGenEngine:
    tooling = build_tooling(
        perplexity_api_key=perplexity_api_key,
        hunter_api_key=hunter_api_key,
        audit_jsonl_path=audit_jsonl_path,
        db=db,
        email_dry_run=email_dry_run,
        smtp=smtp,
    )
    queue = OutreachQueueStore(
        jsonl_path=outreach_queue_jsonl or Path("data/outreach_queue.jsonl"),
        db=db,
    )
    discover = DiscoverAgent(tooling.executor)
    enrich = EnrichAgent(tooling.executor)
    personalize = PersonalizeAgent(tooling.executor, queue)
    workflow = LangGraphPipelineRunner(discover, enrich, personalize)
    return LeadGenEngine(
        tooling=tooling,
        discover=discover,
        enrich=enrich,
        personalize=personalize,
        queue=queue,
        workflow=workflow,
    )
