"""Mocked team-roster lookup."""

from __future__ import annotations

from typing import Any

from ._data import load


def lookup_for_category(category: str) -> dict[str, Any]:
    teams = load("teams.json")
    for team in teams:
        if category in team["categories"]:
            return dict(team)
    # default fallback
    for team in teams:
        if "other" in team["categories"]:
            return dict(team)
    return {"name": "unknown", "queue": "support.general", "sla_hours": 24, "lead": ""}
