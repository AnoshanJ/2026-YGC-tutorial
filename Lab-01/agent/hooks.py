"""Strands hooks for the customer-support agent.

`CustomerIdBindingHook` — the harness-side identity binding.

OWASP API #1 is "Broken Object Level Authorization." The naive fix in the rest
of this lab is to (a) inject `[verified customer_id=X]` into the message and
(b) check ownership server-side on every tool. That's defense in depth, but
the LLM is still the principal — a prompt injection can make the model pass
the wrong `customer_id` to any tool whose docstring it can reach. Server-side
ownership checks like `_load_owned_order` catch order-scoped abuse, but
customer-scoped reads (e.g. `get_refund_history(customer_id)`) have nothing
to check against once the LLM picks the ID.

This hook moves the principal one layer up. The harness — not the model —
sets `customer_id` on every tool call's input *just before* it ships to the
MCP server. Whatever the LLM tried to pass is overwritten. The model can
read the customer's name from its memory / conversation context (we surface
that for tone), but it has no syntactic handle on the identifier that
actually scopes data access.

The pattern is exactly the same as setting an Authorization header in a
backend request: the LLM proposes the call shape, the harness signs it.
"""

import json
from dataclasses import dataclass

from strands.hooks import HookRegistry
from strands.hooks.events import BeforeToolCallEvent

# Tools whose input dicts get `customer_id` injected. Anything NOT in this set
# is left alone — e.g., `search_policy_kb` (no customer scoping) or the
# AgentSkills `skills` loader. Keep the list explicit so it's clear which
# tools depend on identity binding.
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
    """Forces the trusted customer_id onto every customer-scoped tool call.

    Constructed with the customer_id authenticated at session start (in this
    lab, supplied via `python run.py --customer <id>`; in production it
    would come from your session cookie / JWT / OIDC subject claim).

    Strands fires `BeforeToolCallEvent` synchronously before each tool runs.
    We mutate `event.tool_use["input"]["customer_id"]` in place — the LLM's
    proposed value is silently replaced. If the LLM hallucinated a different
    customer_id, the audit ledger entry that lands will still belong to the
    real customer.
    """

    customer_id: str

    def register_hooks(self, registry: HookRegistry, **_: object) -> None:
        registry.add_callback(BeforeToolCallEvent, self._bind_customer_id)

    def _bind_customer_id(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use
        name = tool_use.get("name")
        if name not in CUSTOMER_SCOPED_TOOLS:
            return
        # `input` is a dict on tool_use; mutate in place so the downstream
        # tool dispatcher sees the trusted value.
        tool_use["input"]["customer_id"] = self.customer_id


@dataclass
class RefundCapHook:
    """Enforces the agent's per-call refund cap at the harness layer.

    The cap is an attribute of the agent's scoped identity (see
    `agent-profile.yaml` → `refund_cap_usd`), not a fact about the backend.
    Enforcing here — *before* the tool dispatches — means even a prompt-
    injected agent that tries to call `issue_refund(amount_usd=1_000_000)`
    will see a synthetic 403, NOT the refund actually clear. The MCP
    server has a defense-in-depth check too, but in production each
    backend would serve many agents and shouldn't have to know each one's
    cap; the harness is the right principal authority.

    The cap stays visible in the system prompt as an efficiency hint, so
    the agent can route to `escalate_to_human` directly for amounts over
    the cap instead of wasting a tool call. The hook is the safety net for
    when the agent doesn't follow that hint (prompt injection, hallucination).
    """

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
        event.cancel_tool = json.dumps({
            "error": "policy_violation",
            "code": 403,
            "detail": (
                f"refund of ${amount:.2f} exceeds agent cap of "
                f"${self.refund_cap_usd:.2f}"
            ),
            "remediation": "escalate_to_human",
        })
