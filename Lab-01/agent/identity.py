"""Scoped agent identity.

The agent has its OWN identity — not the user's. Its permissions, refund cap,
and audit trail are all tied to this identity. In production, the agent
identity would be issued by your IDP (Asgardeo, Okta, etc.) as a scoped
service principal. Here we instantiate it directly for the demo.

The §6 closing demo points at this: agent-level guardrails (refund cap,
scoped tools) work; for governance at scale you need a control plane.
"""
from dataclasses import dataclass, field


@dataclass
class AgentIdentity:
    agent_id: str
    name: str
    refund_cap_usd: float = 200.0
    allowed_tools: set[str] = field(default_factory=set)
    initiating_user_id: str | None = None

    def can_refund(self, amount_usd: float) -> tuple[bool, str | None]:
        """Returns (allowed, reason_if_not). Reason is for the structured error
        returned by issue_refund. Don't raise — the agent reads the reason."""
        if amount_usd <= 0:
            return False, f"refund amount must be positive, got ${amount_usd:.2f}"
        if amount_usd > self.refund_cap_usd:
            return False, (
                f"refund of ${amount_usd:.2f} exceeds agent cap of "
                f"${self.refund_cap_usd:.2f}"
            )
        return True, None

    def has_tool(self, tool_name: str) -> bool:
        """Empty allowed_tools means all tools allowed (default agent profile)."""
        return not self.allowed_tools or tool_name in self.allowed_tools


DEFAULT_AGENT = AgentIdentity(
    agent_id="cs-agent-v1",
    name="Customer Support Agent v1",
    refund_cap_usd=200.0,
    allowed_tools={
        "lookup_customer",
        "get_order",
        "get_customer_orders",
        "search_policy_kb",
        "update_shipping_address",
        "cancel_order",
        "issue_refund",
        "escalate_to_human",
    },
)
