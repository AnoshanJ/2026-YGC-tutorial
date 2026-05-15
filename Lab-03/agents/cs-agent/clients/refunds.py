"""Mocked refund-issuing client.

Refund cap enforcement lives here so the rejection appears as a backend response
(realistic) rather than as control flow inside the tool wrapper.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

_LOG: list[dict[str, Any]] = []


class RefundOverCap(Exception):
    def __init__(self, amount: float, cap: float, currency: str):
        super().__init__(
            f"Refund amount {amount} {currency} exceeds the configured cap of {cap} {currency}."
        )
        self.amount = amount
        self.cap = cap
        self.currency = currency


def issue(
    order_id: str,
    amount: float,
    reason: str,
    cap: float,
    currency: str,
) -> dict[str, Any]:
    if amount > cap:
        raise RefundOverCap(amount=amount, cap=cap, currency=currency)
    receipt = {
        "receipt_id": f"R-{uuid.uuid4().hex[:8].upper()}",
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "reason": reason,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "status": "issued",
    }
    _LOG.append(receipt)
    return dict(receipt)


def recent(limit: int = 10) -> list[dict[str, Any]]:
    return list(_LOG[-limit:])
