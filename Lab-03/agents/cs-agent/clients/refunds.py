"""Mocked refund-issuing client.

Refund cap enforcement lives here so the rejection appears as a backend response
(realistic) rather than as control flow inside the tool wrapper.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from . import orders as orders_client

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
    # Stamp the order so subsequent reads (get_order, get_customer_orders)
    # reflect that this order was already refunded. Best-effort: if the order
    # row is missing, we still return the receipt — the refund happened.
    try:
        orders_client.mark_refunded(
            order_id=order_id,
            amount=amount,
            receipt_id=receipt["receipt_id"],
        )
    except orders_client.OrderNotFound:
        pass
    return dict(receipt)


def recent(limit: int = 10) -> list[dict[str, Any]]:
    return list(_LOG[-limit:])
