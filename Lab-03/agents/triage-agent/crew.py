"""Order Triage Crew — 4 sub-agents, sequential process.

Each sub-agent emits its own OTEL agent-span via openinference-instrumentation-crewai,
producing the multi-agent trace hierarchy that's the showcase for Lab 3.
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Crew, Process, Task

from tools import (
    lookup_order_status,
    lookup_team_roster,
    policy_compliance_check,
    search_policy_kb,
    tone_check,
)

# CrewAI uses LiteLLM under the hood; we stick to OpenAI for the demo.
MODEL = "openai/gpt-4o-mini"


def _classifier() -> Agent:
    return Agent(
        role="Email Classifier",
        goal=(
            "Categorize an inbound customer support email into one of: "
            "refund_request, shipping_question, product_question, complaint, other. "
            "Always include a confidence score between 0 and 1."
        ),
        backstory=(
            "You are an experienced triage operator who has seen tens of thousands "
            "of customer emails. You spot intent quickly and never draft responses."
        ),
        tools=[],
        llm=MODEL,
        allow_delegation=False,
        verbose=False,
    )


def _router() -> Agent:
    return Agent(
        role="Team Router",
        goal=(
            "Given the email's category, decide which internal team should own "
            "the response and set a priority (low/normal/high)."
        ),
        backstory=(
            "You know the customer support org chart cold. You match work to teams "
            "by SLA and category, not by who's available."
        ),
        tools=[lookup_team_roster],
        llm=MODEL,
        allow_delegation=False,
        verbose=False,
    )


def _drafter() -> Agent:
    return Agent(
        role="Response Drafter",
        goal=(
            "Draft a concise, empathetic reply to the customer that addresses "
            "their request. Cite relevant policy when stating decisions. Look up "
            "order status when the email mentions an order id."
        ),
        backstory=(
            "You're a senior support writer. You acknowledge feelings, state the "
            "facts plainly, and never invent product details or commitments."
        ),
        tools=[search_policy_kb, lookup_order_status],
        llm=MODEL,
        allow_delegation=False,
        verbose=False,
    )


def _verifier() -> Agent:
    return Agent(
        role="Response Verifier",
        goal=(
            "Check the drafted response for tone and policy compliance. Return "
            "either 'approved' or 'needs_revision' with specific findings."
        ),
        backstory=(
            "You enforce the response standards: tone, PII leakage, and category-"
            "specific rules. You flag complaints that weren't escalated and any "
            "refund response that doesn't cite a policy."
        ),
        tools=[tone_check, policy_compliance_check],
        llm=MODEL,
        allow_delegation=False,
        verbose=False,
    )


def _build_tasks(agents: dict[str, Agent], email: dict[str, Any]) -> list[Task]:
    classify = Task(
        description=(
            "Classify the following email. Return a JSON object with keys "
            "'category' (one of refund_request, shipping_question, product_question, "
            "complaint, other) and 'confidence' (0..1).\n\n"
            f"From: {email.get('from', '')}\n"
            f"Subject: {email.get('subject', '')}\n"
            f"Body: {email.get('body', '')}"
        ),
        expected_output='JSON: {"category": ..., "confidence": ...}',
        agent=agents["classifier"],
    )
    route = Task(
        description=(
            "Given the classification from the previous step, look up the owning "
            "team and decide the priority. Return JSON: "
            '{"team": ..., "queue": ..., "priority": one of low|normal|high}.'
        ),
        expected_output='JSON: {"team": ..., "queue": ..., "priority": ...}',
        agent=agents["router"],
        context=[classify],
    )
    draft = Task(
        description=(
            "Write a concise reply (under 120 words) for the customer. Use "
            "search_policy_kb to ground policy statements; use lookup_order_status "
            "if the email references an order id. Do NOT include credit-card "
            "numbers, full mailing addresses, or any government ID."
        ),
        expected_output="A plain-text reply to send to the customer.",
        agent=agents["drafter"],
        context=[classify, route],
    )
    verify = Task(
        description=(
            "Run tone_check and policy_compliance_check on the draft from the "
            "previous step, with the category from the classifier. Return JSON: "
            '{"verdict": approved|needs_revision, "reasons": [...], "final": '
            "the draft text unchanged}."
        ),
        expected_output=('JSON: {"verdict": ..., "reasons": [...], "final": ...}'),
        agent=agents["verifier"],
        context=[classify, draft],
    )
    return [classify, route, draft, verify]


def run_triage(email: dict[str, Any]) -> Any:
    agents = {
        "classifier": _classifier(),
        "router": _router(),
        "drafter": _drafter(),
        "verifier": _verifier(),
    }
    tasks = _build_tasks(agents, email)
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )
    return crew.kickoff()
