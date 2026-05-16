"""MCP server: the customer-support backend, redesigned for agents (v2).

The "good" side of the §2a contrast. Same backend, same data, same
capabilities as `customer_support_v1` — but every tool was rewritten with
the agent in mind: action-verb names, typed parameters, structured returns,
explicit error contracts.

State flows in via:

  - Env vars at launch (refund cap, agent identity)
  - Explicit tool parameters per call (customer_id, order_id, etc.)
  - The mock backend (CustomerSupportClient reads/writes mocks/data/*.json)

There's no session closure here (we're a separate Python interpreter from
the agent). That's exactly how a production team's MCP server works:
they don't know or care about your agent's session — you pass everything
they need on each call.

Every order tool takes `customer_id` as its first parameter and verifies
that the order belongs to that customer before reading or writing. The
agent gets the verified customer_id from the message prefix; the tool
enforces ownership server-side so a wrong (or injected) `order_id` can't
leak or mutate someone else's order. Returns
`{"error": "ownership_mismatch", "code": 403, ...}` on mismatch.

Run via stdio (Strands' MCPClient launches it as a subprocess from
agent/core.py).
"""

import logging

from mcp.server.fastmcp import FastMCP

from agent.identity import AgentIdentity
from agent.profile import load_profile
from mocks.client import CustomerSupportClient

