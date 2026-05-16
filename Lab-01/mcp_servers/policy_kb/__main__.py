"""Local MCP server exposing the company policy KB.

Runs as a subprocess of the agent (launched via Strands' MCPClient from
agent/core.py). The agent calls `search_policy_kb(query)` like a native
tool; under the hood, this server reads `policies/*.md` and returns the
matching ones.

In production this would be a hosted service owned by the policy /
compliance team. The agent team never edits policy content — they just
call the MCP tool.

To run standalone (for debugging):
    python -m mcp_servers.policy_kb
"""

import logging
import re
from pathlib import Path

# Silence MCP framework's INFO logs (e.g. "Processing request of type
# ListToolsRequest" on every agent build) — keeps the on-stage trace clean.
logging.basicConfig(level=logging.WARNING)
for noisy in ("mcp", "mcp.server", "mcp.server.lowlevel", "FastMCP"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from mcp.server.fastmcp import FastMCP  # noqa: E402  — after logging config

mcp = FastMCP("policy-kb")

# policies/ sits at the repo root, next to agent/ and mcp_servers/
POLICIES_DIR = Path(__file__).parent.parent.parent / "policies"


def _parse_policy(path: Path) -> dict:
    """Parse a policy markdown file. Returns id, title, keywords, rule, full_text.

    Format: YAML frontmatter + markdown body. We extract frontmatter manually
    instead of pulling in another dep just for that.
    """
    text = path.read_text()

    # Frontmatter between --- markers
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not fm_match:
        # No frontmatter — return body only
        return {
            "id": path.stem,
            "title": path.stem.replace("_", " ").title(),
            "keywords": [],
            "rule": text.strip(),
            "full_text": text.strip(),
        }

    fm_text, body = fm_match.groups()

    # Parse simple YAML (no nesting needed for our schema)
    fm: dict = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            # Inline list — split by comma
            value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        fm[key] = value

    return {
        "id": fm.get("id", path.stem),
        "title": fm.get("title", path.stem),
        "keywords": fm.get("keywords", [])
        if isinstance(fm.get("keywords"), list)
        else [],
        "rule": body.strip(),
        "full_text": text.strip(),
    }


def _load_policies() -> list[dict]:
    """Read every .md in policies/, parsed."""
    if not POLICIES_DIR.exists():
        return []
    return [_parse_policy(p) for p in sorted(POLICIES_DIR.glob("*.md"))]


@mcp.tool()
def search_policy_kb(query: str) -> list[dict]:
    """Search the company policy knowledge base.

    Returns the most relevant policies for the query. Each result includes:
      - `id`           — short policy identifier (e.g., "damaged_item")
      - `title`        — human-readable title
      - `rule`         — the policy body (the authoritative content)
      - `relevance`    — keyword-match score

    Always call this BEFORE taking compensating actions (refunds, credits,
    address changes). Don't memorize rules — they change. The audit trail
    proves you checked.
    """
    policies = _load_policies()
    q = query.lower()
    matches: list[tuple[int, dict]] = []

    for p in policies:
        score = 0
        for kw in p["keywords"]:
            if isinstance(kw, str) and kw.lower() in q:
                score += 2
        # Title words also count
        for word in p["title"].lower().split():
            if word in q and len(word) > 3:
                score += 1
        if score > 0:
            matches.append((score, p))

    matches.sort(key=lambda x: x[0], reverse=True)

    if not matches:
        return [
            {
                "id": "no_match",
                "title": "No matching policy",
                "rule": (
                    "No policy in the knowledge base matched this query. "
                    "If unsure how to proceed, escalate to a human via "
                    "escalate_to_human."
                ),
                "relevance": 0,
            }
        ]

    return [
        {
            "id": p["id"],
            "title": p["title"],
            "rule": p["rule"],
            "relevance": score,
        }
        for score, p in matches[:3]
    ]


if __name__ == "__main__":
    # Stdio transport — what the agent connects to via Strands' MCPClient
    mcp.run(transport="stdio")
