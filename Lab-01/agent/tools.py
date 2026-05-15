"""Customer-support agent tools — the well-designed set.

Each tool follows agent-first principles:
- Action-verb name (`lookup_customer`, not `info`)
- Typed parameters (no string-blob args)
- Structured return values (dicts with named fields)
- Structured errors (dicts with `error` key) — never raised exceptions
- Docstring that tells the agent WHEN to call and WHAT to expect

This file is the §2 contrast to `tools_bad.py` — same capabilities, very
different ergonomics. Same model, swap which tool list goes into Agent(...)
and the agent's behavior changes dramatically.

Tools don't touch mock data directly — they go through `CustomerSupportClient`.
Swap that class for a real API client to go from demo to production without
touching the tool code. The `search_policy_kb` tool is NOT here — it lives
in `mcp_server/server.py` (MCP boundary between agent team and policy team).
"""
from dataclasses import dataclass

from agents import function_tool, RunContextWrapper

from agent import memory
from agent.identity import AgentIdentity
from agent.skills import list_skills, load_skill_by_name
from mocks.client import CustomerSupportClient


@dataclass
class Deps:
    """Per-run context. Available to every tool via RunContextWrapper[Deps].

    `identity` — the agent's scoped identity (refund cap, agent_id for audit).
    `client`   — the backend client. In the lab it wraps mocks; in production
                 you'd inject a real OrderService / CustomerService.
    `current_customer_id` — the verified customer for this session (from
                 the authenticated session, surfaced via the message prefix).
                 Memory tools use this; other tools fall back to the agent
                 reading it out of the prefix.
    """

    identity: AgentIdentity
    client: CustomerSupportClient
    current_customer_id: str


# ---------------------------------------------------------------------------
# Read tools (no skills required, no MCP — these are the agent team's own systems)
# ---------------------------------------------------------------------------


@function_tool
def lookup_customer(ctx: RunContextWrapper[Deps], customer_id: str) -> dict:
    """Look up a customer's profile by their customer_id.

    Call this first when you need to verify who you're speaking with, or
    when you need their tier, verification status, or email.
    Returns the customer record, or {"error": "customer_not_found"} if missing.
    """
    c = ctx.context.client.get_customer(customer_id)
    if c is None:
        return {"error": "customer_not_found", "customer_id": customer_id}
    return c.model_dump()


@function_tool
def get_order(ctx: RunContextWrapper[Deps], order_id: str) -> dict:
    """Fetch a single order by order_id.

    Returns: status, items, total_usd, shipping_address, delivery_days_late,
    damaged flag. Use this when the customer references a specific order
    by number. Returns {"error": "order_not_found"} if missing.
    """
    o = ctx.context.client.get_order(order_id)
    if o is None:
        return {"error": "order_not_found", "order_id": order_id}
    return o.model_dump()


@function_tool
def get_customer_orders(
    ctx: RunContextWrapper[Deps],
    customer_id: str,
    limit: int = 5,
) -> dict:
    """List a customer's recent orders, most recent first, capped at `limit`.

    Use when the customer doesn't give an order number, or when you need
    their history to make a judgment call (e.g., repeat damaged delivery
    signals a warehouse problem, not just a customer one).
    """
    items = ctx.context.client.get_customer_orders(customer_id)
    items.sort(key=lambda o: o.placed, reverse=True)
    return {"orders": [o.model_dump() for o in items[:limit]]}


# ---------------------------------------------------------------------------
# Write tools (each one paired with a skill that encodes the procedure)
# ---------------------------------------------------------------------------


@function_tool
def update_shipping_address(
    ctx: RunContextWrapper[Deps],
    order_id: str,
    new_address: str,
) -> dict:
    """Update the shipping address on an order that has NOT yet shipped.

    Returns {"error": "order_already_shipped", "remediation": "redirect_to_carrier"}
    if the order has status other than 'placed' or 'preparing' — once a package
    is with the carrier, the customer must redirect via the carrier directly.
    On success: {"ok": True, "ref": "<audit_ref>"}.
    """
    client = ctx.context.client
    o = client.get_order(order_id)
    if o is None:
        return {"error": "order_not_found", "order_id": order_id}
    if o.status not in ("placed", "preparing"):
        return {
            "error": "order_already_shipped",
            "order_id": order_id,
            "current_status": o.status,
            "remediation": "redirect_to_carrier",
        }
    ref = client.update_shipping_address(
        order_id, new_address, ctx.context.identity.agent_id
    )
    return {"ok": True, "ref": ref}


@function_tool
def cancel_order(
    ctx: RunContextWrapper[Deps],
    order_id: str,
    reason: str,
) -> dict:
    """Cancel an order that has NOT yet shipped.

    `reason` is logged to the audit ledger. Returns the same error contract
    as update_shipping_address for already-shipped orders.
    """
    client = ctx.context.client
    o = client.get_order(order_id)
    if o is None:
        return {"error": "order_not_found", "order_id": order_id}
    if o.status not in ("placed", "preparing"):
        return {
            "error": "order_already_shipped",
            "order_id": order_id,
            "current_status": o.status,
            "remediation": "contact_customer_for_return",
        }
    ref = client.cancel_order(order_id, reason, ctx.context.identity.agent_id)
    return {"ok": True, "ref": ref}


