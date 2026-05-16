"""Load the agent profile from agent-profile.yaml.

The YAML is the complete declarative description of the agent: identity,
model, tool set, skill directory, MCP servers, memory config, refund cap.
`agent/core.py` is a loader on top of this.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROFILE_PATH = Path(__file__).parent.parent / "agent-profile.yaml"


@dataclass
class MemoryConfig:
    # Within-session chat history. Persisted per-customer by Strands' FileSessionManager
    # when True; when False the agent's message list is cleared between turns.
    conversation: bool = True
    # Past-sessions per-customer summary in memory/customer_<id>.md, loaded fully
    # into the system prompt.
    episodic: bool = False


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


# Minimal fallback if agent.system_prompt is missing from YAML. Keep this
# functional but stark so the user notices and restores the real template.
_DEFAULT_SYSTEM_PROMPT = (
    "You are {name} (agent_id={agent_id}). Help customers with order issues. "
    "You can issue refunds up to ${refund_cap_usd:.2f}; escalate larger ones. "
    "(NOTE: `agent.system_prompt` is missing from agent-profile.yaml — "
    "restore the full template from the lab README.)"
)


@dataclass
class Profile:
    agent_id: str
    name: str
    model: str
    language: str
    system_prompt: str
    skills_dir: str | None
    mcp_servers: list[MCPServerConfig]
    memory: MemoryConfig
    refund_cap_usd: float


def load_profile(path: Path = PROFILE_PATH) -> Profile:
    """Read agent-profile.yaml and return a typed Profile."""
    if not path.exists():
        raise FileNotFoundError(f"agent-profile.yaml not found at {path}. See README.")
    raw = yaml.safe_load(path.read_text())

    agent_section = raw.get("agent", {})
    memory_section = raw.get("memory", {})
    mcp_section = raw.get("mcp_servers") or []

    mcp_servers = [
        MCPServerConfig(
            name=entry["name"],
            command=entry["command"],
            args=list(entry.get("args", [])),
            env=dict(entry.get("env", {})),
        )
        for entry in mcp_section
    ]

    return Profile(
        agent_id=agent_section.get("id", "cs-agent-v1"),
        name=agent_section.get("name", "Customer Support Agent"),
        model=agent_section.get("model", "gpt-4o-2024-08-06"),
        language=agent_section.get("language", "English"),
        system_prompt=agent_section.get("system_prompt") or _DEFAULT_SYSTEM_PROMPT,
        skills_dir=raw.get("skills_dir"),
        mcp_servers=mcp_servers,
        memory=MemoryConfig(
            conversation=memory_section.get("conversation", True),
            episodic=memory_section.get("episodic", False),
        ),
        refund_cap_usd=float(raw.get("refund_cap_usd", 200.0)),
    )
