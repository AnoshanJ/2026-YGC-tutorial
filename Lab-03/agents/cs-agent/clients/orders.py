"""Mocked order management client."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ._data import load

_OVERRIDES: dict[str, dict[str, Any]] = {}


class OrderNotFound(Exception):
    pass


class OrderImmutable(Exception):
    """Raised when a write is attempted on an order that's past the allowed state."""


def _get_raw(order_id: str) -> dict[str, Any]:
    if order_id in _OVERRIDES:
        return _OVERRIDES[order_id]
    for o in load("orders.json"):
        if o["id"] == order_id:
            return o
    raise OrderNotFound(f"No order with id {order_id!r}")


def get(order_id: str) -> dict[str, Any]:
    return deepcopy(_get_raw(order_id))


def list_for_customer(customer_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """List a customer's orders newest-first, with in-memory overrides applied.

    Refunds, cancellations, and address updates mutate `_OVERRIDES`; using disk
    data alone would hide those mutations from the agent across turns.
    """
    merged: list[dict[str, Any]] = []
    for o in load("orders.json"):
        if o["customer_id"] != customer_id:
            continue
        merged.append(deepcopy(_OVERRIDES.get(o["id"], o)))
    merged.sort(key=lambda o: o["created_at"], reverse=True)
    return merged[:limit]


def update_shipping_address(order_id: str, address: str) -> dict[str, Any]:
    o = deepcopy(_get_raw(order_id))
    if o["status"] not in ("processing",):
        raise OrderImmutable(
            f"Order {order_id} is in '{o['status']}' state; shipping address is locked."
        )
    o["shipping_address"] = address
    _OVERRIDES[order_id] = o
    return deepcopy(o)


def cancel(order_id: str, reason: str) -> dict[str, Any]:
    o = deepcopy(_get_raw(order_id))
    if o["status"] in ("shipped", "delivered", "cancelled"):
        raise OrderImmutable(
            f"Order {order_id} is in '{o['status']}' state and cannot be cancelled."
        )
    o["status"] = "cancelled"
    o["cancellation_reason"] = reason
    _OVERRIDES[order_id] = o
    return deepcopy(o)


def mark_refunded(order_id: str, amount: float, receipt_id: str) -> dict[str, Any]:
    """Stamp a refund onto the order so it's visible in subsequent reads.

    Idempotent in spirit but not strict: a second call overwrites the prior
    refund stamp. Callers (refunds.issue) decide whether to allow that.
    """
    o = deepcopy(_get_raw(order_id))
    o["refund_status"] = "refunded"
    o["refund_amount"] = amount
    o["refund_receipt_id"] = receipt_id
    o["refunded_at"] = datetime.now(timezone.utc).isoformat()
    _OVERRIDES[order_id] = o
    return deepcopy(o)
