"""The agent factory — `build_agent()`.

This is the "thin harness" the §1 demo points at. The function below does:

  1. Loads the agent profile from agent-profile.yaml (identity, tool_set,
     memory toggles, refund cap)
  2. Picks the tool set (good or bad — the §2 toggle)
  3. Builds the skill catalog (name + description per skill — Anthropic-
     style; the agent loads full procedures on demand via read_skill)
  4. Loads the customer's episodic memory if `memory.episodic: true` and
     a customer_id was passed
  5. Wires the MCP policy-KB server
  6. Constructs `agents.Agent(...)` and returns it

That's it. The intelligence lives in the tools, the skills, the policies,
and the MCP server. The agent itself is configuration + a control loop
(loop is inside the SDK; we don't write it).
"""
from agents import Agent
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv

from agent import memory
from agent.identity import AgentIdentity
from agent.profile import Profile, load_profile
from agent.skills import list_skills
from agent.tools import ALL_TOOLS as GOOD_TOOLS
from agent.tools_bad import ALL_TOOLS as BAD_TOOLS

load_dotenv()


def _skill_catalog() -> str:
    """Build the Anthropic-style skill catalog for the system prompt.

    Just `name: description` per skill. The agent reads this index to decide
    which skill applies, then calls `read_skill(name)` to load the full
    procedure. Full skill bodies don't go in the system prompt — that would
    bloat the context and hide skill usage from the trace.

    Files starting with underscore (`_TEMPLATE.md`) are skipped — they're
    templates, not real skills.
    """
    skills = list_skills()
    if not skills:
        return ""
    lines = [f"- **{s.name}**: {s.description}" for s in skills]
    return "\n".join(lines)


def _memory_section(
    enabled: bool,
    customer_id: str | None,
    memory_content: str,
    writable: bool,
) -> str:
    """Build the Episodic Memory section of the system prompt.

    Simple pattern: load the customer's memory file FULLY into the prompt
    (same as Claude Code's CLAUDE.md, GitHub Copilot's instructions file).
    No retrieval, no on-demand loading — the file is small enough.

    The agent maintains memory via the `remember` and `compact_memory` tools.
    """
    if not enabled or customer_id is None:
        return ""  # episodic disabled — no section at all

    if not memory_content:
        # No prior interactions yet
        if writable:
            return (
                "No prior interactions on file for this customer yet. "
                "After resolving the current request, use `remember(<concise note>)` "
                "to start their record."
            )
        return "No prior interactions on file for this customer yet."

    # Memory exists — embed it directly, then explain the write tools
    parts = [memory_content.strip()]
    if writable:
        parts.append(
            "\n---\n"
            "Use `remember(<concise note>)` after resolving the request to "
            "record anything a future agent should know. Use `compact_memory("
            "<rewrite>)` sparingly when memory grows long and rambling — "
            "you're overwriting, so be careful."
        )
    else:
        parts.append(
            "\n---\n"
            "(Read-only in this configuration — you have no tool to update memory.)"
        )
    return "\n".join(parts)


def _build_instructions(
    identity: AgentIdentity,
    skill_catalog: str = "",
    skills_loadable: bool = True,
    memory_section: str = "",
) -> str:
    parts = [
        f"You are {identity.name} (agent_id={identity.agent_id}).",
        "Your job: help customers with order issues efficiently, accurately, and on policy.",
        "",
        "## Session context",
        "Every customer message arrives prefixed with `[verified customer_id=<id>]`. "
        "That ID is the customer you're speaking with — already authenticated "
        "through their account session. **Do NOT ask the customer for their ID** "
        "— you already have it. Use it directly in your tool calls "
        "(`lookup_customer`, `escalate_to_human`, etc.).",
        "",
        "## Your authority",
        f"- You can issue refunds up to ${identity.refund_cap_usd:.2f}.",
        "- Refunds ABOVE your cap MUST be escalated via `escalate_to_human`. "
        "Do NOT split into smaller refunds — that's a policy violation flagged in audit.",
        "- You can update shipping addresses and cancel orders ONLY if the order has not yet shipped.",
        "- Always include a reason on writes; it's audit-logged.",
        "",
        "## Approach",
        "1. Look up the customer (using the verified ID from the message prefix) to "
        "get their profile and tier — useful context for tone and authority.",
        "2. Look up the order(s) referenced before acting.",
        "3. Check policy via `search_policy_kb` BEFORE compensating actions "
        "(refunds, credits). Don't memorize rules — they change.",
        "4. If a tool returns an error, READ it. A `policy_violation` (code 403) is "
        "permanent — do NOT retry; escalate. A transient error (network, timeout) "
        "is worth one retry.",
        "5. If unsure or the situation feels adversarial, escalate with priority `high`.",
        "",
        "## Style",
        "Friendly, concise English. Acknowledge the customer's frustration when relevant. "
        "Cite policy by name once. Don't explain your tool calls.",
    ]
    if skill_catalog:
        parts.append("\n## Skills available")
        if skills_loadable:
            parts.append(
                "When a customer's request matches a skill's description below, "
                "call `read_skill(<name>)` to load the full procedure, then follow "
                "it step by step. The descriptions tell you when each skill applies; "
                "the full procedure comes from `read_skill`.\n"
            )
        else:
            parts.append(
                "Note: these skills describe how a well-equipped agent would handle "
                "common situations. You do not have a tool to load their procedures "
                "in this configuration — you'll have to improvise with the tools you "
                "have. Escalate if you're unsure.\n"
            )
        parts.append(skill_catalog)
    if memory_section:
        parts.append("\n## Episodic memory\n\n" + memory_section)
    return "\n".join(parts)


