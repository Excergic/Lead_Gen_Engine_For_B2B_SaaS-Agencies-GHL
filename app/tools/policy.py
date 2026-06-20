from __future__ import annotations

from enum import StrEnum


class AgentRole(StrEnum):
    OPERATOR = "operator"
    DISCOVER_AGENT = "discover_agent"
    ENRICH_AGENT = "enrich_agent"
    OUTREACH_AGENT = "outreach_agent"
    CONVERT_AGENT = "convert_agent"


TOOL_CAPABILITIES: dict[str, set[AgentRole]] = {
    "perplexity_web_search": {AgentRole.OPERATOR, AgentRole.DISCOVER_AGENT},
    "enrich_profile": {AgentRole.OPERATOR, AgentRole.ENRICH_AGENT, AgentRole.DISCOVER_AGENT},
    "enrich_email": {AgentRole.OPERATOR, AgentRole.ENRICH_AGENT, AgentRole.DISCOVER_AGENT},
    "score_signal": {AgentRole.OPERATOR, AgentRole.DISCOVER_AGENT, AgentRole.ENRICH_AGENT, AgentRole.OUTREACH_AGENT},
    "research_prospect_signals": {AgentRole.OPERATOR, AgentRole.OUTREACH_AGENT},
    "write_outreach": {AgentRole.OPERATOR, AgentRole.OUTREACH_AGENT},
    "send_email": {AgentRole.OPERATOR},  # HITL: operator only, after explicit approve
    "book_meeting": {AgentRole.OPERATOR, AgentRole.CONVERT_AGENT},
}


class ToolAccessDenied(PermissionError):
    def __init__(self, actor: AgentRole, tool_name: str) -> None:
        super().__init__(f"Role '{actor.value}' is not permitted to call tool '{tool_name}'")


class ToolPolicy:
    """RBAC gate — policy before mechanism (security-engineering)."""

    def __init__(self, capabilities: dict[str, set[AgentRole]] | None = None) -> None:
        self._capabilities = capabilities or TOOL_CAPABILITIES

    def check(self, actor: AgentRole, tool_name: str) -> None:
        allowed = self._capabilities.get(tool_name)
        if not allowed or actor not in allowed:
            raise ToolAccessDenied(actor, tool_name)

    def allowed_tools(self, actor: AgentRole) -> list[str]:
        return sorted(
            name for name, roles in self._capabilities.items() if actor in roles
        )
