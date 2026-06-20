from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from supabase import Client

from app.engine.factory import LeadGenEngine
from app.services.outreach_queue import OutreachQueueStore
from app.services.stage1 import DefinitionService
from app.tools.personalize.defaults import merge_client_context
from app.tools.personalize.models import ClientContext, OutreachDraft
from app.tools.policy import AgentRole

logger = logging.getLogger(__name__)


class OutreachHitlService:
    """Human-in-the-loop: review, approve, reject, then explicitly send."""

    def __init__(
        self,
        engine: LeadGenEngine,
        queue: OutreachQueueStore,
        db: Client | None = None,
    ) -> None:
        self._engine = engine
        self._queue = queue
        self._definitions = DefinitionService(db) if db else None

    def list_pending(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return [_draft_view(d) for d in self._queue.list_pending(limit=limit)]

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self._require(draft_id)
        return _draft_view(draft)

    def approve(self, draft_id: str, *, reviewed_by: str = "operator") -> dict[str, Any]:
        draft = self._queue.approve(draft_id, reviewed_by=reviewed_by)
        logger.info("outreach_approved draft_id=%s", draft_id)
        return _draft_view(draft)

    def reject(
        self,
        draft_id: str,
        *,
        reason: str = "",
        reviewed_by: str = "operator",
    ) -> dict[str, Any]:
        draft = self._queue.reject(draft_id, reason=reason, reviewed_by=reviewed_by)
        logger.info("outreach_rejected draft_id=%s", draft_id)
        return _draft_view(draft)

    def update(
        self,
        draft_id: str,
        *,
        subject: str | None = None,
        body: str | None = None,
        hook: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        draft = self._queue.update(
            draft_id,
            subject=subject,
            body=body,
            hook=hook,
            email=email,
        )
        logger.info("outreach_updated draft_id=%s", draft_id)
        return _draft_view(draft)

    def send(self, draft_id: str) -> dict[str, Any]:
        draft = self._require(draft_id)
        if not draft.email or not draft.email.strip():
            raise ValueError(
                "No recipient email on this draft. Use Edit to add the prospect's email, then approve again."
            )
        if draft.status != "approved":
            raise ValueError(
                f"Draft must be approved before send (status={draft.status}). "
                "Call POST /outreach/{id}/approve first."
            )

        result = self._engine.tooling.executor.run(
            AgentRole.OPERATOR,
            "send_email",
            draft=draft,
        )
        sent = self._queue.mark_sent(draft_id)
        return {
            "draft": _draft_view(sent),
            "send_result": result,
        }

    def load_client_context(self, client_id: UUID | None) -> ClientContext:
        from app.tools.personalize.defaults import default_client_context

        if not client_id or not self._definitions:
            return default_client_context()
        definition = self._definitions.get_active(client_id)
        return merge_client_context(definition)

    def _require(self, draft_id: str) -> OutreachDraft:
        draft = self._queue.get(draft_id)
        if not draft:
            raise KeyError(f"Outreach draft '{draft_id}' not found")
        return draft


def _draft_view(draft: OutreachDraft) -> dict[str, Any]:
    sig = draft.signals
    return {
        "id": draft.id,
        "lead_id": draft.lead_id,
        "contact_name": draft.contact_name,
        "company_name": draft.company_name,
        "email": draft.email,
        "status": draft.status,
        "subject": draft.subject,
        "hook": draft.hook,
        "body": draft.body,
        "signal_used": draft.signal_used,
        "signal_type": draft.signal_type.value,
        "research": {
            "revenue_trend": sig.revenue_trend.value,
            "revenue_notes": sig.revenue_notes,
            "new_features": sig.new_features,
            "new_workflows": sig.new_workflows,
            "hiring_signals": sig.hiring_signals,
            "recent_posts_summary": sig.recent_posts_summary,
            "strongest_signal": sig.strongest_signal,
            "hook_angle": sig.hook_angle,
            "confidence": sig.confidence,
            "sources": sig.sources,
        },
        "created_at": draft.created_at.isoformat(),
        "reviewed_at": draft.reviewed_at.isoformat() if draft.reviewed_at else None,
        "reviewed_by": draft.reviewed_by,
        "rejection_reason": draft.rejection_reason,
        "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
    }
