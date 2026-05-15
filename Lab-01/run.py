"""Interactive CLI for the customer support agent.

Default: a multi-turn conversation. Type your question, the agent streams its
tool calls and reply, you type the next question, the agent remembers what
came before. Exit with `exit` / `quit` / `:q` / Ctrl-C / Ctrl-D.

Hot-reload: agent-profile.yaml and skills/*.md are watched between turns.
Edit either while the REPL is running and the agent rebuilds on your next
message — you'll see "[dim]config reloaded[/dim]". No restart needed.

In production, the customer_id comes from the authenticated session (login,
OIDC token, JWT). For the demo we use `--customer <id>` (default `cust_001`).

Usage:
  python run.py                                  # REPL as Alice
  python run.py --customer cust_002              # REPL as Bob (for §3)
  python run.py --customer cust_003              # REPL as Carol (for §4b)
  python run.py "single question"                # one-shot, exits after
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from agents import Runner
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.status import Status

from agent.core import build_agent, make_policy_kb_server
from agent.profile import PROFILE_PATH, load_profile
from agent.tools import Deps
from mocks.client import CustomerSupportClient

ROOT = Path(__file__).parent
SKILLS_DIR = ROOT / "skills"

console = Console()

EXIT_TOKENS = {"exit", "quit", "/exit", "/quit", ":q", "bye"}
HISTORY_FILE = str(Path.home() / ".lab1_history")


# ---------------------------------------------------------------------------
# Framing & rendering (unchanged from previous run.py)
# ---------------------------------------------------------------------------


def frame(customer_id: str, message: str) -> str:
    """Prepend the verified session context. The agent's system prompt
    explains this prefix — already authenticated through their session."""
    return f"[verified customer_id={customer_id}] {message}"


def _parse(obj):
    """Best-effort: return obj as a Python object (parses JSON strings)."""
    if isinstance(obj, (dict, list)):
        return obj
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except (ValueError, TypeError):
            return obj
    return obj


def _truncate(text, n: int = 50) -> str:
    s = str(text) if text is not None else ""
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------- args summarizers (per-tool, with generic fallback) -------------


def _summarize_args(name: str, raw) -> str:
    args = _parse(raw)
    if not isinstance(args, dict):
        return _truncate(args, 60)

    # Per-tool — compact, human-readable
    if name == "lookup_customer":
        return args.get("customer_id", "?")
    if name == "get_order":
        return args.get("order_id", "?")
    if name == "get_customer_orders":
        return args.get("customer_id", "?")
    if name == "search_policy_kb":
        return f'"{_truncate(args.get("query", ""), 40)}"'
    if name == "update_shipping_address":
        return f'{args.get("order_id", "?")}, "{_truncate(args.get("new_address", ""), 30)}"'
    if name == "cancel_order":
        return f'{args.get("order_id", "?")}, "{_truncate(args.get("reason", ""), 30)}"'
    if name == "issue_refund":
        return (
            f'{args.get("order_id", "?")}, '
            f'${args.get("amount_usd", "?")}, '
            f'"{_truncate(args.get("reason", ""), 30)}"'
        )
    if name == "escalate_to_human":
        return (
            f'priority={args.get("priority", "normal")}, '
            f'"{_truncate(args.get("reason", ""), 40)}"'
        )
    if name == "remember":
        return f'"{_truncate(args.get("note", ""), 50)}"'
    if name == "compact_memory":
        return f'<rewrite, {len(args.get("new_content", ""))} chars>'
    if name == "read_skill":
        return args.get("skill_name", "?")

    # Bad-tool fallback — args is usually a string blob
    if "args" in args and len(args) == 1:
        return _truncate(args["args"], 50)

    # Generic — k=v pairs, truncated
    return ", ".join(f"{k}={_truncate(v, 25)}" for k, v in args.items())


# ---------- result summarizers -----------------------------------------


def _summarize_result(name: str, raw):
    """Returns (text, is_error)."""
    result = _parse(raw)

    # Generic error first (uniform contract from our tools)
    if isinstance(result, dict) and "error" in result:
        code = result.get("code")
        detail = result.get("detail") or result.get("error")
        remediation = result.get("remediation")
        bits = []
        if code:
            bits.append(f"{code}")
        bits.append(_truncate(detail, 50))
        if remediation:
            bits.append(f"→ {remediation}")
        return "err: " + " ".join(bits), True

    # Per-tool — readable summary
    if name == "lookup_customer" and isinstance(result, dict):
        return (
            f'{result.get("name", "?")}, {result.get("tier", "?")}, '
            f'{result.get("lifetime_orders", "?")} orders',
            False,
        )
    if name == "get_order" and isinstance(result, dict):
        status = result.get("status", "?")
        total = result.get("total_usd", "?")
        late = result.get("delivery_days_late", 0)
        late_str = f", {late}d late" if late else ""
        damaged_str = ", damaged" if result.get("damaged") else ""
        return f"{status}, ${total}{late_str}{damaged_str}", False
    if name == "get_customer_orders" and isinstance(result, dict):
        n = len(result.get("orders", []))
        return f"{n} orders", False
    if name == "issue_refund" and isinstance(result, dict):
        return (
            f'ok {result.get("ref", "")}, ${result.get("amount_usd", "?")}',
            False,
        )
    if name == "escalate_to_human" and isinstance(result, dict):
        return (
            f'ok {result.get("ticket_id", "")} (priority {result.get("priority", "normal")})',
            False,
        )
    if name in {"update_shipping_address", "cancel_order"} and isinstance(result, dict):
        return f'ok {result.get("ref", "")}', False
    if name in {"remember", "compact_memory"} and isinstance(result, dict):
        return "ok", False
    if name == "read_skill" and isinstance(result, dict):
        if "procedure" in result:
            return (
                f'{result.get("name", "?")} loaded ({len(result["procedure"])} chars)',
                False,
            )
        return _truncate(result, 60), False

    # MCP results — list of policy hits
    if isinstance(result, list):
        if not result:
            return "(empty)", False
        first = result[0]
        if isinstance(first, dict):
            label = first.get("id") or first.get("title") or first.get("name") or "?"
            extra = f" (+{len(result)-1} more)" if len(result) > 1 else ""
            return f"{label}{extra}", False
        return f"[{len(result)} items]", False

    # Bad-tool string results
    if isinstance(result, str):
        return _truncate(result, 70), False

    # Generic dict fallback
    if isinstance(result, dict):
        if result.get("ok"):
            ref = result.get("ref") or result.get("ticket_id") or ""
            return f"ok {ref}".strip(), False
        return _truncate(result, 70), False

    return _truncate(result, 70), False


# ---------- rendering --------------------------------------------------


def _render_call_with_result(step: int, name: str, args, result) -> None:
    args_str = _summarize_args(name, args)
    result_str, is_error = _summarize_result(name, result)
    arrow = "[red]✗[/red]" if is_error else "[dim]→[/dim]"
    result_style = "red" if is_error else ""
    if result_style:
        result_str = f"[{result_style}]{result_str}[/{result_style}]"
    console.print(
        f"[yellow]⏵[/yellow] [bold yellow]{name}[/bold yellow]"
        f"([dim]{args_str}[/dim]) {arrow} {result_str}"
    )


def _render_reasoning(text: str) -> None:
    console.print(f"  [dim italic]reasoning:[/dim italic] [dim]{_truncate(text, 200)}[/dim]")


def _call_id_of(raw) -> str | None:
    """Extract a tool-call id from a ToolCallItem.raw_item or
    ToolCallOutputItem.raw_item, defensively. The OpenAI Agents SDK uses
    different field names depending on the call type / version."""
    for attr in ("call_id", "id", "tool_call_id"):
        v = getattr(raw, attr, None)
        if v:
            return str(v)
    if isinstance(raw, dict):
        for attr in ("call_id", "id", "tool_call_id"):
            if raw.get(attr):
                return str(raw[attr])
    return None


async def _stream_events(result) -> None:
    """Drain stream_events() and render tool calls + results as compact one-liners.

    We buffer pending calls in a dict keyed by call_id. When the matching
    output arrives, we render `tool(args) → result` on a single line.
    Reasoning items render inline as they arrive (italic dim).
    """
    status = Status("[dim]agent thinking…[/dim]", spinner="dots", console=console)
    status.start()
    first = True
    step = 0
    pending: dict[str, tuple[int, str, object]] = {}

    try:
        async for event in result.stream_events():
            if event.type != "run_item_stream_event":
                continue

            if first:
                status.stop()
                first = False

            item = event.item
            cls = type(item).__name__

            if cls == "ToolCallItem":
                step += 1
                raw = item.raw_item
                name = getattr(raw, "name", None)
                args = getattr(raw, "arguments", None)
                if name is None and hasattr(raw, "function"):
                    name = raw.function.name
                    args = raw.function.arguments
                call_id = _call_id_of(raw) or f"_step_{step}"
                pending[call_id] = (step, name or cls, args or "{}")

            elif cls == "ToolCallOutputItem":
                call_id = _call_id_of(item.raw_item) or _call_id_of(item)
                if call_id and call_id in pending:
                    s, name, args = pending.pop(call_id)
                else:
                    # Orphan output — render what we can
                    s, name, args = step, "?", ""
                _render_call_with_result(s, name, args, item.output)

            elif cls == "ReasoningItem":
                text = getattr(item, "content", None)
                if not text:
                    raw = getattr(item, "raw_item", None)
                    if raw is not None:
                        text = getattr(raw, "content", None) or getattr(raw, "summary", None)
                if text:
                    _render_reasoning(text if isinstance(text, str) else json.dumps(text))
    finally:
        if first:
            status.stop()


# ---------------------------------------------------------------------------
# Hot-reload tracking
# ---------------------------------------------------------------------------


def _config_mtime() -> float:
    """Latest mtime across agent-profile.yaml and every skill file.

    If anything in this set is touched between turns, we rebuild the agent
    so the change takes effect immediately (no restart).
    """
    paths: list[Path] = [PROFILE_PATH]
    if SKILLS_DIR.exists():
        paths.extend(p for p in SKILLS_DIR.iterdir() if p.is_file())
    return max(
        (p.stat().st_mtime for p in paths if p.exists()),
        default=0.0,
    )


# ---------------------------------------------------------------------------
# Conversation loop
# ---------------------------------------------------------------------------


async def _process_turn(
    agent,
    deps,
    conversation: list[dict],
    customer_id: str,
    user_msg: str,
) -> list[dict]:
    """Run one turn end-to-end. Returns the updated conversation list."""
    conversation.append({"role": "user", "content": frame(customer_id, user_msg)})

    try:
        result = Runner.run_streamed(agent, conversation, context=deps)
        await _stream_events(result)
        final = result.final_output
        new_conversation = result.to_input_list()
    except Exception as e:
        console.print(f"[red]✗ agent error: {type(e).__name__}: {e}[/red]\n")
        conversation.pop()  # roll back so the conversation stays clean
        return conversation

    console.print(Panel(
        Markdown(str(final) if final is not None else "_(no reply)_"),
        title="[green]agent[/green]",
        border_style="green",
        padding=(0, 1),
    ))
    console.print()

    return new_conversation


def _banner(
    client: CustomerSupportClient,
    customer_id: str,
    tool_set: str,
    episodic: bool,
) -> None:
    customer = client.get_customer(customer_id)
    name = customer.name if customer else customer_id
    tier = customer.tier if customer else "?"
    console.print()
    console.print(Rule(
        f"[bold]Customer Support Agent[/bold] · "
        f"tools=[yellow]{tool_set}[/yellow] · "
        f"episodic_memory={'[green]on[/green]' if episodic else '[dim]off[/dim]'}"
    ))
    console.print(
        f"[dim]session: {name} ({customer_id}, {tier}-tier) · "
        f"type [bold]exit[/bold] / Ctrl-D to quit · ↑/↓ for history · "
        f"edit agent-profile.yaml or skills/ to hot-reload[/dim]"
    )
    console.print()


def _build_prompt_session() -> PromptSession:
    return PromptSession(history=FileHistory(HISTORY_FILE))


def _make_deps(identity, client: CustomerSupportClient, customer_id: str) -> Deps:
    return Deps(identity=identity, client=client, current_customer_id=customer_id)


async def _repl(customer_id: str) -> None:
    profile = load_profile()
    client = CustomerSupportClient()
    mcp = make_policy_kb_server()
    async with mcp:
        agent, identity = build_agent(
            profile=profile, customer_id=customer_id, mcp_servers=[mcp]
        )
        deps = _make_deps(identity, client, customer_id)
        session = _build_prompt_session()
        conversation: list[dict] = []
        last_mtime = _config_mtime()

        _banner(client, customer_id, profile.tool_set, profile.memory.episodic)

        while True:
            try:
                user_msg = await session.prompt_async(
                    HTML("<ansicyan><b>you ›</b></ansicyan> ")
                )
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]bye[/dim]\n")
                return

            user_msg = (user_msg or "").strip()
            if not user_msg:
                continue
            if user_msg.lower() in EXIT_TOKENS:
                console.print("[dim]bye[/dim]\n")
                return

            # Hot-reload: rebuild agent if config or skills changed
            current_mtime = _config_mtime()
            if current_mtime != last_mtime:
                profile = load_profile()
                agent, identity = build_agent(
                    profile=profile, customer_id=customer_id, mcp_servers=[mcp]
                )
                deps = _make_deps(identity, client, customer_id)
                last_mtime = current_mtime
                console.print(
                    f"[dim]✓ config reloaded · tools=[yellow]{profile.tool_set}[/yellow] · "
                    f"episodic={'on' if profile.memory.episodic else 'off'}[/dim]\n"
                )

            conversation = await _process_turn(agent, deps, conversation, customer_id, user_msg)
            console.print(Rule(style="dim"))


async def _one_shot(customer_id: str, message: str) -> None:
    profile = load_profile()
    client = CustomerSupportClient()
    mcp = make_policy_kb_server()
    async with mcp:
        agent, identity = build_agent(
            profile=profile, customer_id=customer_id, mcp_servers=[mcp]
        )
        deps = _make_deps(identity, client, customer_id)

        _banner(client, customer_id, profile.tool_set, profile.memory.episodic)
        customer = client.get_customer(customer_id)
        label = customer.name if customer else customer_id
        console.print(Panel(
            message,
            title=f"[cyan]you · {label}[/cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))
        console.print()
        await _process_turn(agent, deps, [], customer_id, message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive CLI for the customer support agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--customer",
        default="cust_001",
        help="Customer ID for the verified session (default: cust_001 / Alice). "
             "Also: cust_002 (Bob, §3), cust_003 (Carol, §4b business tier).",
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="If provided, runs as one-shot and exits. Otherwise drops into REPL.",
    )
    args = parser.parse_args()

    try:
        if args.message:
            asyncio.run(_one_shot(args.customer, args.message))
        else:
            asyncio.run(_repl(args.customer))
    except KeyboardInterrupt:
        console.print("\n[dim]bye[/dim]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
