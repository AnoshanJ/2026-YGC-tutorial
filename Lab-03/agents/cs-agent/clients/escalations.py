"""Mocked human-escalation queue."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

_QUEUE: list[dict[str, Any]] = []


def create(customer_id: str, summary: str, priority: str, queue: str) -> dict[str, Any]:
    ticket = {
        "ticket_id": f"ESC-{uuid.uuid4().hex[:6].upper()}",
        "customer_id": customer_id,
        "summary": summary,
        "priority": priority,
        "queue": queue,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
    }
    _QUEUE.append(ticket)
    return dict(ticket)


def recent(limit: int = 10) -> list[dict[str, Any]]:
    return list(_QUEUE[-limit:])
