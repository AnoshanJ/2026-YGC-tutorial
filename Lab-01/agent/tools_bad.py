"""Intentionally BAD-designed tools — same capabilities as tools.py, but
shaped to make the agent fumble. The Section 2 contrast.

Specific failure modes (each is a real anti-pattern in production systems):
- Single-string args (no schema) → agent invents serialization
- Vague names (`info`, `do_refund`) → agent picks wrong tool
- Conflated operations (`info` covers customer + order lookup) → ambiguity
- Useless returns (`"see policy docs"`) → agent can't ground decisions
- No structured errors → failures look like success strings

These tools are still FUNCTIONAL — they extract what they can from the
agent's string args. That's the point: the agent doesn't get stuck, it
gets through with a messy reply. "Bad design" not "broken implementation".

Switching `tools.py` ↔ `tools_bad.py` is the Section 2 hands-on: edit
`agent-profile.yaml`, flip `tool_set: bad` → `good`, re-run, watch the trace
clean up. Same model, same prompt — different tool layer.
"""
import re

from agents import function_tool, RunContextWrapper

from agent.tools import Deps  # share the same context shape


# Patterns the agent commonly uses when forced to serialize into a single string
_CUST_RE = re.compile(r"cust_[a-zA-Z0-9_-]+")
_ORDER_RE = re.compile(r"\b\d{3,}\b")          # order ids are 3+ digits
_AMOUNT_RE = re.compile(r"\$?(\d+(?:\.\d+)?)") # dollar amount, optional $


@function_tool
def info(ctx: RunContextWrapper[Deps], args: str) -> str:
    """Get information about stuff. Pass what you want as a string."""
    # No schema: agent has to invent a format. The tool gamely tries to find
    # a customer id or order id anywhere in the string. Works often enough
    # that the agent thinks it's fine — but the result type is also vague
    # (a stringified dict instead of structured JSON), which compounds errors.
    a = args.strip()
    cust = _CUST_RE.search(a)
    if cust:
        c = ctx.context.client.get_customer(cust.group())
        return str(c.model_dump()) if c else "not found"
    order = _ORDER_RE.search(a)
    if order:
        o = ctx.context.client.get_order(order.group())
        return str(o.model_dump()) if o else "not found"
    return "couldn't figure out what you wanted"


@function_tool
def do_refund(ctx: RunContextWrapper[Deps], args: str) -> str:
    """Does refunds. Pass the details as a string."""
    # Agent has to encode (order_id, amount, reason) into one string. We
    # accept the comma-separated format AND the natural `field=value` style.
    # No structured error means "nope: ..." looks like a string to interpret.
    a = args.strip()
    order_id: str | None = None
    amount: float | None = None

    parts = [p.strip() for p in a.split(",")]
    if len(parts) >= 2:
        try:
            order_id = parts[0].split("=", 1)[-1].strip()
            amount = float(parts[1].split("=", 1)[-1].strip().lstrip("$"))
        except (ValueError, IndexError):
            order_id = None
            amount = None

    if order_id is None or amount is None:
        order_match = _ORDER_RE.search(a)
        amount_match = _AMOUNT_RE.search(a)
        if order_match and amount_match:
            order_id = order_match.group()
            amount = float(amount_match.group(1))

    if order_id is None or amount is None:
        return "couldn't parse"

    o = ctx.context.client.get_order(order_id)
    if o is None:
        return "order not found"

    allowed, why = ctx.context.identity.can_refund(amount)
    if not allowed:
        return f"nope: {why}"

    ref = ctx.context.client.issue_refund(
        order_id, o.customer_id, amount, "refund", ctx.context.identity.agent_id
    )
    return f"ok {ref}"


@function_tool
def policy(ctx: RunContextWrapper[Deps], q: str) -> str:
    """Look up policy."""
    # Vague return — no actual rule, no structure. Agent has to guess.
    # MCP isn't even wired here (this is the bad-design world).
    return "see policy docs"


@function_tool
def order_action(ctx: RunContextWrapper[Deps], args: str) -> str:
    """Do order things — cancel, update address, etc. Pass as string."""
    # Conflates multiple operations. Doesn't actually do anything useful
    # without further prodding — the agent has to encode the op in a way
    # that's never documented.
    return "specify the operation"


@function_tool
def escalate(ctx: RunContextWrapper[Deps], why: str) -> str:
    """Escalate."""
    # No priority, no customer link, no audit context preserved.
    ctx.context.client.open_ticket(why, "normal", ctx.context.identity.agent_id)
    return "escalated"


# ---------------------------------------------------------------------------
# Bad-design tool list — same contract as ALL_TOOLS in tools.py
# ---------------------------------------------------------------------------

ALL_TOOLS = [info, do_refund, policy, order_action, escalate]
