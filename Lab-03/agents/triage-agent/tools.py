"""Tool definitions exposed to the triage crew's sub-agents.

Each tool delegates to a mocked client. Results are returned as JSON strings
since CrewAI tool outputs are text.
"""

from __future__ import annotations

import json

from crewai.tools import tool

from clients import checks as checks_client
from clients import orders as orders_client
from clients import policies as policies_client
from clients import teams as teams_client


@tool("lookup_team_roster")
def lookup_team_roster(category: str) -> str:
    """Look up which support team handles a triage category.

    Returns team name, queue, SLA hours, and team lead as JSON.
    """
    return json.dumps(teams_client.lookup_for_category(category))


@tool("lookup_order_status")
def lookup_order_status(order_id: str) -> str:
    """Look up an order's shipping status, carrier, tracking, and ETA."""
    return json.dumps(orders_client.status_for(order_id))


@tool("search_policy_kb")
def search_policy_kb(query: str) -> str:
    """Search the policy knowledge base for relevant snippets."""
    return json.dumps(policies_client.search(query))


@tool("tone_check")
def tone_check(text: str) -> str:
    """Score a drafted response for tone (negative / neutral_or_positive)."""
    return json.dumps(checks_client.tone(text))


@tool("policy_compliance_check")
def policy_compliance_check(text: str, category: str) -> str:
    """Check a drafted response for PII leaks and policy compliance for the category."""
    return json.dumps(checks_client.policy_compliance(text, category))
