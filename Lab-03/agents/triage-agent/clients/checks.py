"""Mocked compliance and tone checks used by the Verifier sub-agent."""

from __future__ import annotations

import re
from typing import Any

_NEGATIVE_PHRASES = (
    "not my problem",
    "you should have",
    "that's wrong",
    "tough luck",
    "we can't help",
    "stop emailing",
)
_PII_PATTERNS = (
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),  # credit-card-ish
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # US SSN-ish
)


def tone(text: str) -> dict[str, Any]:
    lowered = text.lower()
    hits = [p for p in _NEGATIVE_PHRASES if p in lowered]
    return {
        "verdict": "negative" if hits else "neutral_or_positive",
        "negative_phrases": hits,
        "length_chars": len(text),
    }


def policy_compliance(text: str, category: str) -> dict[str, Any]:
    findings: list[str] = []
    for pat in _PII_PATTERNS:
        if pat.search(text):
            findings.append("contains_pii")
            break
    if category == "complaint" and "escalat" not in text.lower():
        findings.append("complaint_without_escalation")
    if category == "refund_request" and "policy" not in text.lower():
        findings.append("refund_without_policy_citation")
    return {
        "compliant": not findings,
        "findings": findings,
    }
