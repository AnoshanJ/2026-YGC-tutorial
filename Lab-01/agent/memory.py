"""File-based episodic memory.

Each customer's prior interactions are stored as a markdown file at
`memory/customer_<id>.md`. When `memory.episodic` is true in agent-profile.yaml,
the file is loaded fully into the agent's system prompt at session start.

Same pattern as Claude Code's `CLAUDE.md`, GitHub Copilot's
`.github/copilot-instructions.md`, ChatGPT's bio. Production agents with
larger memory volumes swap this for vector retrieval (Mem0, Letta, Zep);
for one customer's history (a few dozen lines) full-load is the right call.

The agent updates memory via two tools:
- `remember(note)` — append a new entry (the daily move)
- `compact_memory(new_content)` — overwrite with a shorter summary (rare)
"""
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"


def _path(customer_id: str) -> Path:
    return MEMORY_DIR / f"customer_{customer_id}.md"


def load(customer_id: str) -> str:
    """Return the customer's full memory file contents (empty string if none)."""
    MEMORY_DIR.mkdir(exist_ok=True)
    p = _path(customer_id)
    return p.read_text() if p.exists() else ""


def append(customer_id: str, note: str) -> None:
    """Append a timestamped entry to the customer's memory file."""
    MEMORY_DIR.mkdir(exist_ok=True)
    p = _path(customer_id)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {timestamp}\n{note}\n"
    with p.open("a") as f:
        f.write(entry)


def write(customer_id: str, content: str) -> None:
    """Overwrite the customer's memory file (compaction)."""
    MEMORY_DIR.mkdir(exist_ok=True)
    _path(customer_id).write_text(content)


def clear(customer_id: str) -> None:
    """Remove a customer's memory file. Used for demo reset, not by agent."""
    p = _path(customer_id)
    if p.exists():
        p.unlink()
