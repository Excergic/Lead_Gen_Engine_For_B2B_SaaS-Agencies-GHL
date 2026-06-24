from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.tools.audit import ToolAuditLogger
from app.tools.enrichment.providers import (
    EmailWaterfallTool,
    ProfileEnrichTool,
    enrich_email_parameters,
    enrich_profile_parameters,
)
from app.tools.enrichment.scoring import ScoreSignalTool, score_signal_parameters
from app.tools.executor import ToolExecutor
from app.tools.personalize.outreach_tools import (
    ResearchProspectSignalsTool,
    WriteOutreachTool,
    research_signals_parameters,
    write_outreach_parameters,
)
from app.tools.email.smtp_sender import SmtpEmailSender
from app.tools.personalize.send_email import SendEmailTool
from app.tools.perplexity import PerplexityWebSearchTool, perplexity_tool_parameters
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolRegistry, ToolSpec


@dataclass
class ToolingBundle:
    registry: ToolRegistry
    policy: ToolPolicy
    audit: ToolAuditLogger
    executor: ToolExecutor


def build_tooling(
    *,
    perplexity_api_key: str,
    hunter_api_key: str | None = None,
    apollo_api_key: str | None = None,
    audit_jsonl_path: Path | None = None,
    db: Any | None = None,
    email_dry_run: bool = True,
    smtp: SmtpEmailSender | None = None,
) -> ToolingBundle:
    registry = ToolRegistry()
    policy = ToolPolicy()
    audit = ToolAuditLogger(jsonl_path=audit_jsonl_path, db=db)

    search = PerplexityWebSearchTool(api_key=perplexity_api_key)
    registry.register(
        ToolSpec(
            name=search.name,
            description=search.description,
            handler=search.run,
            parameters=perplexity_tool_parameters(),
            timeout_seconds=30.0,
            max_retries=2,
        )
    )

    profile = ProfileEnrichTool(api_key=perplexity_api_key)
    registry.register(
        ToolSpec(
            name=profile.name,
            description=profile.description,
            handler=profile.run,
            parameters=enrich_profile_parameters(),
            timeout_seconds=45.0,
            max_retries=1,
        )
    )

    email = EmailWaterfallTool(
        perplexity_api_key=perplexity_api_key,
        hunter_api_key=hunter_api_key,
        apollo_api_key=apollo_api_key,
    )
    registry.register(
        ToolSpec(
            name=email.name,
            description=email.description,
            handler=email.run,
            parameters=enrich_email_parameters(),
            timeout_seconds=30.0,
            max_retries=1,
        )
    )

    signals = ResearchProspectSignalsTool(api_key=perplexity_api_key)
    registry.register(
        ToolSpec(
            name=signals.name,
            description=signals.description,
            handler=signals.run,
            parameters=research_signals_parameters(),
            timeout_seconds=60.0,
            max_retries=1,
        )
    )

    outreach = WriteOutreachTool(api_key=perplexity_api_key)
    registry.register(
        ToolSpec(
            name=outreach.name,
            description=outreach.description,
            handler=outreach.run,
            parameters=write_outreach_parameters(),
            timeout_seconds=45.0,
            max_retries=1,
        )
    )

    send_email = SendEmailTool(dry_run=email_dry_run, smtp=smtp)
    registry.register(
        ToolSpec(
            name=send_email.name,
            description=send_email.description,
            handler=send_email.run,
            parameters={
                "type": "object",
                "properties": {
                    "draft": {"type": "object"},
                    "draft_id": {"type": "string"},
                },
            },
            timeout_seconds=15.0,
            max_retries=0,
        )
    )

    score = ScoreSignalTool(api_key=perplexity_api_key)
    registry.register(
        ToolSpec(
            name=score.name,
            description=score.description,
            handler=score.run,
            parameters=score_signal_parameters(),
            timeout_seconds=30.0,
            max_retries=1,
        )
    )

    executor = ToolExecutor(registry=registry, policy=policy, audit=audit)
    return ToolingBundle(registry=registry, policy=policy, audit=audit, executor=executor)
