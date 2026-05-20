"""File-based episodic memory.

Each customer's prior interactions are stored as a markdown file at
`memory/episodic/customer_<id>.md`. When `memory.episodic.enabled` is true in
agent-profile.yaml, the file is loaded fully into the agent's system
prompt at agent build (see `agent/core.py::_memory_section`). Conversation
history (within-session chat) is separate — it's `agent.messages` on the
per-customer cached Agent in `main.py`, no on-disk transcript.

Same pattern as Claude Code's `CLAUDE.md` + `MEMORY.md`, GitHub Copilot's
`.github/copilot-instructions.md`, ChatGPT's bio. Production agents with
larger memory volumes swap this for vector retrieval (Mem0, Letta, Zep);
for one customer's history (a few dozen lines) full-load is the right call.

Two layers live here:
- The `load` / `append` / `write` / `clear` helpers — pure file ops, also
  used by `agent/core.py` to inject memory into the system prompt at build
  time and by `reset.py` for demo cleanup.
- The `append_memory` / `compact_memory` Strands tools — `@tool`-decorated
  wrappers the agent calls during the loop. They live here (in-process
  with the agent) rather than in an MCP server because memory is
  session-scoped state the agent owns end-to-end — there's no team
  boundary to cross. See README §2b's "tools that stay local" rule.
"""

from datetime import datetime
from pathlib import Path

from strands import tool

MEMORY_DIR = Path(__file__).parent.parent / "memory" / "episodic"


def _path(customer_id: str) -> Path:
    return MEMORY_DIR / f"customer_{customer_id}.md"


def load(customer_id: str) -> str:
    """Return the customer's full memory file contents (empty string if none)."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(customer_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def append(customer_id: str, note: str) -> None:
    """Append a timestamped entry to the customer's memory file."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(customer_id)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {timestamp}\n{note}\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(entry)


def write(customer_id: str, content: str) -> None:
    """Overwrite the customer's memory file (compaction)."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _path(customer_id).write_text(content, encoding="utf-8")


def clear(customer_id: str) -> None:
    """Remove a customer's memory file. Used for demo reset, not by agent."""
    p = _path(customer_id)
    if p.exists():
        p.unlink()


# ----- Agent-facing tools -------------------------------------------------


@tool
def append_memory(customer_id: str, note: str) -> dict:
    """Append one short note to this customer's episodic-memory log.

    Use append_memory to store episodic memory for information the DB does not model well: customer situation, promises made, emotional tone, urgency, and recurring patterns.

    Keep entries short and actionable. Include when relevant:

    Order ID or entity involved
    Action/promise made
    Customer tone (1–2 words)
    Important pattern or context

    Reference DB records instead of duplicating tool-retrievable facts like order status, refund refs, ticket IDs, or policy text.

    Good:
    #1234 delayed; customer flying tomorrow. Issued $10 shipping_delay credit. Tone: pressed but reasonable.

    Bad:
    Customer upset about delayed order and travel deadline.

    Do not call append_memory for routine informational exchanges. Episodic memory is a continuity layer, not a transcript.

    customer_id is injected by the harness; pass an empty string or placeholder if required.
    """
    append(customer_id, note)
    return {"ok": True, "saved_for": customer_id}


@tool
def compact_memory(customer_id: str, new_content: str) -> dict:
    """Rewrite the customer's entire memory file with a compacted version.

    Use ONLY when the existing memory has grown long and rambling. You
    are OVERWRITING; old content is replaced. Be careful.
    """
    write(customer_id, new_content)
    return {"ok": True, "rewrote": customer_id}
