"""Instance-level configuration, read from env at startup.

These map 1:1 onto the `configSchema` declared on the CS agent kind.
``ESCALATION_QUEUE`` is the kind-pinned (immutable) field; all others are
owner-mutable when the instance is created.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _env_float(name: str, default: float | None = None) -> float:
    raw = os.environ.get(name)
    if raw is None:
        if default is None:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return float(raw)


@dataclass(frozen=True)
class Config:
    region: str
    language: str
    currency: str
    refund_cap: float
    tone: str
    company_name: str
    additional_guidance: str
    escalation_queue: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            region=_env("REGION", "na"),
            language=_env("LANGUAGE", "en"),
            currency=_env("CURRENCY", "USD"),
            refund_cap=_env_float("REFUND_CAP", 200.0),
            tone=_env("TONE", "friendly"),
            company_name=_env("COMPANY_NAME", "Acme"),
            additional_guidance=_env("ADDITIONAL_GUIDANCE", ""),
            escalation_queue=_env("ESCALATION_QUEUE", "cs-escalations"),
        )