# Silence the MCP framework's INFO logs (otherwise every list_tools call
# leaks into the on-stage trace).
logging.basicConfig(level=logging.WARNING)
for noisy in ("mcp", "mcp.server", "mcp.server.lowlevel", "FastMCP"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

mcp = FastMCP("customer-support-v2")

# State at launch. The server reads the same agent-profile.yaml as the
# agent — single source of truth for agent_id / name / refund_cap. In a
# real deployment this would come from the team's own config service or
# service-principal credentials.
_client = CustomerSupportClient()
_profile = load_profile()
_identity = AgentIdentity(
    agent_id=_profile.agent_id,
    name=_profile.name,
    refund_cap_usd=_profile.refund_cap_usd,
)


def _load_owned_order(customer_id: str, order_id: str):
    """Fetch an order and verify it belongs to `customer_id`.

    Returns (order, None) on success, or (None, error_dict) if the order
    doesn't exist or belongs to someone else. The ownership check is
    enforced here so callers can't forget it — broken object-level
    authorization (OWASP API #1) is one tool signature away if you make
    `customer_id` optional or trust the agent to check.
    """
    o = _client.get_order(order_id)
    if o is None:
        return None, {"error": "order_not_found", "order_id": order_id}
    if o.customer_id != customer_id:
        return None, {
            "error": "ownership_mismatch",
            "code": 403,
            "order_id": order_id,
            "detail": "this order does not belong to the verified customer",
            "remediation": "do_not_act",
        }
    return o, None


# ----- Read tools -----------------------------------------------------


@mcp.tool()
def lookup_customer(customer_id: str) -> dict:
    """Look up a customer's profile by their customer_id.

    Call this first when you need to verify who you're speaking with,
    or when you need their tier, verification status, or email.
    Returns the customer record, or {"error": "customer_not_found"}.
    """
    c = _client.get_customer(customer_id)
    if c is None:
        return {"error": "customer_not_found", "customer_id": customer_id}
    return c.model_dump()


@mcp.tool()
def get_order(customer_id: str, order_id: str) -> dict:
    """Fetch a single order by order_id, scoped to the verified customer.

    `customer_id` is the verified ID from the message prefix — pass it
    directly. The server checks the order belongs to that customer; a
    mismatch returns {"error": "ownership_mismatch", "code": 403, ...}
    and you should NOT retry with a different customer_id.

    On success returns: status, items, total_usd, shipping_address,
    delivery_days_late, damaged flag.
    """
    o, err = _load_owned_order(customer_id, order_id)
    if err is not None:
        return err
    return o.model_dump()


@mcp.tool()
def get_customer_orders(customer_id: str, limit: int = 5) -> dict:
    """List a customer's recent orders, most recent first, capped at `limit`.

    Use when the customer doesn't give an order number, or when you need
    their history to make a judgment call (e.g., repeat damaged delivery
    signals a warehouse problem, not just a customer one).
    """
    items = _client.get_customer_orders(customer_id)
    items.sort(key=lambda o: o.placed, reverse=True)
    return {"orders": [o.model_dump() for o in items[:limit]]}


@mcp.tool()
def get_open_tickets(customer_id: str) -> dict:
    """Return tickets opened for this customer that are still status=open.

    Call this whenever episodic memory points at a ticket (e.g. "verify
    TICKET-1001 progress before replying") OR before escalating something
    that may already be tracked. Each result includes ticket_id, priority,
    reason, opened_at — enough to decide whether the original issue is
    still hanging vs. resolved.

    Empty list = no open tickets on file. If a ticket your memory referenced
    is NOT in here, treat memory as stale and update it via `remember`.
    """
    tickets = _client.get_open_tickets(customer_id)
    return {"tickets": tickets, "count": len(tickets)}


@mcp.tool()
def get_refund_history(customer_id: str) -> dict:
    """Return every refund previously issued to this customer.

    Call this BEFORE any new refund — episodic memory may claim "$X already
    refunded on order Y", but this ledger is the source of truth. Each result
    includes ref, order_id, amount_usd, reason, issued_at. Use it to:
      - avoid double-refunding an order (anti-split policy)
      - reconcile what episodic memory says against the audit trail
      - cite a specific past `ref` in your reply when relevant
    """
    refunds = _client.get_refund_history(customer_id)
    return {"refunds": refunds, "count": len(refunds)}


# ----- Write tools ---------------------------------------------------


@mcp.tool()
def update_shipping_address(customer_id: str, order_id: str, new_address: str) -> dict:
    """Update the shipping address on an order that has NOT yet shipped.

    Scoped to the verified customer — pass `customer_id` from the
    message prefix. Ownership is enforced server-side; a mismatch
    returns {"error": "ownership_mismatch", "code": 403, ...}.

    Returns {"error": "order_already_shipped", "remediation": "redirect_to_carrier"}
    if status is other than 'placed' or 'preparing'. On success:
    {"ok": True, "ref": "<audit_ref>"}.
    """
    o, err = _load_owned_order(customer_id, order_id)
    if err is not None:
        return err
    if o.status not in ("placed", "preparing"):
        return {
            "error": "order_already_shipped",
            "order_id": order_id,
            "current_status": o.status,
            "remediation": "redirect_to_carrier",
        }
    ref = _client.update_shipping_address(order_id, new_address, _identity.agent_id)
    return {"ok": True, "ref": ref}


@mcp.tool()
def cancel_order(customer_id: str, order_id: str, reason: str) -> dict:
    """Cancel an order that has NOT yet shipped.

    Scoped to the verified customer. `reason` is logged to the audit
    ledger. Same ownership and already-shipped error contracts as
    `update_shipping_address`.
    """
    o, err = _load_owned_order(customer_id, order_id)
    if err is not None:
        return err
    if o.status not in ("placed", "preparing"):
        return {
            "error": "order_already_shipped",
            "order_id": order_id,
            "current_status": o.status,
            "remediation": "contact_customer_for_return",
        }
    ref = _client.cancel_order(order_id, reason, _identity.agent_id)
    return {"ok": True, "ref": ref}


@mcp.tool()
def issue_refund(
    customer_id: str, order_id: str, amount_usd: float, reason: str
) -> dict:
    """Issue a refund on an order, scoped to the verified customer.

    Pass `customer_id` from the message prefix. Ownership is enforced
    server-side — a mismatch returns
    {"error": "ownership_mismatch", "code": 403, ...} and you should NOT
    retry with a different customer_id.

    Enforces this server's refund cap (set at launch via REFUND_CAP_USD).
    If amount_usd exceeds the cap, returns:
      {"error": "policy_violation", "code": 403, "detail": "...",
       "remediation": "escalate_to_human"}

    The remediation is the contract: a 403 is PERMANENT — escalate, don't
    retry with a smaller amount. Splitting a single refund into multiple
    smaller calls is explicitly prohibited by the `refund_authority`
    policy and will be flagged in audit.

    Use specific `reason` values:
      - "shipping_delay_credit" for delay compensation
      - "damaged_item_full_refund" / "damaged_item_partial" for damage
      - "return_within_window" for normal returns
    """
    o, err = _load_owned_order(customer_id, order_id)
    if err is not None:
        return err

    allowed, why = _identity.can_refund(amount_usd)
    if not allowed:
        return {
            "error": "policy_violation",
            "code": 403,
            "detail": why,
            "remediation": "escalate_to_human",
        }

    ref = _client.issue_refund(
        order_id, o.customer_id, amount_usd, reason, _identity.agent_id
    )
    return {"ok": True, "ref": ref, "amount_usd": amount_usd}


# ----- Escalation --------------------------------------------------


@mcp.tool()
def escalate_to_human(
    reason: str,
    priority: str = "normal",
    customer_id: str | None = None,
) -> dict:
    """Open a ticket for a human agent to handle.

    Use when:
      - the action exceeds your authority (e.g., refund > cap)
      - the situation is ambiguous and needs human judgment
      - the customer explicitly asks for a human
      - input guardrails have flagged the message as adversarial

    `priority` must be one of: 'low', 'normal', 'high', 'urgent'.
    `reason` should include FULL context — the human picking this up
    should not need to re-investigate.
    """
    if priority not in {"low", "normal", "high", "urgent"}:
        return {
            "error": "invalid_priority",
            "allowed": ["low", "normal", "high", "urgent"],
        }
    ticket_id = _client.open_ticket(reason, priority, _identity.agent_id, customer_id)
    return {"ok": True, "ticket_id": ticket_id, "priority": priority}


if __name__ == "__main__":
    mcp.run(transport="stdio")
