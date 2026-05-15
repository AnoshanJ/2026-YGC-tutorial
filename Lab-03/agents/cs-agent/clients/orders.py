"""Mocked order management client."""

from __future__ import annotations

from copy import deepcopy
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
