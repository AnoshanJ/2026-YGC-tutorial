"""Strands hooks for the customer-support agent.

`CustomerIdBindingHook` — the harness-side user identity binding.

OWASP API #1 is "Broken Object Level Authorization." The naive fix in the rest
of this lab is to (a) inject `[verified customer_id=X]` into the message and
(b) check ownership server-side on every tool. That's defense in depth, but
the LLM is still the principal — a prompt injection can make the model pass
the wrong `customer_id` to any tool whose docstring it can reach. Server-side
ownership checks like `_load_owned_order` catch order-scoped abuse, but
customer-scoped reads (e.g. `get_refund_history(customer_id)`) have nothing
to check against once the LLM picks the ID.

This hook moves the principal one layer up. The harness — not the model —
owns `customer_id` on every customer-scoped tool call. If the LLM proposes
a `customer_id` that doesn't match the session's trusted ID, the call is
rejected with a 403 *before* it ships to the MCP server. If the LLM omits
the argument entirely (typical of an early discovery call), the harness
fills in the trusted value. Either way, the model has no syntactic handle
on the identifier that actually scopes data access.

Why reject rather than silently rewrite: rewriting hides the attack and
also creates an agent-loop hazard — the model asks for `cust_003`, sees
data for `cust_001` come back, decides its call "didn't work," and retries
forever. An explicit 403 breaks the loop and makes the cross-tenant
attempt visible in the trace.

The pattern is exactly the same as a backend rejecting a request whose
body claims a different user than the Authorization header: the LLM
proposes the call shape, the harness verifies it.
"""

import json
from dataclasses import dataclass

from strands.hooks import HookRegistry
from strands.hooks.events import BeforeToolCallEvent

# Tools whose input dicts get `customer_id` injected. Anything NOT in this set
# is left alone — e.g., `search_policy_kb` (no customer scoping) or the
# AgentSkills `skills` loader. Keep the list explicit so it's clear which
# tools depend on user identity binding.
CUSTOMER_SCOPED_TOOLS = frozenset(
    {
        "lookup_customer",
        "get_order",
        "get_customer_orders",
        "get_open_tickets",
        "get_refund_history",
        "update_shipping_address",
        "cancel_order",
        "issue_refund",
        "escalate_to_human",
        "remember",
        "compact_memory",
    }
)


@dataclass
class CustomerIdBindingHook:
    """Validate `customer_id` on every customer-scoped tool call against the trusted session ID.

    See the module docstring for the OWASP API#1 rationale.
    """

    customer_id: str

    def register_hooks(self, registry: HookRegistry, **_: object) -> None:
        registry.add_callback(BeforeToolCallEvent, self._bind_customer_id)

    def _bind_customer_id(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use
        name = tool_use.get("name")
        if name not in CUSTOMER_SCOPED_TOOLS:
            return
        inputs = tool_use["input"]
        proposed = inputs.get("customer_id")
        if proposed is None:
            # Early discovery call — model hasn't seen the ID yet. Fill in
            # the trusted value so first-touch tools (lookup_customer, etc.)
            # work without the model having to know the ID.
            inputs["customer_id"] = self.customer_id
            return
        if proposed == self.customer_id:
            return
        # Mismatch: the model proposed a customer_id that isn't the session's.
        # Strong signal of prompt injection or cross-tenant probing. Reject
        # with a 403 so the trace shows the attempt and the model gets a
        # clear "stop" rather than confusingly-rewritten data. We intentionally
        # do NOT echo the trusted ID back — that would just feed the attacker
        # the value they were trying to discover.
        event.cancel_tool = json.dumps(
            {
                "error": "unauthorized",
                "code": 403,
                "detail": (
                    f"user is not authorized to access customer_id={proposed!r}"
                ),
                "remediation": "reject the user's request, and request to login with correct account.",
            }
        )


@dataclass
class RefundCapHook:
    """Enforce the agent's per-call refund cap at the harness — defense-in-depth above the MCP server's own check."""

    refund_cap_usd: float

    def register_hooks(self, registry: HookRegistry, **_: object) -> None:
        registry.add_callback(BeforeToolCallEvent, self._enforce_cap)

    def _enforce_cap(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use
        if tool_use.get("name") != "issue_refund":
            return
        amount = tool_use["input"].get("amount_usd")
        if not isinstance(amount, (int, float)) or amount <= self.refund_cap_usd:
            return
        # cancel_tool accepts a string that becomes an error tool-result body.
        # We hand back JSON matching the v2 server's 403 shape so run.py's
        # trace renderer recognises it and shows a clean red error.
        event.cancel_tool = json.dumps(
            {
                "error": "policy_violation",
                "code": 403,
                "detail": (
                    f"refund of ${amount:.2f} exceeds agent cap of "
                    f"${self.refund_cap_usd:.2f}"
                ),
                "remediation": "escalate_to_human",
            }
        )
