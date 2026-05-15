"""Load the agent profile from agent-profile.yaml.

The YAML file is the single source of truth for the agent's identity, model,
which tool set to register, which memory types are active, and the refund cap.
The §2 / §3 / §5 toggles all live in that file.

`load_profile()` returns a Profile dataclass. `build_agent()` in core.py
consumes it.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROFILE_PATH = Path(__file__).parent.parent / "agent-profile.yaml"


@dataclass
class MemoryConfig:
    conversation: bool = True
    episodic: bool = False
    semantic: bool = False


@dataclass
class Profile:
    agent_id: str
    name: str
    model: str
    tool_set: str            # "good" | "bad"
    memory: MemoryConfig
    refund_cap_usd: float


def load_profile(path: Path = PROFILE_PATH) -> Profile:
    """Read agent-profile.yaml and return a typed Profile."""
    if not path.exists():
        raise FileNotFoundError(
            f"agent-profile.yaml not found at {path}. "
            "This file is required — see README."
        )
    raw = yaml.safe_load(path.read_text())

    agent_section = raw.get("agent", {})
    memory_section = raw.get("memory", {})

    tool_set = raw.get("tool_set", "good")
    if tool_set not in ("good", "bad"):
        raise ValueError(
            f"agent-profile.yaml: tool_set must be 'good' or 'bad', got {tool_set!r}"
        )

    return Profile(
        agent_id=agent_section.get("id", "cs-agent-v1"),
        name=agent_section.get("name", "Customer Support Agent"),
        model=agent_section.get("model", "gpt-4o-2024-08-06"),
        tool_set=tool_set,
        memory=MemoryConfig(
            conversation=memory_section.get("conversation", True),
            episodic=memory_section.get("episodic", False),
            semantic=memory_section.get("semantic", False),
        ),
        refund_cap_usd=float(raw.get("refund_cap_usd", 200.0)),
    )


def profile_mtime(path: Path = PROFILE_PATH) -> float:
    """Modification time of the YAML file. Used by run.py for hot-reload."""
    return path.stat().st_mtime if path.exists() else 0.0
