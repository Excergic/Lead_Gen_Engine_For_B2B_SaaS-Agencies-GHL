from __future__ import annotations

import logging
from typing import Any

from app.tools.email.smtp_sender import SmtpEmailSender
from app.tools.personalize.models import OutreachDraft

logger = logging.getLogger(__name__)


class SendEmailTool:
    """
    HITL-gated email send. NEVER called by agents directly.

    Modes:
      dry_run=True (default)          — logs intent only, email NOT sent.
      dry_run=False + smtp configured — sends via SMTP after HITL approval.
      dry_run=False + no smtp         — raises RuntimeError with config guidance.
    """

    name = "send_email"
    description = (
        "Send an approved outreach email. BLOCKED unless draft status is 'approved'. "
        "Operator-only. Human must approve first, then explicitly trigger send."
    )

    def __init__(
        self,
        *,
        dry_run: bool = True,
        smtp: SmtpEmailSender | None = None,
    ) -> None:
        self._dry_run = dry_run
        self._smtp = smtp

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
                "draft_id": d.id,
                "message": (
                    "Dry-run mode — email NOT sent. "
                    "Set EMAIL_DRY_RUN=false and configure SMTP to send live."
                ),
            }

        # Live send
        if not self._smtp:
            raise RuntimeError(
                "EMAIL_DRY_RUN=false but SMTP is not configured. "
                "Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM_ADDRESS in your .env."
            )

        result = self._smtp.send(
            to=d.email,
            subject=d.subject,
            body=d.body,
        )
        result["draft_id"] = d.id
        logger.info(
            "email_sent draft_id=%s to=%s subject=%s",
            d.id,
            d.email,
            d.subject,
        )
        return result
