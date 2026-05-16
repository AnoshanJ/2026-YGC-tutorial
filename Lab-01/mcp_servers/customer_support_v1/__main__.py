"""MCP server: the customer-support backend — original first cut (v1).

The "bad" side of the §2a contrast. Same backend, same data as
`customer_support_v2` — but the tools showcase five common anti-patterns
backend teams fall into when they aren't designing for an LLM consumer.

Each anti-pattern is its own section below, with a `# === Anti-pattern
N: ... ===` header and a 2-sentence comment explaining why the shape
hurts the agent. README §2a has a sample query per pattern so you can
demo the fumble live.
"""

import logging
import re

from mcp.server.fastmcp import FastMCP

from agent.identity import AgentIdentity
from agent.profile import load_profile
from mocks.client import CustomerSupportClient

logging.basicConfig(level=logging.WARNING)
for noisy in ("mcp", "mcp.server", "mcp.server.lowlevel", "FastMCP"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

mcp = FastMCP("customer-support-v1")

# Read identity / refund cap from the same agent-profile.yaml as the
# agent itself — single source of truth, no env-var injection needed.
_client = CustomerSupportClient()
_profile = load_profile()
_identity = AgentIdentity(
    agent_id=_profile.agent_id,
    name=_profile.name,
    refund_cap_usd=_profile.refund_cap_usd,
)


# === Anti-pattern 1: vague description =====================================
# The docstring says nothing about WHEN to call this, what corpus it
# searches, or what shape it returns. The agent has no signal that this
# tool exists for in-house CS operational notes, so it either skips the
# tool entirely or calls it for the wrong kind of question.

# The CS team's in-house operational notes — short FAQ snippets they
# maintain for their own reference. Realistic shape for an internal
# knowledge base nobody fully documented.
_CS_NOTES = [
    "Tier rules: customers reach 'business' tier after 12 orders in 12 months; 'premium' after 30.",
    "Verification: the verified badge appears once a customer completes email verification at signup.",
    "Carrier handoff happens at the 'preparing' → 'in_transit' status transition; before that the order is still in our warehouse.",
    "Address changes after carrier handoff route through the carrier's portal, not through our system.",
    "Refund processing: refunds appear in the customer's bank 5–7 business days after the audit ledger entry is written.",
    "Ticket priorities: 'urgent' pages oncall within 15 min; 'high' within 4 hours; 'normal' next business day.",
]


@mcp.tool()
def search(query: str) -> str:
    """Search."""
    words = [w.lower() for w in query.split() if len(w) > 3]
    hits = [n for n in _CS_NOTES if any(w in n.lower() for w in words)]
    return "\n".join(hits) if hits else "no results"


# === Anti-pattern 2: vague input schema (single-string blob) ==============
# Forcing the agent to serialize multiple values into one string makes it
# invent a format (JSON? key=val? prose?). Half the calls misparse, the
# rest waste tokens guessing the right shape, and any second value the
# agent stuffs in (e.g. an order id alongside a customer id) is silently
# dropped by the regex.

_CUST_RE = re.compile(r"cust_[a-zA-Z0-9_-]+")
_ORDER_RE = re.compile(r"\b\d{3,}\b")


@mcp.tool()
def info(args: str) -> str:
    """Get info. Pass what you want as a string."""
    a = args.strip()
    cust = _CUST_RE.search(a)
    if cust:
        c = _client.get_customer(cust.group())
        return str(c.model_dump()) if c else "not found"
    order = _ORDER_RE.search(a)
    if order:
        o = _client.get_order(order.group())
        return str(o.model_dump()) if o else "not found"
    return "couldn't figure out what you wanted"


# === Anti-pattern 3: output noise (too much detail) =======================
# The backend returns its raw `SELECT *` record — DB ids, timestamps,
# shard keys, audit pointers, duplicated legacy fields — and the tool
# passes it straight through. The agent has to scan past 15+ noise fields
# to find the one it actually needs, and often picks a similar-looking
# wrong one (e.g. `_legacy_email_field` instead of `email`).


@mcp.tool()
def get_customer_full(customer_id: str) -> dict:
    """Returns the customer record."""
    record = _client.get_customer_record(customer_id)
    if record is None:
        return {"error": "customer_not_found"}
    return record


# === Anti-pattern 4: tools too atomic =====================================
# Splitting one logical lookup into four micro-tools forces the agent to
# round-trip four times for what should be one call. Each round-trip
# costs a turn, tokens, and a chance for the agent to drift mid-task.


@mcp.tool()
def get_customer_name(customer_id: str) -> str:
    """Get the name."""
    c = _client.get_customer(customer_id)
    return c.name if c else ""


@mcp.tool()
def get_customer_email(customer_id: str) -> str:
    """Get the email."""
    c = _client.get_customer(customer_id)
    return c.email if c else ""


@mcp.tool()
def get_customer_tier(customer_id: str) -> str:
    """Get the tier."""
    c = _client.get_customer(customer_id)
    return c.tier if c else ""


@mcp.tool()
def get_customer_verified(customer_id: str) -> bool:
    """Is verified."""
    c = _client.get_customer(customer_id)
    return bool(c.verified) if c else False


# === Anti-pattern 5: tools compound multiple actions ======================
# Conflating cancel, refund, and address-update under one tool — with a
# verb-string `action` and a grab-bag of optional params, only some of
# which apply per action — forces the agent to guess the exact literal
# AND know which params pair with which verb. Errors degrade to
# "unknown action", and the audit log can't distinguish operations.


@mcp.tool()
def order_action(
    order_id: str,
    action: str,
    refund_amount_usd: float | None = None,
    cancel_reason: str | None = None,
    new_address: str | None = None,
) -> dict:
    """Do order things — cancel, refund, update_address."""
    o = _client.get_order(order_id)
    if o is None:
        return {"error": "order not found"}
    if action == "cancel":
        ref = _client.cancel_order(
            order_id, cancel_reason or "no reason", _identity.agent_id
        )
        return {"ok": True, "ref": ref}
    if action == "refund":
        if refund_amount_usd is None:
            return {"error": "missing refund_amount_usd"}
        allowed, why = _identity.can_refund(refund_amount_usd)
        if not allowed:
            return {"error": f"nope: {why}"}
        ref = _client.issue_refund(
            order_id, o.customer_id, refund_amount_usd, "refund", _identity.agent_id
        )
        return {"ok": True, "ref": ref}
    if action == "update_address":
        if new_address is None:
            return {"error": "missing new_address"}
        ref = _client.update_shipping_address(order_id, new_address, _identity.agent_id)
        return {"ok": True, "ref": ref}
    return {"error": f"unknown action: {action}"}


# Utility — minimally usable, not part of the §2a anti-pattern walkthrough.
# Kept so the agent has SOME escalation path in v1 mode.
@mcp.tool()
def escalate(why: str) -> str:
    """Escalate."""
    _client.open_ticket(why, "normal", _identity.agent_id, None)
    return "escalated"


if __name__ == "__main__":
    mcp.run(transport="stdio")
