"""Mocked policy-KB search client.

The KB endpoint is region-scoped via the agent's configuration. Internally we
just key into the region-specific JSON file shipped with the agent.
"""

from __future__ import annotations

from typing import Any

from ._data import load

_REGION_FILES = {
    "na": "policies-na.json",
    "emea": "policies-emea.json",
    "apac": "policies-apac.json",
}


def search(region: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    filename = _REGION_FILES.get(region.lower())
    if not filename:
        return []
    docs = load(filename)
    q = query.lower().strip()
    if not q:
        return docs[:limit]
    scored: list[tuple[int, dict[str, Any]]] = []
    for d in docs:
        score = 0
        text = f"{d['title']} {d['body']}".lower()
        for token in q.split():
            if token in text:
                score += 1
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:limit]] or docs[:limit]
