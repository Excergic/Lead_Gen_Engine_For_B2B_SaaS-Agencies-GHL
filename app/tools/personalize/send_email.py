from __future__ import annotations

import logging
from typing import Any

from app.tools.personalize.models import OutreachDraft

logger = logging.getLogger(__name__)


class SendEmailTool:
    """
    HITL-gated email send. NEVER called by agents directly.
    Requires draft status=approved. Default: dry-run logs only.
    """

    name = "send_email"
    description = (
        "Send an approved outreach email. BLOCKED unless draft status is 'approved'. "
        "Operator-only. Human must approve first, then explicitly trigger send."
    )

    def __init__(self, *, dry_run: bool = True) -> None:
        self._dry_run = dry_run

    def run(
        self,
        *,
        draft: OutreachDraft | dict[str, Any],
        draft_id: str | None = None,
    ) -> dict[str, Any]:
        d = draft if isinstance(draft, OutreachDraft) else OutreachDraft.model_validate(draft)

        if d.status != "approved":
            raise PermissionError(
                f"HITL gate: draft must be 'approved' before send (current: {d.status}). "
                "Review and approve via POST /api/v1/outreach/{id}/approve first."
            )
        if not d.email:
            raise ValueError(f"No email on draft {d.id} — cannot send")

        if self._dry_run:
            logger.info(
                "DRY_RUN send_email to=%s subject=%s draft_id=%s",
                d.email,
                d.subject,
                d.id,
            )
            return {
                "sent": False,
                "dry_run": True,
                "to": d.email,
                "subject": d.subject,
                "message": "Dry-run mode — email NOT sent. Set EMAIL_DRY_RUN=false + SMTP to send.",
            }

        # Production: wire Instantly/Smartlead/SMTP here
        raise NotImplementedError("Live email sending not configured — use dry_run=True")
