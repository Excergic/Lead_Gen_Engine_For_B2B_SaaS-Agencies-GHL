from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from supabase import Client

from app.tools.personalize.models import OutreachDraft

logger = logging.getLogger(__name__)


class OutreachQueueStore:
    """HITL queue — drafts require human approve before send."""

    def __init__(self, jsonl_path: Path, db: Client | None = None) -> None:
        self._jsonl_path = jsonl_path
        self._db = db
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def queue(self, draft: OutreachDraft) -> OutreachDraft:
        draft.status = "pending_review"
        if self._db:
            self._insert_db(draft)
        self._append_jsonl(draft)
        return draft

    def list_pending(self, *, limit: int = 50) -> list[OutreachDraft]:
        if self._db:
            rows = (
                self._db.table("outreach_drafts")
                .select("*")
                .eq("status", "pending_review")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return [_row_to_draft(r) for r in rows.data]
        return self._list_jsonl(status="pending_review", limit=limit)

    def get(self, draft_id: str) -> OutreachDraft | None:
        if self._db:
            row = (
                self._db.table("outreach_drafts")
                .select("*")
                .eq("id", draft_id)
                .maybe_single()
                .execute()
            )
            if row and row.data:
                return _row_to_draft(row.data)
        for draft in self._load_all_jsonl():
            if draft.id == draft_id:
                return draft
        return None

    def approve(self, draft_id: str, *, reviewed_by: str = "operator") -> OutreachDraft:
        draft = self._require(draft_id)
        if draft.status != "pending_review":
            raise ValueError(f"Draft {draft_id} is not pending review (status={draft.status})")
        draft.status = "approved"
        draft.reviewed_at = datetime.now(UTC)
        draft.reviewed_by = reviewed_by
        self._update(draft)
        return draft

    def reject(self, draft_id: str, *, reason: str = "", reviewed_by: str = "operator") -> OutreachDraft:
        draft = self._require(draft_id)
        if draft.status != "pending_review":
            raise ValueError(f"Draft {draft_id} is not pending review")
        draft.status = "rejected"
        draft.reviewed_at = datetime.now(UTC)
        draft.reviewed_by = reviewed_by
        draft.rejection_reason = reason
        self._update(draft)
        return draft

    def mark_sent(self, draft_id: str) -> OutreachDraft:
        draft = self._require(draft_id)
        if draft.status != "approved":
            raise ValueError(
                f"Draft {draft_id} must be approved before send (status={draft.status}). "
                "Human approval required."
            )
        draft.status = "sent"
        draft.sent_at = datetime.now(UTC)
        self._update(draft)
        return draft

    def update(
        self,
        draft_id: str,
        *,
        subject: str | None = None,
        body: str | None = None,
        hook: str | None = None,
        email: str | None = None,
    ) -> OutreachDraft:
        draft = self._require(draft_id)
        if draft.status in ("sent", "rejected"):
            raise ValueError(f"Cannot edit draft with status={draft.status}")

        if subject is not None:
            draft.subject = subject
        if body is not None:
            draft.body = body
        if hook is not None:
            draft.hook = hook
        if email is not None:
            draft.email = email or None

        # Edited approved drafts need re-review before send
        if draft.status == "approved":
            draft.status = "pending_review"
            draft.reviewed_at = None
            draft.reviewed_by = None

        self._update(draft)
        return draft

    def _require(self, draft_id: str) -> OutreachDraft:
        draft = self.get(draft_id)
        if not draft:
            raise KeyError(f"Outreach draft '{draft_id}' not found")
        return draft

    def _append_jsonl(self, draft: OutreachDraft) -> None:
        with self._jsonl_path.open("a") as f:
            f.write(draft.model_dump_json() + "\n")

    def _load_all_jsonl(self) -> list[OutreachDraft]:
        if not self._jsonl_path.exists():
            return []
        by_id: dict[str, OutreachDraft] = {}
        for line in self._jsonl_path.read_text().splitlines():
            if line.strip():
                d = OutreachDraft.model_validate(json.loads(line))
                by_id[d.id] = d
        return list(by_id.values())

    def _list_jsonl(self, *, status: str, limit: int) -> list[OutreachDraft]:
        drafts = [d for d in self._load_all_jsonl() if d.status == status]
        drafts.sort(key=lambda d: d.created_at, reverse=True)
        return drafts[:limit]

    def _update(self, draft: OutreachDraft) -> None:
        if self._db:
            self._db.table("outreach_drafts").update(_draft_to_row(draft)).eq("id", draft.id).execute()
        drafts = self._load_all_jsonl()
        by_id = {d.id: d for d in drafts}
        by_id[draft.id] = draft
        self._jsonl_path.write_text(
            "\n".join(d.model_dump_json() for d in by_id.values()) + "\n"
        )

    def _insert_db(self, draft: OutreachDraft) -> None:
        try:
            self._db.table("outreach_drafts").insert(_draft_to_row(draft)).execute()
        except Exception as exc:
            logger.warning("outreach_db_insert_failed: %s", exc)


def _draft_to_row(draft: OutreachDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "lead_id": draft.lead_id,
        "contact_name": draft.contact_name,
        "company_name": draft.company_name,
        "email": draft.email,
        "subject": draft.subject,
        "body": draft.body,
        "hook": draft.hook,
        "signal_used": draft.signal_used,
        "signal_type": draft.signal_type.value,
        "signals": draft.signals.model_dump(),
        "status": draft.status,
        "created_at": draft.created_at.isoformat(),
        "reviewed_at": draft.reviewed_at.isoformat() if draft.reviewed_at else None,
        "reviewed_by": draft.reviewed_by,
        "rejection_reason": draft.rejection_reason,
        "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
        "raw": draft.raw,
    }


def _row_to_draft(row: dict[str, Any]) -> OutreachDraft:
    from app.tools.personalize.models import ProspectSignals, SignalType

    signals_data = row.get("signals") or {}
    if isinstance(signals_data, str):
        signals_data = json.loads(signals_data)
    return OutreachDraft(
        id=str(row["id"]),
        lead_id=str(row["lead_id"]),
        contact_name=row.get("contact_name"),
        company_name=row.get("company_name"),
        email=row.get("email"),
        subject=row["subject"],
        body=row["body"],
        hook=row.get("hook") or "",
        signal_used=row.get("signal_used") or "",
        signal_type=SignalType(row.get("signal_type", "other")),
        signals=ProspectSignals.model_validate(signals_data),
        status=row.get("status", "pending_review"),
        created_at=row.get("created_at"),
        reviewed_at=row.get("reviewed_at"),
        reviewed_by=row.get("reviewed_by"),
        rejection_reason=row.get("rejection_reason"),
        sent_at=row.get("sent_at"),
        raw=row.get("raw") or {},
    )
