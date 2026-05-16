"""The agent factory — `build_agent()`.

A thin loader. The agent has NO tools of its own — every tool comes from
an MCP server declared in `agent-profile.yaml`'s `mcp_servers` list, and
every `MCPClient` is passed straight to `Agent(tools=[...])` so Strands'
ToolProvider lifecycle owns the subprocesses end-to-end (`start()` on
first tool load; `stop()` when the Agent is GC'd / loses its last consumer).

For the §2a hands-on: edit the YAML to swap `customer_support_v1` for
`customer_support_v2`, type `exit`, run `python run.py` again. No
hot-reload — keeping the build path one direction makes the architecture
obvious on stage.
"""

import os
from pathlib import Path

from mcp import StdioServerParameters, stdio_client
from strands import Agent, AgentSkills
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient

from agent import memory
from agent.hooks import CustomerIdBindingHook, RefundCapHook
from agent.identity import AgentIdentity
from agent.profile import MCPServerConfig, Profile, load_profile

ROOT = Path(__file__).parent.parent
# Both forms of memory live under one root so the audience can see at a
# glance that conversation history and episodic notes are the same family:
#   memory/episodic/customer_<id>.md      — curated, agent-written via remember()
#   memory/sessions/session_<id>/...      — raw transcript, Strands-managed
SESSIONS_DIR = ROOT / "memory" / "sessions"


# ---------------------------------------------------------------------------
# MCP server construction
# ---------------------------------------------------------------------------


def make_mcp_client(config: MCPServerConfig) -> MCPClient:
    """Build a Strands MCPClient from a profile entry.

    Env vars inherit the parent's environment so the subprocess has PATH,
    PYTHONPATH, OPENAI_API_KEY, etc. — plus whatever this config injects.

    The returned client is a `ToolProvider`: pass it directly to
    `Agent(tools=[...])`. Strands spawns the subprocess on first tool load
    and stops it when the Agent is finalized — no manual `__enter__` /
    `__exit__` needed.
    """
    full_env = dict(os.environ)
    full_env.update(config.env)
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command=config.command,
                args=list(config.args),
                env=full_env,
            )
        )
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def _memory_section(
    enabled: bool,
    customer_id: str | None,
    memory_content: str,
) -> str:
    """Render the Episodic Memory block.

    Loads the customer's memory file FULLY into the prompt (Claude Code /
    Copilot pattern). The agent updates it via the `remember` /
    `compact_memory` local tools — registered alongside MCP clients in
    `build_agent` and only attached when episodic memory is enabled.

    The protocol (verify pointers via tools, observations shape tone, close
    the loop with `remember()`) is inlined here rather than expressed as a
    discoverable skill — when episodic memory is on, this procedure always
    applies, so it's part of the prompt, not a "decision" the agent makes.
    """
    if not enabled or customer_id is None:
        return ""

    body = (
        memory_content.strip()
        if memory_content
        else "No prior interactions on file for this customer yet."
    )

    protocol = (
        "**Protocol for using the memory above:**\n\n"
        "1. **Treat entries as pointers, not data.** For every concrete "
        "claim in the notes — a ticket ID, refund ref, order ID, amount — "
        "verify the current state via the matching read tool "
        "(`get_open_tickets`, `get_refund_history`, `get_order`, "
        "`lookup_customer`) BEFORE letting it influence an action. Memory "
        "may be stale; the audit ledger and APIs are the source of truth.\n"
        "2. **Use observations to shape tone, never numbers.** "
        '"Repeat customer, second damaged delivery" is fine for phrasing; '
        '"$58 already refunded" requires verifying the ledger first.\n'
        "3. **Close the loop on every non-trivial interaction.** Call "
        '`remember(customer_id="", note=<short note>)` at the end. **Write '
        "a note small enough to fit on a sticky.** Record what tools "
        "*cannot* tell the next agent: tone, patterns, open promises, "
        "pointers to verify next time. Strip everything an API call would "
        "return.\n\n"
        "**Concrete example — Alice complains her order #1234 is late, "
        "you issue a $10 shipping_delay credit.**\n\n"
        "  ❌ BAD (re-documents data the audit ledger already holds):\n"
        "  > Customer reported order #1234 late. Verified order is "
        "in_transit_delayed with DHL, 4 business days late. No prior "
        "refunds on file. Issued $10 shipping_delay_credit per policy with "
        "ref recorded in ledger. Set expectation to keep tracking; will "
        "follow up if not delivered soon.\n\n"
        "  ✅ GOOD (only what tools cannot fetch):\n"
        "  > #1234 first delay complaint. Told her 1–2 more days. "
        "Tone: reasonable.\n\n"
        "Every fact in the BAD note is verifiable via `get_order` / "
        "`get_refund_history` / `search_policy_kb`; the next agent will "
        "fetch them anyway. The GOOD note captures only the promise made "
        "and the tone — the two things tools can't surface. Procedural "
        'follow-up instructions ("if she follows up, trace + escalate per '
        "policy\") do NOT belong here either — that's policy recap, and "
        "`handle-refund` + `search_policy_kb` already cover it."
    )

    return f"{body}\n\n---\n{protocol}"


