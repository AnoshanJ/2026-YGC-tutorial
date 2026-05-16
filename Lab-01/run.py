"""Interactive CLI for the customer support agent.

Default: a multi-turn conversation. Type your question, the agent runs (and
streams tool calls), you see a compact one-line trace, then a Markdown
panel with the reply. Exit with `exit` / `quit` / `:q` / Ctrl-C / Ctrl-D.

The agent is built once per launch — there is no hot-reload. To apply edits
to `agent-profile.yaml`, `skills/`, or anything else: type `exit`, then
`python run.py` again. Strands owns every MCP subprocess as a ToolProvider,
so an `exit` cleanly shuts everything down.

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
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.status import Status
from rich.table import Table
from rich.text import Text

from agent.core import build_agent
from agent.profile import load_profile
from mocks.client import CustomerSupportClient

# Load .env into os.environ before the OpenAI client is constructed and
# before any MCP subprocess is spawned (make_mcp_client inherits os.environ),
# so OPENAI_API_KEY etc. are visible at runtime.
load_dotenv(Path(__file__).parent / ".env")

# Strands' AgentSkills plugin can warn on prompt re-injection in edge cases —
# harmless in our flow but noisy on stage. Silence it.
logging.getLogger("strands.vended_plugins.skills.agent_skills").setLevel(logging.ERROR)

ROOT = Path(__file__).parent
SKILLS_DIR = ROOT / "skills"

console = Console()

EXIT_TOKENS = {"exit", "quit", "/exit", "/quit", ":q", "bye"}
HISTORY_FILE = str(ROOT / ".repl_history")


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


def frame(_customer_id: str, message: str) -> str:
    """Pass the user message through unchanged.

    The customer's identity is bound at the harness layer via
    `agent.hooks.CustomerIdBindingHook` — it never appears in text the LLM
    can read. The model has no syntactic handle on the customer_id and
    cannot manipulate it via prompt injection. If a tool needs the ID, the
    hook injects the trusted value into the tool call's input dict just
    before dispatch."""
    return message


# ---------------------------------------------------------------------------
# Trace rendering (compact one-liner per tool call)
# ---------------------------------------------------------------------------


def _truncate(text, n: int = 50) -> str:
    s = str(text) if text is not None else ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _parse(obj):
    """Return obj as a Python object (parses JSON strings best-effort)."""
    if isinstance(obj, (dict, list)) or obj is None:
        return obj
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except (ValueError, TypeError):
            return obj
    return obj


def _summarize_args(name: str, raw) -> str:
    args = _parse(raw)
    if not isinstance(args, dict):
        return _truncate(args, 60)

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
            f"{args.get('order_id', '?')}, "
            f"${args.get('amount_usd', '?')}, "
            f'"{_truncate(args.get("reason", ""), 30)}"'
        )
    if name == "escalate_to_human":
        return (
            f"priority={args.get('priority', 'normal')}, "
            f'"{_truncate(args.get("reason", ""), 40)}"'
        )
    if name == "remember":
        return f'"{_truncate(args.get("note", ""), 50)}"'
    if name == "compact_memory":
        return f"<rewrite, {len(args.get('new_content', ''))} chars>"
    if name == "skills":  # AgentSkills plugin's loader tool
        return args.get("skill_name", "?")

    # Bad-tool fallback: single string arg
    if "args" in args and len(args) == 1:
        return _truncate(args["args"], 50)

    return ", ".join(f"{k}={_truncate(v, 25)}" for k, v in args.items())


def _summarize_result(name: str, raw):
    """Returns (text, is_error)."""
    result = _parse(raw)

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

    if name == "lookup_customer" and isinstance(result, dict):
        return (
            f"{result.get('name', '?')}, {result.get('tier', '?')}, "
            f"{result.get('lifetime_orders', '?')} orders",
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
            f"ok {result.get('ref', '')}, ${result.get('amount_usd', '?')}",
            False,
        )
    if name == "escalate_to_human" and isinstance(result, dict):
        return (
            f"ok {result.get('ticket_id', '')} (priority {result.get('priority', 'normal')})",
            False,
        )
    if name in {"update_shipping_address", "cancel_order"} and isinstance(result, dict):
        return f"ok {result.get('ref', '')}", False
    if name in {"remember", "compact_memory"} and isinstance(result, dict):
        return "ok", False
    if name == "skills":
        # AgentSkills returns the skill body as a string (or dict with content).
        if isinstance(result, str):
            return f"skill loaded ({len(result)} chars)", False
        if isinstance(result, dict):
            body = (
                result.get("instructions")
                or result.get("body")
                or result.get("content")
            )
            if body:
                return f"skill loaded ({len(body)} chars)", False
        return _truncate(result, 60), False

    if isinstance(result, list):
        if not result:
            return "(empty)", False
        first = result[0]
        if isinstance(first, dict):
            label = first.get("id") or first.get("title") or first.get("name") or "?"
            extra = f" (+{len(result) - 1} more)" if len(result) > 1 else ""
            return f"{label}{extra}", False
        return f"[{len(result)} items]", False

    if isinstance(result, str):
        return _truncate(result, 70), False

    if isinstance(result, dict):
        if result.get("ok"):
            ref = result.get("ref") or result.get("ticket_id") or ""
            return f"ok {ref}".strip(), False
        return _truncate(result, 70), False

    return _truncate(result, 70), False


def _render_call(name: str, args, result) -> None:
    args_str = _summarize_args(name, args)
    result_str, is_error = _summarize_result(name, result)
    arrow = "[red]✗[/red]" if is_error else "[dim]→[/dim]"
    if is_error:
        result_str = f"[red]{result_str}[/red]"
    console.print(
        f"[yellow]⏵[/yellow] [bold yellow]{name}[/bold yellow]"
        f"([dim]{args_str}[/dim]) {arrow} {result_str}"
    )


# ---------------------------------------------------------------------------
# Strands event handling
# ---------------------------------------------------------------------------


def _extract_tool_use(event: dict):
    """Pull (id, name, input) out of a Strands stream event if it's a tool-use
    event. Returns None otherwise. Strands' streaming chunks for tool use
    typically look like {"current_tool_use": {"name": ..., "input": ..., "toolUseId": ...}}.
    """
    tu = event.get("current_tool_use") if isinstance(event, dict) else None
    if not tu or not tu.get("name"):
        return None
    return (
        tu.get("toolUseId") or tu.get("id") or tu.get("name"),
        tu["name"],
        tu.get("input", {}),
    )


def _extract_tool_results_from_messages(messages: list) -> dict:
    """Walk the agent's message history and return a {tool_use_id: result_content}
    map. Strands stores tool returns as `role=user` (or `role=tool`) messages
    with `toolResult` content blocks. Defensive across shapes."""
    out: dict = {}
    for msg in messages or []:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not content:
            continue
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                tr = block.get("toolResult") or block.get("tool_result")
                if isinstance(tr, dict):
                    tu_id = tr.get("toolUseId") or tr.get("tool_use_id") or tr.get("id")
                    # content might be a string, list of {"text": ...}, or dict
                    body = tr.get("content")
                    if isinstance(body, list) and body:
                        first = body[0]
                        if isinstance(first, dict):
                            body = first.get("text") or first.get("json") or first
                    if tu_id:
                        out[tu_id] = body
    return out


async def _run_turn(agent, message: str) -> str:
    """Drive one agent turn. Each tool call streams to the trace LIVE.

    We listen for two Strands callback events on `stream_async`:
      - ModelMessageEvent     (role=assistant) → tool uses with parsed input
      - ToolResultMessageEvent (role=user)     → tool results

    The mid-stream `current_tool_use` deltas carry input as a partial JSON
    string that's never re-emitted as a parsed dict, so they're useless
    for our trace. The two message-events above are emitted right after
    each model turn / tool batch finishes — they're the live signal.
    """
    status = Status("[dim]agent thinking…[/dim]", spinner="dots", console=console)
    status.start()
    first = True
    # tu_id -> {"name": str, "args": dict, "rendered": bool}
    pending: dict[str, dict] = {}
    final_text_parts: list[str] = []

    def _record_tool_use(block: dict) -> None:
        tu = block.get("toolUse") or block.get("tool_use")
        if not isinstance(tu, dict):
            return
        tu_id = tu.get("toolUseId") or tu.get("id")
        name = tu.get("name")
        if not tu_id or not name:
            return
        pending[tu_id] = {
            "name": name,
            "args": tu.get("input") or {},
            "rendered": False,
        }

    def _flush_result(block: dict) -> None:
        tr = block.get("toolResult") or block.get("tool_result")
        if not isinstance(tr, dict):
            return
        tu_id = tr.get("toolUseId") or tr.get("tool_use_id") or tr.get("id")
        slot = pending.get(tu_id) if tu_id else None
        if slot is None or slot["rendered"]:
            return
        body = tr.get("content")
        if isinstance(body, list) and body:
            head = body[0]
            if isinstance(head, dict):
                body = head.get("text") or head.get("json") or head
        _render_call(slot["name"], slot["args"], body)
        slot["rendered"] = True

    try:
        async for event in agent.stream_async(message):
            if first:
                status.stop()
                first = False

            if not isinstance(event, dict):
                continue

            # Final reply streams as text deltas — collect for the Markdown panel
            data = event.get("data")
            if isinstance(data, str):
                final_text_parts.append(data)

            # ModelMessageEvent / ToolResultMessageEvent both expose `message`
            msg = event.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            role = msg.get("role")
            for block in content:
                if not isinstance(block, dict):
                    continue
                if role == "assistant":
                    _record_tool_use(block)
                elif role == "user":
                    _flush_result(block)
    finally:
        if first:
            status.stop()

    # Catch-all: render any tool whose result didn't come through as an event
    # (shouldn't happen with the message-events above, but the audit shouldn't
    # silently drop calls).
    messages = getattr(agent, "messages", []) or []
    results_by_id = _extract_tool_results_from_messages(messages)
    for tu_id, slot in pending.items():
        if slot["rendered"]:
            continue
        _render_call(
            slot["name"],
            slot["args"],
            results_by_id.get(tu_id, "(no result captured)"),
        )
        slot["rendered"] = True

    # Final reply: prefer streamed text; fall back to last assistant message
    final_reply = "".join(final_text_parts).strip()
    if not final_reply and messages:
        for msg in reversed(messages):
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                final_reply = content
                break
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if text:
                            final_reply = text
                            break
                if final_reply:
                    break

    return final_reply or "(no reply)"


# ---------------------------------------------------------------------------
# Banner + prompt
# ---------------------------------------------------------------------------


def _flag(on: bool) -> Text:
    return Text("● on", style="bold green") if on else Text("○ off", style="dim")


def _discover_skills(skills_dir: Path = SKILLS_DIR) -> list[str]:
    """Return the names of skills the agent will load — every subdirectory
    of skills_dir that contains a SKILL.md. Names match the directory name
    (Strands convention: lowercase + hyphens). Same surface area as the
    AgentSkills plugin auto-discovery in `agent/core.py`."""
    if not skills_dir.exists():
        return []
    return sorted(
        p.name for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists()
    )


def _banner(
    client: CustomerSupportClient,
    customer_id: str,
    mcp_names: list[str],
    conversation: bool,
    episodic: bool,
) -> None:
    """Startup banner — a panel with a key/value layout so wide-terminal
    rendering doesn't truncate and the demo state pops at a glance."""
    customer = client.get_customer(customer_id)
    name = customer.name if customer else customer_id
    tier = customer.tier if customer else "?"

    grid = Table.grid(padding=(0, 1), expand=False)
    grid.add_column(style="dim", justify="right", no_wrap=True)
    grid.add_column()

    grid.add_row(
        "session",
        Text.assemble(
            (name, "bold"),
            (f"  ({customer_id} · {tier} tier)", "dim"),
        ),
    )
    mcps = ", ".join(mcp_names) if mcp_names else "(none)"
    grid.add_row("mcps", Text(mcps, style="yellow"))
    skills = _discover_skills()
    skills_str = ", ".join(skills) if skills else "(none)"
    grid.add_row("skills", Text(skills_str, style="magenta"))
    grid.add_row(
        "memory",
        Text.assemble(
            ("conversation ", ""),
            _flag(conversation),
            ("    episodic ", ""),
            _flag(episodic),
        ),
    )

    hint = Text.assemble(
        ("exit", "bold"),
        (" / Ctrl-D to quit  ·  ", "dim"),
        ("↑/↓", "bold"),
        (" history  ·  edit ", "dim"),
        ("agent-profile.yaml", "bold"),
        (" or ", "dim"),
        ("skills/", "bold"),
        (" then ", "dim"),
        ("exit", "bold"),
        (" + ", "dim"),
        ("python run.py", "bold"),
        (" to apply", "dim"),
    )

    console.print()
    console.print(
        Panel(
            Group(grid, Text(""), hint),
            title="[bold]Customer Support Agent[/bold]",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()


def _build_prompt_session() -> PromptSession:
    return PromptSession(history=FileHistory(HISTORY_FILE))


# ---------------------------------------------------------------------------
# Run loops
# ---------------------------------------------------------------------------


async def _process_turn(agent, customer_id: str, user_msg: str) -> None:
    framed = frame(customer_id, user_msg)
    try:
        final = await _run_turn(agent, framed)
    except Exception as e:
        console.print(f"[red]✗ agent error: {type(e).__name__}: {e}[/red]\n")
        return

    console.print(
        Panel(
            Markdown(final),
            title="[green]agent[/green]",
            border_style="green",
            padding=(0, 1),
        )
    )
    console.print()


async def _repl(customer_id: str) -> None:
    profile = load_profile()
    display_client = CustomerSupportClient()  # for banner / customer name lookup

    agent, _identity = build_agent(profile=profile, customer_id=customer_id)
    session = _build_prompt_session()

    _banner(
        display_client,
        customer_id,
        [s.name for s in profile.mcp_servers],
        profile.memory.conversation,
        profile.memory.episodic,
    )

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

        await _process_turn(agent, customer_id, user_msg)

        # Conversation memory off → agent forgets between turns. With it on,
        # FileSessionManager has already persisted this turn to disk.
        if not profile.memory.conversation:
            agent.messages.clear()

        console.print(Rule(style="dim"))


async def _one_shot(customer_id: str, message: str) -> None:
    profile = load_profile()
    display_client = CustomerSupportClient()

    agent, _identity = build_agent(profile=profile, customer_id=customer_id)

    _banner(
        display_client,
        customer_id,
        [s.name for s in profile.mcp_servers],
        profile.memory.conversation,
        profile.memory.episodic,
    )
    customer = display_client.get_customer(customer_id)
    label = customer.name if customer else customer_id
    console.print(
        Panel(
            message,
            title=f"[cyan]you · {label}[/cyan]",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()
    await _process_turn(agent, customer_id, message)


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