def _build_identity(profile: Profile) -> AgentIdentity:
    """Construct the scoped AgentIdentity from the YAML profile."""
    return AgentIdentity(
        agent_id=profile.agent_id,
        name=profile.name,
        refund_cap_usd=profile.refund_cap_usd,
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


def make_policy_kb_server() -> MCPServerStdio:
    """Construct (but do not connect) the policy-KB MCP server.

    The agent calls `search_policy_kb` as if it were a native tool; under
    the hood the OpenAI Agents SDK forwards to this subprocess, which reads
    `policies/*.md` and returns matches.

    Caller is responsible for the lifecycle:
        async with make_policy_kb_server() as mcp:
            agent, identity = build_agent(mcp_servers=[mcp])
    """
    return MCPServerStdio(
        name="policy_kb",
        params={
            "command": "python",
            "args": ["-m", "mcp_server.server"],
        },
    )


def build_agent(
    profile: Profile | None = None,
    customer_id: str | None = None,
    mcp_servers: list | None = None,
) -> tuple[Agent, AgentIdentity]:
    """Build the customer support agent from the YAML profile.

    Args:
        profile: a loaded Profile. If None, reads agent-profile.yaml.
        customer_id: optional. If set AND `profile.memory.episodic` is True,
                     the customer's episodic memory is injected into the
                     system prompt at build time.
        mcp_servers: pre-connected MCP servers to attach. If None, a fresh
                     (un-connected) policy_kb server is created — useful only
                     when the caller wraps the agent in `async with`.

    Returns:
        (Agent, AgentIdentity) — the Agent for `Runner.run_streamed(...)` and
        the AgentIdentity for the `Deps` object the tools see.
    """
    if profile is None:
        profile = load_profile()

    identity = _build_identity(profile)

    # Build the skill catalog (just name+description; full procedures load on
    # demand via the `read_skill` tool — Anthropic's skills pattern).
    skill_catalog = _skill_catalog()

    # Whether the agent can actually call read_skill / recall_customer_memory /
    # remember. Tied to the tool set: `good` has them, `bad` doesn't — so the
    # bad-tools agent sees the catalogs but can't load anything. Part of the
    # §2 contrast.
    capable_tools = profile.tool_set == "good"

    # Episodic memory — load the full file into the prompt when enabled.
    # Same pattern as Claude Code's CLAUDE.md. The agent has `remember` and
    # `compact_memory` tools to update it.
    customer_memory = ""
    if profile.memory.episodic and customer_id:
        customer_memory = memory.load(customer_id)

    memory_section = _memory_section(
        enabled=profile.memory.episodic,
        customer_id=customer_id,
        memory_content=customer_memory,
        writable=capable_tools,
    )

    tools = GOOD_TOOLS if profile.tool_set == "good" else BAD_TOOLS

    if mcp_servers is None:
        mcp_servers = [make_policy_kb_server()]

    agent = Agent(
        name=identity.name,
        instructions=_build_instructions(
            identity,
            skill_catalog=skill_catalog,
            skills_loadable=capable_tools,
            memory_section=memory_section,
        ),
        model=profile.model,
        tools=tools,
        mcp_servers=mcp_servers,
    )
    return agent, identity