@function_tool
def issue_refund(
    ctx: RunContextWrapper[Deps],
    order_id: str,
    amount_usd: float,
    reason: str,
) -> dict:
    """Issue a refund on an order.

    Enforces the agent's scoped refund cap. If `amount_usd` exceeds the cap,
    returns:
      {"error": "policy_violation", "code": 403, "detail": "...",
       "remediation": "escalate_to_human"}

    The remediation field is the contract: on a 403, escalate — do NOT retry
    with a smaller amount. Splitting a single refund into multiple smaller
    calls is explicitly prohibited by the `refund_authority` policy and will
    be flagged as a violation in audit.

    `reason` is logged. Use specific reasons:
      - "shipping_delay_credit" for delay compensation
      - "damaged_item_full_refund" / "damaged_item_partial" for damage
      - "return_within_window" for normal returns
    """
    client = ctx.context.client
    identity = ctx.context.identity

    o = client.get_order(order_id)
    if o is None:
        return {"error": "order_not_found", "order_id": order_id}

    allowed, why = identity.can_refund(amount_usd)
    if not allowed:
        return {
            "error": "policy_violation",
            "code": 403,
            "detail": why,
            "remediation": "escalate_to_human",
        }

    ref = client.issue_refund(
        order_id, o.customer_id, amount_usd, reason, identity.agent_id
    )
    return {"ok": True, "ref": ref, "amount_usd": amount_usd}


# ---------------------------------------------------------------------------
# Episodic memory — write tools only. The memory itself is loaded into the
# system prompt at session start (see agent/core.py).
# ---------------------------------------------------------------------------


@function_tool
def remember(ctx: RunContextWrapper[Deps], note: str) -> dict:
    """Append a note to the current customer's episodic memory.

    Use AFTER resolving a non-trivial interaction. Record only what a
    future agent (or you, next session) would actually want to know:

      - actions taken (refunds issued + amounts, tickets opened + IDs)
      - promises made (replacement shipping, follow-up by date)
      - customer state (frustrated, longtime account, repeat issue)
      - patterns worth tracking (this is their 2nd damaged delivery)

    Don't save trivial details. Don't dump the whole conversation. Think
    of it as a one-paragraph case note — brief, factual, scannable.
    The customer_id is from the verified session — you don't pass it.
    """
    cust_id = ctx.context.current_customer_id
    memory.append(cust_id, note)
    return {"ok": True, "saved_for": cust_id}


@function_tool
def compact_memory(ctx: RunContextWrapper[Deps], new_content: str) -> dict:
    """Rewrite the customer's entire memory file with a compacted version.

    Use ONLY when the existing memory has grown long, rambling, or
    redundant. Write a shorter version that preserves the key facts —
    open tickets, outstanding promises, important patterns. You are
    OVERWRITING; old content is replaced. Be careful.

    Most sessions never need this — `remember()` is the daily tool.
    """
    cust_id = ctx.context.current_customer_id
    memory.write(cust_id, new_content)
    return {"ok": True, "rewrote": cust_id}


# ---------------------------------------------------------------------------
# Skill access (Anthropic-style: catalog in prompt, full procedure on demand)
# ---------------------------------------------------------------------------


@function_tool
def read_skill(ctx: RunContextWrapper[Deps], skill_name: str) -> dict:
    """Read the full procedure for a named skill.

    Your system prompt lists the skills available with a one-line description
    each. When the customer's request matches a skill's description, call this
    tool to load the full procedure — then follow it step by step.

    Args:
        skill_name: the `name` field from the skill catalog (e.g.,
                    'handle_refund', 'verify_customer').

    Returns the skill's `name`, `description`, and `procedure` (the markdown
    body). On miss, returns `{"error": "skill_not_found", "available": [...]}`
    listing what IS available so you can recover.
    """
    skill = load_skill_by_name(skill_name)
    if skill is None:
        return {
            "error": "skill_not_found",
            "skill_name": skill_name,
            "available": [s.name for s in list_skills()],
        }
    return {
        "name": skill.name,
        "description": skill.description,
        "procedure": skill.body,
    }


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


@function_tool
def escalate_to_human(
    ctx: RunContextWrapper[Deps],
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
    - safety / fraud signals are present

    `priority` must be one of: 'low', 'normal', 'high', 'urgent'.
    `reason` should include full context — the human picking up this ticket
    should not need to re-investigate. Include `customer_id` so it's linked.

    Returns: {"ok": True, "ticket_id": "TICKET-NNNN", "priority": "..."}
    """
    if priority not in {"low", "normal", "high", "urgent"}:
        return {
            "error": "invalid_priority",
            "allowed": ["low", "normal", "high", "urgent"],
        }
    ticket_id = ctx.context.client.open_ticket(
        reason, priority, ctx.context.identity.agent_id, customer_id
    )
    return {"ok": True, "ticket_id": ticket_id, "priority": priority}


# ---------------------------------------------------------------------------
# The exported tool list — what the agent harness passes into Agent(tools=...)
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    lookup_customer,
    get_order,
    get_customer_orders,
    update_shipping_address,
    cancel_order,
    issue_refund,
    remember,
    compact_memory,
    read_skill,
    escalate_to_human,
]