def _build_instructions(profile: Profile, memory_section: str = "") -> str:
    """Render the system prompt from `profile.system_prompt`.

    Every field of the loaded profile is available as a placeholder —
    add a field to YAML and it's automatically referenceable as `{name}`,
    `{agent_id}`, `{refund_cap_usd}`, `{model}`, etc. The episodic memory
    block is the only part that stays in Python because the customer's
    memory file is loaded per-build.
    """
    base = profile.system_prompt.format(**vars(profile))
    if memory_section:
        base += "\n\n## Episodic memory\n\n" + memory_section

    if profile.skills_dir:
        base += "\n\n## Available skills\n\n"
    return base


# ---------------------------------------------------------------------------
# Build the agent
# ---------------------------------------------------------------------------


def _resolve_skills_dir(profile: Profile) -> Path | None:
    if not profile.skills_dir:
        return None
    path = Path(profile.skills_dir)
    if not path.is_absolute():
        path = ROOT / path
    return path if path.exists() else None


def build_agent(
    profile: Profile | None = None,
    customer_id: str | None = None,
) -> tuple[Agent, AgentIdentity]:
    """Build the customer support agent.

    One Agent per REPL run; the YAML is read once at construct time.
    Editing YAML or skills/ on disk has no effect until the next launch.

    Args:
        profile: loaded Profile (defaults to agent-profile.yaml).
        customer_id: needed when memory.episodic is True (to load the
            right customer's memory file) and when memory.conversation
            is True (used as the SessionManager session_id).
    """
    if profile is None:
        profile = load_profile()

    identity = AgentIdentity(
        agent_id=profile.agent_id,
        name=profile.name,
        refund_cap_usd=profile.refund_cap_usd,
    )

    # --- Episodic memory: load the customer's memory file into the prompt ---
    customer_memory = (
        memory.load(customer_id) if profile.memory.episodic and customer_id else ""
    )
    memory_section = _memory_section(
        enabled=profile.memory.episodic,
        customer_id=customer_id,
        memory_content=customer_memory,
    )

    # --- Tools: every MCP server in the YAML, passed as ToolProviders.
    # Strands handles subprocess lifecycle — see make_mcp_client docstring.
    mcp_clients = [make_mcp_client(cfg) for cfg in profile.mcp_servers]

    # --- Local tools: episodic memory writes. Live in-process with the agent
    # because they're session-scoped state the agent owns end-to-end — no
    # team / deployment boundary to cross (README §2b's "tools that stay
    # local" rule). Only attached when episodic memory is enabled, so the
    # tool catalog matches what's documented in the system prompt.
    local_tools: list = []
    if profile.memory.episodic:
        local_tools.extend([memory.remember, memory.compact_memory])

    # --- Skills: AgentSkills plugin auto-discovers SKILL.md under skills_dir,
    # injects the catalog into the system prompt, and registers a `skills`
    # loader tool the agent calls to read a skill body on demand.
    plugins: list = []
    skills_dir = _resolve_skills_dir(profile)
    if skills_dir:
        plugins.append(AgentSkills(skills=[str(skills_dir)]))

    # --- Conversation memory: Strands' FileSessionManager keyed by customer_id.
    # Two users → two session_ids → two on-disk directories, fully isolated.
    # Without it `agent.messages` is a per-process list — fine for this single-
    # user CLI, but a cross-user leak in any multi-tenant deployment.
    session_manager = None
    if profile.memory.conversation and customer_id:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session_manager = FileSessionManager(
            session_id=customer_id,
            storage_dir=str(SESSIONS_DIR),
        )

    # --- Identity binding: the harness, not the LLM, is the principal.
    # Every customer-scoped tool call has its `customer_id` arg overwritten
    # with the session's trusted ID. Prompt injection can no longer cross
    # customer boundaries (OWASP API#1). See agent/hooks.py.
    hooks_: list = []
    if customer_id:
        hooks_.append(CustomerIdBindingHook(customer_id=customer_id))
    # Enforce the agent's scoped refund authority at the harness, so even a
    # prompt-injected agent cannot exceed its cap. The v2 MCP server has a
    # matching server-side check as defense in depth — the hook just makes
    # sure the bad call never reaches the wire.
    hooks_.append(RefundCapHook(refund_cap_usd=profile.refund_cap_usd))

    agent = Agent(
        agent_id=profile.agent_id,
        name=profile.name,
        description=f"Customer support agent. Refund authority up to ${profile.refund_cap_usd:.2f}.",
        model=OpenAIModel(model_id=profile.model),
        system_prompt=_build_instructions(profile, memory_section),
        tools=[*mcp_clients, *local_tools],
        plugins=plugins,
        hooks=hooks_,
        session_manager=session_manager,
        # Suppress Strands' default PrintingCallbackHandler — it streams text
        # chunks straight to stdout (no newlines), which collides with our own
        # trace rendering in run.py. We collect tokens from stream_async events
        # ourselves and render the final reply inside a Rich Panel.
        callback_handler=None,
    )
    return agent, identity
