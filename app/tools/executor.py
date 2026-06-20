from __future__ import annotations

import logging
import time
from typing import Any

from app.tools.audit import ToolAuditLogger
from app.tools.perplexity import run_with_retry
from app.tools.policy import AgentRole, ToolPolicy
from app.tools.registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Policy → audit → timeout/retry → handler. Agents call this, not handlers directly."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        audit: ToolAuditLogger,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.audit = audit

    def run(self, actor: AgentRole, tool_name: str, **kwargs: Any) -> Any:
        self.policy.check(actor, tool_name)
        tool = self.registry.get(tool_name)
        record = self.audit.start(actor.value, tool_name, **kwargs)

        started = time.perf_counter()
        try:
            result = run_with_retry(
                tool.run,
                max_retries=tool.max_retries,
                **kwargs,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            result_count = len(result) if isinstance(result, list) else 1
            self.audit.finish(
                record,
                status="success",
                latency_ms=latency_ms,
                result_count=result_count,
            )
            logger.info(
                "tool_call_ok tool=%s actor=%s latency_ms=%s results=%s",
                tool_name,
                actor.value,
                latency_ms,
                result_count,
            )
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.audit.finish(
                record,
                status="error",
                latency_ms=latency_ms,
                error=str(exc)[:500],
            )
            logger.error("tool_call_fail tool=%s actor=%s error=%s", tool_name, actor.value, exc)
            raise
