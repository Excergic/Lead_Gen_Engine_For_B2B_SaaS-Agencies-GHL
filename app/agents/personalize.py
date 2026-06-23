from __future__ import annotations

import logging
from typing import Any

from app.services.outreach_queue import OutreachQueueStore
from app.tools.enrichment.models import EnrichedLead
from app.tools.executor import ToolExecutor
from app.tools.personalize.models import ClientContext, OutreachDraft
from app.tools.policy import AgentRole

logger = logging.getLogger(__name__)


class PersonalizeAgent:
    """
    Stage 5 PERSONALIZE:
    1. research_prospect_signals — recent revenue, features, workflows
    2. write_outreach — draft email tied to strongest signal
    3. queue for HITL — never auto-send
    """

    def __init__(
        self,
        executor: ToolExecutor,
        queue: OutreachQueueStore,
        actor: AgentRole = AgentRole.OUTREACH_AGENT,
    ) -> None:
        self.executor = executor
        self.queue = queue
        self.actor = actor

    def personalize_lead(
        self,
        lead: EnrichedLead,
        client: ClientContext,
    ) -> OutreachDraft:
        logger.info("personalize_start lead_id=%s", lead.id)

        signals = self.executor.run(
            self.actor,
            "research_prospect_signals",
            contact_name=lead.contact_name,
            company_name=lead.company_name,
            linkedin_url=lead.linkedin_url,
            source_url=lead.source_url,
            industry=lead.industry,
            icp_id=lead.icp_id.value,
        )

        message = self.executor.run(
            self.actor,
            "write_outreach",
            signals=signals.model_dump(),
            client=client.model_dump(),
            contact_name=lead.contact_name,
        )

        draft = OutreachDraft(
            lead_id=lead.id,
            lead_channel=lead.channel.value,
            contact_name=lead.contact_name or signals.contact_name,
            company_name=lead.company_name or signals.company_name,
            email=lead.email,
            subject=message.subject,
            body=message.body,
            hook=message.hook,
            signal_used=message.signal_used,
            signal_type=message.signal_type,
            signals=signals,
            status="pending_review",
            raw={"message": message.raw},
        )

        queued = self.queue.queue(draft)
        logger.info(
            "personalize_queued draft_id=%s signal=%s",
            queued.id,
            queued.signal_used[:80] if queued.signal_used else "",
        )
        return queued

    def personalize_batch(
        self,
        leads: list[EnrichedLead],
        client: ClientContext,
    ) -> list[OutreachDraft]:
        drafts: list[OutreachDraft] = []
        for lead in leads:
            try:
                drafts.append(self.personalize_lead(lead, client))
            except Exception as exc:
                logger.warning("personalize_failed lead_id=%s err=%s", lead.id, exc)
        return drafts
