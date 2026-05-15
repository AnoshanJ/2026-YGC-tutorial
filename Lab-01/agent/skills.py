"""Skill loader — parses skills/*.md with YAML frontmatter.

Anthropic-style skill discovery: each skill has a `name` + `description` in
frontmatter. The agent's system prompt advertises the catalog (just the
descriptions). When the agent decides a skill is relevant, it calls the
`read_skill` tool to load the full procedure on demand.

This file is responsible only for *parsing*. The catalog injection lives
in agent/core.py; the `read_skill` tool lives in agent/tools.py.
"""
import re
from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "skills"


@dataclass
class Skill:
    name: str           # from frontmatter, used as the dispatch key
    description: str    # one-line; this is what the agent reads to decide relevance
    body: str           # full markdown without the frontmatter block
    file_name: str      # for debugging / error messages


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Empty dict if no frontmatter."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        return {}, text

    fm_text, body = match.groups()
    fm: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm, body


def parse_skill_file(path: Path) -> Skill | None:
    """Parse a skill markdown file. Returns None if the file doesn't exist."""
    if not path.exists():
        return None
    text = path.read_text()
    fm, body = _parse_frontmatter(text)
    return Skill(
        name=fm.get("name") or path.stem,
        description=fm.get("description", ""),
        body=body.strip(),
        file_name=path.name,
    )


def list_skills() -> list[Skill]:
    """All skills under skills/, sorted by name. Files starting with _ are skipped
    (they're templates / drafts, not real skills)."""
    if not SKILLS_DIR.exists():
        return []
    out: list[Skill] = []
    for path in sorted(SKILLS_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        skill = parse_skill_file(path)
        if skill is not None:
            out.append(skill)
    return out


def load_skill_by_name(name: str) -> Skill | None:
    """Load a single skill by its `name` (the frontmatter field — NOT the
    filename, though for our convention they match)."""
    for skill in list_skills():
        if skill.name == name:
            return skill
    # Fall back: try by filename in case someone forgot the frontmatter name
    return parse_skill_file(SKILLS_DIR / f"{name}.md")
