from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

MAX_QUERY_AUDIT_LEN = 500


def _hash_input(kwargs: dict[str, Any]) -> str:
    safe = {k: v for k, v in kwargs.items() if k not in {"api_key", "password", "token"}}
    payload = json.dumps(safe, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class ToolAuditRecord:
    def __init__(
        self,
        *,
        tool_call_id: str,
        actor: str,
        tool_name: str,
        input_hash: str,
        input_preview: str,
    ) -> None:
        self.tool_call_id = tool_call_id
        self.actor = actor
        self.tool_name = tool_name
        self.input_hash = input_hash
        self.input_preview = input_preview
        self.started_at = datetime.now(UTC)
        self.completed_at: datetime | None = None
        self.status = "running"
        self.latency_ms: int | None = None
        self.error: str | None = None
        self.result_count: int | None = None

    def complete(self, *, status: str, latency_ms: int, result_count: int = 0, error: str | None = None) -> dict[str, Any]:
        self.completed_at = datetime.now(UTC)
        self.status = status
        self.latency_ms = latency_ms
        self.result_count = result_count
        self.error = error
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "actor": self.actor,
            "tool_name": self.tool_name,
            "input_hash": self.input_hash,
            "input_preview": self.input_preview,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "result_count": self.result_count,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ToolAuditLogger:
    """Append-only audit trail — Supabase optional, JSONL always."""

    def __init__(self, jsonl_path: Path | None = None, db: Any | None = None) -> None:
        self._jsonl_path = jsonl_path
        self._db = db
        if jsonl_path:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def start(self, actor: str, tool_name: str, **kwargs: Any) -> ToolAuditRecord:
        preview = str(kwargs.get("query", kwargs))[:MAX_QUERY_AUDIT_LEN]
        record = ToolAuditRecord(
            tool_call_id=str(uuid4()),
            actor=actor,
            tool_name=tool_name,
            input_hash=_hash_input(kwargs),
            input_preview=preview,
        )
        logger.info("tool_call_start actor=%s tool=%s id=%s", actor, tool_name, record.tool_call_id)
        return record

    def finish(self, record: ToolAuditRecord, **kwargs: Any) -> None:
        row = record.complete(**kwargs)
        self._append_jsonl(row)
        self._append_db(row)

    def _append_jsonl(self, row: dict[str, Any]) -> None:
        if not self._jsonl_path:
            return
        with self._jsonl_path.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def _append_db(self, row: dict[str, Any]) -> None:
        if not self._db:
            return
        try:
            self._db.table("tool_audit_log").insert(row).execute()
        except Exception as exc:
            logger.warning("audit_db_write_failed: %s", exc)
